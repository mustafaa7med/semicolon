from __future__ import annotations
import re
import textwrap
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
import sqlparse
from sqlparse import tokens as TT
from .keywords import (
    RIVER,
    CLAUSE_KEYWORDS,
    NEWLINE_STARTERS,
    CONJUNCT_KEYWORDS,
    PADDED,
    KEYWORD_SUFFIX,
    AS_SUFFIX,
    SQL_KEYWORDS,
    pad_keyword,
)

_FUNC_SPACE_RE = re.compile(r'(\w)\s+\(')

# SQL keywords that must keep a space before '(' (not function calls)
_KW_SPACE_BEFORE_PAREN_RE = re.compile(
    r'\b(IN|NOT|ANY|SOME|ALL|EXISTS|OVER|WITHIN|FILTER)\(',
    re.IGNORECASE,
)

_OPERATOR_RE = re.compile(
    r'\s*([=<>!]+|::|\|\||\+|-(?!-)|(?<!\()\*(?!\))|/|%|@>|<@|&&|\|\|)\s*'
)

def _is_keyword_token(ttype) -> bool:
    return ttype in (TT.Keyword, TT.Keyword.DML, TT.Keyword.DDL,
                     TT.Keyword.CTE, TT.Keyword.Order, TT.Keyword.Type)


def _uppercase_keywords(sql: str) -> str:
    # Uppercase all SQL keywords while leaving string literals and comments.
    result = []
    for tok in sqlparse.parse(sql)[0].flatten():
        val = tok.value
        if _is_keyword_token(tok.ttype):
            result.append(val.upper())
        elif tok.ttype is TT.Name and val.upper() in SQL_KEYWORDS:
            result.append(val.upper())
        else:
            result.append(val)
    return "".join(result)


def _strip_extra_whitespace(sql: str) -> str:
    return sqlparse.format(sql, strip_whitespace=True)

@dataclass
class Clause:
    keyword: str          # e.g. "SELECT", "LEFT JOIN", "ORDER BY"
    content: str          # raw content after the keyword (stripped)


def _split_into_clauses(sql: str) -> List[Clause]:
    starters = sorted(NEWLINE_STARTERS, key=len, reverse=True)
    pat = re.compile(
        r'\b(' + '|'.join(re.escape(s) for s in starters) + r')\b',
        re.IGNORECASE,
    )

    flat_tokens: list[tuple] = []
    for tok in sqlparse.parse(sql)[0].flatten():
        flat_tokens.append((tok.ttype, tok.value))

    clauses: List[Clause] = []
    current_kw = ""
    current_parts: List[str] = []
    depth = 0
    i = 0

    while i < len(flat_tokens):
        ttype, val = flat_tokens[i]

        # Track parenthesis depth
        if val == '(':
            depth += 1
            current_parts.append(val)
            i += 1
            continue
        if val == ')':
            depth -= 1
            current_parts.append(val)
            i += 1
            continue

        if depth == 0 and _is_keyword_token(ttype):
            upper = val.upper()
            # Try to match multi-word keywords (look ahead for BY, ALL, etc.)
            combined = upper
            j = i + 1
            # Peek ahead skipping whitespace
            while j < len(flat_tokens):
                pt, pv = flat_tokens[j]
                if pt in (TT.Whitespace, TT.Newline, TT.Whitespace.Newline):
                    j += 1
                    continue
                if _is_keyword_token(pt) and pv.upper() in ('BY', 'ALL', 'INTO', 'JOIN', 'OUTER'):
                    combined = combined + ' ' + pv.upper()
                    j += 1
                    continue
                break

            if combined in NEWLINE_STARTERS:
                # Save previous clause
                if current_kw or current_parts:
                    clauses.append(Clause(
                        keyword=current_kw,
                        content=' '.join(''.join(current_parts).split()),
                    ))
                current_kw = combined
                current_parts = []
                i = j
                continue
            elif upper in NEWLINE_STARTERS:
                if current_kw or current_parts:
                    clauses.append(Clause(
                        keyword=current_kw,
                        content=' '.join(''.join(current_parts).split()),
                    ))
                current_kw = upper
                current_parts = []
                i += 1
                continue

        current_parts.append(val)
        i += 1

    # Flush last clause
    if current_kw or current_parts:
        clauses.append(Clause(
            keyword=current_kw,
            content=' '.join(''.join(current_parts).split()),
        ))

    return clauses


@dataclass
class Column:
    expression: str
    alias: Optional[str] = None
    alias_explicit: bool = True  # False when alias has no AS keyword


def _split_columns(content: str) -> List[Column]:
    cols: List[Column] = []
    depth = 0
    current: List[str] = []
    i = 0

    while i < len(content):
        ch = content[i]
        if ch == '(':
            depth += 1
            current.append(ch)
        elif ch == ')':
            depth -= 1
            current.append(ch)
        elif ch == ',' and depth == 0:
            raw = ''.join(current).strip()
            if raw:
                cols.append(_parse_column(raw))
            current = []
        else:
            current.append(ch)
        i += 1

    raw = ''.join(current).strip()
    if raw:
        cols.append(_parse_column(raw))

    return cols


def _parse_column(raw: str) -> Column:
    tokens = list(sqlparse.parse(raw)[0].flatten())
    as_pos = None
    depth = 0
    for idx, tok in enumerate(tokens):
        if tok.value == '(':
            depth += 1
        elif tok.value == ')':
            depth -= 1
        elif (depth == 0
              and tok.ttype in (TT.Keyword, TT.Keyword.DML)
              and tok.value.upper() == 'AS'):
            as_pos = idx
    if as_pos is not None:
        expr_parts = [t.value for t in tokens[:as_pos]]
        alias_parts = [t.value for t in tokens[as_pos + 1:]]
        expr = ''.join(expr_parts).strip()
        alias = ''.join(alias_parts).strip()
        return Column(expression=expr, alias=alias, alias_explicit=True)
    # No AS keyword — check for implicit alias on a parenthesized expression:
    # e.g. "(SELECT ...) alias_name"
    s = raw.strip()
    if s.startswith('('):
        d, close_idx = 0, -1
        for i, ch in enumerate(s):
            if ch == '(':
                d += 1
            elif ch == ')':
                d -= 1
                if d == 0:
                    close_idx = i
                    break
        if close_idx >= 0:
            after = s[close_idx + 1:].strip()
            if after and re.match(r'^\w+$', after):
                return Column(expression=s[:close_idx + 1], alias=after, alias_explicit=False)
    return Column(expression=raw.strip())


def _format_select_columns(cols: List[Column], indent: str) -> str:
    if not cols:
        return ""

    col_start = len(indent)

    normed = [
        Column(
            expression=_FUNC_SPACE_RE.sub(r'\1(', c.expression),
            alias=c.alias,
            alias_explicit=c.alias_explicit,
        )
        for c in cols
    ]

    # AS wall: only for non-subquery, non-CASE columns with an explicit AS alias.
    aliased = [c for c in normed if c.alias and c.alias_explicit
               and not _is_subquery_expr(c.expression)
               and not _is_case_expr(c.expression)]
    as_col = max((len(c.expression) for c in aliased), default=0)

    col_indent = " " * col_start

    lines: List[str] = []
    for i, col in enumerate(normed):
        is_last = i == len(normed) - 1
        suffix = "" if is_last else ","

        if _is_subquery_expr(col.expression):
            inner = col.expression.strip()[1:-1].strip()
            sub_block = _format_subquery_inline(inner, col_start)
            sub_lines_list = sub_block.splitlines()
            if col.alias:
                alias_str = f" AS {col.alias}" if col.alias_explicit else f" {col.alias}"
                sub_lines_list[-1] = sub_lines_list[-1] + alias_str
            sub_lines_list[-1] = sub_lines_list[-1] + suffix
            if i != 0:
                sub_lines_list[0] = col_indent + sub_lines_list[0]
            lines.append("\n".join(sub_lines_list))
        elif _is_case_expr(col.expression):
            case_block = _format_case_expr(col.expression, col_start)
            case_lines_list = case_block.splitlines()
            if col.alias:
                alias_str = f" AS {col.alias}" if col.alias_explicit else f" {col.alias}"
                case_lines_list[-1] = case_lines_list[-1] + alias_str
            case_lines_list[-1] = case_lines_list[-1] + suffix
            if i != 0:
                case_lines_list[0] = col_indent + case_lines_list[0]
            lines.append("\n".join(case_lines_list))
        else:
            if col.alias:
                if col.alias_explicit:
                    expr_padded = col.expression.ljust(as_col)
                    col_str = f"{expr_padded} AS {col.alias}"
                else:
                    col_str = f"{col.expression} {col.alias}"
            else:
                col_str = col.expression

            if i == 0:
                lines.append(f"{col_str}{suffix}")
            else:
                lines.append(f"{col_indent}{col_str}{suffix}")

    return "\n".join(lines)

@dataclass
class Conjunct:
    operator: str   
    expression: str


def _split_conjuncts(content: str) -> List[Conjunct]:
    conjuncts: List[Conjunct] = []
    current: List[str] = []
    depth = 0
    between_active = False

    tokens = list(sqlparse.parse(content)[0].flatten())
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        val = tok.value
        uval = val.upper()

        if val == '(':
            depth += 1
            current.append(val)
            i += 1
            continue
        if val == ')':
            depth -= 1
            current.append(val)
            i += 1
            continue

        if depth == 0 and _is_keyword_token(tok.ttype):
            if uval == 'BETWEEN':
                between_active = True
                current.append(val)
                i += 1
                continue
            if uval == 'AND' and between_active:
                # This AND belongs to BETWEEN ... AND
                between_active = False
                current.append(val)
                i += 1
                continue
            if uval in ('AND', 'OR'):
                expr = ''.join(current).strip()
                if expr:
                    if not conjuncts:
                        conjuncts.append(Conjunct('', expr))
                    else:
                        pass
                conjuncts_expr = ''.join(current).strip()
                if conjuncts_expr:
                    conjuncts.append(Conjunct('' if not conjuncts else uval, conjuncts_expr))
                    current = []
                else:
                    current.append(val)
                i += 1
                continue

        current.append(val)
        i += 1

    expr = ''.join(current).strip()
    if expr:
        if not conjuncts:
            conjuncts.append(Conjunct('', expr))
        else:
            conjuncts.append(Conjunct('AND', expr))  # fallback

    return conjuncts


def _split_conjuncts_v2(content: str) -> List[Conjunct]:
    tokens_flat = list(sqlparse.parse(content)[0].flatten())
    parts: List[Conjunct] = []
    current_toks: List[str] = []
    depth = 0
    between_seen = False
    operator = ""

    for tok in tokens_flat:
        val = tok.value
        uval = val.strip().upper()

        if val == '(':
            depth += 1
            current_toks.append(val)
            continue
        if val == ')':
            depth -= 1
            current_toks.append(val)
            continue

        if depth == 0 and _is_keyword_token(tok.ttype):
            if uval == 'BETWEEN':
                between_seen = True
                current_toks.append(val)
                continue
            if uval == 'AND' and between_seen:
                between_seen = False
                current_toks.append(val)
                continue
            if uval in ('AND', 'OR'):
                expr = ''.join(current_toks).strip()
                if expr:
                    parts.append(Conjunct(operator, expr))
                operator = uval
                current_toks = []
                continue

        current_toks.append(val)

    expr = ''.join(current_toks).strip()
    if expr:
        parts.append(Conjunct(operator, expr))

    return parts


def _format_between(expr: str, col_offset: int) -> str:
    m = re.search(r'\bBETWEEN\b', expr, re.IGNORECASE)
    if not m:
        return expr

    before = expr[:m.start()]
    rest = expr[m.end():]

    and_m = re.search(r'\bAND\b', rest, re.IGNORECASE)
    if not and_m:
        return expr

    between_val = rest[:and_m.start()].strip()
    after_and = rest[and_m.end():].strip()
    between_start = col_offset + len(before)
    and_indent = between_start + 4
    and_prefix = " " * and_indent

    line1 = f"{before}BETWEEN {between_val}"
    line2 = f"{and_prefix}AND {after_and}"
    return f"{line1}\n{line2}"

@dataclass
class CTEBlock:
    name: str
    body_sql: str  


def _parse_ctes(sql: str) -> Tuple[List[CTEBlock], str]:
    ctes: List[CTEBlock] = []
    rest = sql.strip()
    if not re.match(r'^WITH\b', rest, re.IGNORECASE):
        return [], rest

    rest = rest[4:].strip()

    while True:
        m = re.match(
            r'^(RECURSIVE\s+)?(\w+)\s+AS\s*\(',
            rest,
            re.IGNORECASE,
        )
        if not m:
            break

        cte_name = m.group(2)
        rest = rest[m.end():]  
        depth = 1
        i = 0
        while i < len(rest) and depth > 0:
            if rest[i] == '(':
                depth += 1
            elif rest[i] == ')':
                depth -= 1
            i += 1

        body = rest[:i - 1]
        rest = rest[i:].strip()
        ctes.append(CTEBlock(name=cte_name, body_sql=body.strip()))

        if rest.startswith(','):
            rest = rest[1:].strip()
            if re.match(r'^(SELECT|INSERT|UPDATE|DELETE)\b', rest, re.IGNORECASE):
                break
        else:
            break

    return ctes, rest

def _format_subquery(sql: str, extra_indent: int = 0) -> str:
    """Format a subquery SQL with extra indentation."""
    formatted = _format_select_statement(sql.strip())
    indent = " " * extra_indent
    lines = formatted.splitlines()
    return "\n".join(indent + line for line in lines)


_JOIN_KEYWORDS_BY_LEN = [
    "RIGHT OUTER JOIN",
    "LEFT OUTER JOIN",
    "FULL OUTER JOIN",
    "RIGHT JOIN",
    "INNER JOIN",
    "CROSS JOIN",
    "LEFT JOIN",
    "FULL JOIN",
    "JOIN",
]


def _effective_river(sql: str) -> int:
    upper = sql.upper()
    for jk in _JOIN_KEYWORDS_BY_LEN:
        if re.search(r'\b' + re.escape(jk) + r'\b', upper):
            candidate = len(jk) + 1
            return candidate if candidate > RIVER else RIVER
    return RIVER


def _normalize_expression(expr: str) -> str:
    result = _FUNC_SPACE_RE.sub(r'\1(', expr)
    result = _KW_SPACE_BEFORE_PAREN_RE.sub(r'\1 (', result)
    return _normalize_operators(result)


def _normalize_operators(expr: str) -> str:
    tokens = list(sqlparse.parse(expr)[0].flatten())
    out: List[str] = []
    for tok in tokens:
        if tok.ttype in (TT.Comparison, TT.Operator):
            out.append(f" {tok.value.strip()} ")
        elif tok.ttype is TT.Whitespace and out and out[-1].endswith(' '):
            continue 
        else:
            out.append(tok.value)
    result = "".join(out)
    return re.sub(r'  +', ' ', result)


def _has_select_inside(s: str) -> bool:
    depth = 0
    tokens = list(sqlparse.parse(s)[0].flatten())
    for tok in tokens:
        if tok.value == '(':
            depth += 1
        elif tok.value == ')':
            depth -= 1
        elif depth == 1 and _is_keyword_token(tok.ttype) and tok.value.upper() == 'SELECT':
            return True
    return False


def _is_subquery_expr(expr: str) -> bool:
    s = expr.strip()
    if not s.startswith('('):
        return False
    depth = 0
    for i, ch in enumerate(s):
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth -= 1
            if depth == 0:
                inner = s[1:i].strip()
                remainder = s[i + 1:].strip()
                return (not remainder and
                        bool(re.match(r'^SELECT\b', inner, re.IGNORECASE)))
    return False


def _is_case_expr(expr: str) -> bool:
    """True if expr is a top-level CASE...END expression."""
    s = expr.strip()
    return (bool(re.match(r'^CASE\b', s, re.IGNORECASE)) and
            bool(re.search(r'\bEND\s*$', s, re.IGNORECASE)))


def _parse_case_branches(expr: str):
    s = expr.strip()[4:].strip()  # strip 'CASE'
    end_m = re.search(r'\bEND\s*$', s, re.IGNORECASE)
    if end_m:
        s = s[:end_m.start()].strip()

    tokens = list(sqlparse.parse(s)[0].flatten())
    branches = []
    else_value = None
    i = 0

    while i < len(tokens):
        tok = tokens[i]
        uval = tok.value.strip().upper()

        if _is_keyword_token(tok.ttype) and uval == 'WHEN':
            i += 1
            cond_toks: List[str] = []
            depth = 0
            between_active = False

            while i < len(tokens):
                t = tokens[i]
                tv = t.value
                tuval = tv.strip().upper()
                if tv == '(':
                    depth += 1
                    cond_toks.append(tv)
                    i += 1
                elif tv == ')':
                    depth -= 1
                    cond_toks.append(tv)
                    i += 1
                elif depth == 0 and _is_keyword_token(t.ttype) and tuval == 'BETWEEN':
                    between_active = True
                    cond_toks.append(tv)
                    i += 1
                elif depth == 0 and _is_keyword_token(t.ttype) and tuval == 'AND' and between_active:
                    between_active = False
                    cond_toks.append(tv)
                    i += 1
                elif depth == 0 and _is_keyword_token(t.ttype) and tuval == 'THEN':
                    i += 1
                    break
                else:
                    cond_toks.append(tv)
                    i += 1

            condition = ' '.join(''.join(cond_toks).split())

            then_toks: List[str] = []
            depth = 0
            while i < len(tokens):
                t = tokens[i]
                tv = t.value
                tuval = tv.strip().upper()
                if tv == '(':
                    depth += 1
                    then_toks.append(tv)
                    i += 1
                elif tv == ')':
                    depth -= 1
                    then_toks.append(tv)
                    i += 1
                elif depth == 0 and _is_keyword_token(t.ttype) and tuval in ('WHEN', 'ELSE'):
                    break
                else:
                    then_toks.append(tv)
                    i += 1

            branches.append((condition, ' '.join(''.join(then_toks).split())))

        elif _is_keyword_token(tok.ttype) and uval == 'ELSE':
            i += 1
            else_toks: List[str] = []
            while i < len(tokens):
                t = tokens[i]
                tv = t.value
                tuval = tv.strip().upper()
                if _is_keyword_token(t.ttype) and tuval in ('END', 'WHEN'):
                    break
                else_toks.append(tv)
                i += 1
            else_value = ' '.join(''.join(else_toks).split())
        else:
            i += 1

    return branches, else_value


def _format_case_expr(expr: str, case_col: int) -> str:
    branches, else_value = _parse_case_branches(expr)
    if not branches:
        return expr

    max_cond = max(len(cond) for cond, _ in branches)
    when_indent = " " * (case_col + 5)   
    end_indent = " " * (case_col + 1)    

    lines: List[str] = []
    for idx, (cond, then_val) in enumerate(branches):
        when_line = f"WHEN {cond.ljust(max_cond)} THEN {then_val}"
        if idx == 0:
            lines.append(f"CASE {when_line}")
        else:
            lines.append(f"{when_indent}{when_line}")

    if else_value is not None:
        lines.append(f"{when_indent}ELSE {else_value}")

    lines.append(f"{end_indent}END")
    return "\n".join(lines)


def _format_subquery_inline(inner_sql: str, open_paren_col: int) -> str:
    formatted = _format_select_statement(inner_sql.strip())
    sub_lines = formatted.splitlines()
    non_empty = [l for l in sub_lines if l.strip()]
    if not non_empty:
        return f"({inner_sql})"

    min_indent = min(len(l) - len(l.lstrip()) for l in non_empty)

    result = ["(" + sub_lines[0].lstrip()]
    for line in sub_lines[1:]:
        if line.strip():
            result.append(" " * (open_paren_col + 1) + line[min_indent:])
        else:
            result.append("")
    result.append(" " * (open_paren_col + min_indent) + ")")
    return "\n".join(result)


def _expand_subqueries_in_expr(expr: str, expr_col: int) -> str:
    out: List[str] = []
    i = 0
    while i < len(expr):
        if expr[i] != '(':
            out.append(expr[i])
            i += 1
            continue

        depth = 1
        j = i + 1
        while j < len(expr) and depth > 0:
            if expr[j] == '(':
                depth += 1
            elif expr[j] == ')':
                depth -= 1
            j += 1

        inner = expr[i + 1:j - 1].strip()
        if re.match(r'^SELECT\b', inner, re.IGNORECASE):
            joined = ''.join(out)
            last_nl = joined.rfind('\n')
            paren_col = (len(joined) - last_nl - 1) if last_nl >= 0 else (expr_col + len(joined))
            out.append(_format_subquery_inline(inner, paren_col))
            i = j
        else:
            out.append(expr[i:j])
            i = j

    return ''.join(out)


def _format_clause(clause: Clause, extra_indent: int = 0, effective_river: int = RIVER) -> str:
    kw = clause.keyword
    content = clause.content
    padded_kw = pad_keyword(kw, effective_river)
    ei = " " * extra_indent

    if not kw:
        return ei + content

    prefix = f"{ei}{padded_kw}{KEYWORD_SUFFIX}"

    if kw in ('SELECT', 'DISTINCT'):
        cols = _split_columns(content)
        if not cols:
            return f"{prefix}*"
        col_block = _format_select_columns(cols, prefix)
        return f"{prefix}{col_block}"

    if kw in ('FROM', 'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN',
              'CROSS JOIN', 'LEFT OUTER JOIN', 'RIGHT OUTER JOIN',
              'FULL OUTER JOIN', 'FULL JOIN'):
        if '(' in content and _has_select_inside(content):
            inner, alias = _extract_subquery_and_alias(content)
            sub_fmt = _format_subquery(inner, extra_indent=extra_indent + effective_river + 2)
            if alias:
                return (f"{prefix}(\n\n{sub_fmt}\n\n"
                        f"{ei}{' ' * (len(padded_kw) + 2)}) AS {alias}")
            return (f"{prefix}(\n\n{sub_fmt}\n\n"
                    f"{ei}{' ' * (len(padded_kw) + 2)})")
        return f"{prefix}{content}"

    if kw == 'ON':
        return f"{prefix}{_normalize_expression(content)}"

    if kw in ('WHERE', 'HAVING'):
        conjuncts = _split_conjuncts_v2(content)
        if not conjuncts:
            return f"{prefix}{content}"
        lines: List[str] = []
        for c in conjuncts:
            op = c.operator
            expr = _normalize_expression(c.expression)
            if op == "":
                if re.search(r'\bBETWEEN\b', expr, re.IGNORECASE):
                    formatted_expr = _format_between(
                        expr,
                        col_offset=extra_indent + len(padded_kw) + len(KEYWORD_SUFFIX),
                    )
                    lines.append(f"{prefix}{formatted_expr}")
                else:
                    expanded = _expand_subqueries_in_expr(expr, len(prefix))
                    lines.append(f"{prefix}{expanded}")
            else:
                op_padded = pad_keyword(op, effective_river)
                op_prefix = f"{ei}{op_padded}{KEYWORD_SUFFIX}"
                if re.search(r'\bBETWEEN\b', expr, re.IGNORECASE):
                    formatted_expr = _format_between(
                        expr,
                        col_offset=extra_indent + len(op_padded) + len(KEYWORD_SUFFIX),
                    )
                    lines.append(f"{op_prefix}{formatted_expr}")
                else:
                    expanded = _expand_subqueries_in_expr(expr, len(op_prefix))
                    lines.append(f"{op_prefix}{expanded}")
        return "\n".join(lines)

    if kw in ('ORDER BY', 'GROUP BY'):
        return f"{prefix}{content}"

    if kw in ('UNION', 'UNION ALL', 'EXCEPT', 'EXCEPT ALL', 'INTERSECT', 'INTERSECT ALL'):
        return f"\n{ei}{padded_kw}\n"

    if kw == 'WITH':
        return f"{prefix}{content}"

    return f"{prefix}{content}"


def _extract_subquery_and_alias(content: str) -> Tuple[str, str]:
    i = 0
    # Find opening paren
    while i < len(content) and content[i] != '(':
        i += 1
    i += 1  
    depth = 1
    start = i
    while i < len(content) and depth > 0:
        if content[i] == '(':
            depth += 1
        elif content[i] == ')':
            depth -= 1
        i += 1
    inner = content[start:i - 1]
    rest = content[i:].strip()
    alias = ""
    if re.match(r'^AS\s+', rest, re.IGNORECASE):
        alias = rest[3:].strip()
    elif rest:
        alias = rest
    return inner, alias


def _format_select_statement(sql: str, extra_indent: int = 0, effective_river: int = None) -> str:
    er = effective_river if effective_river is not None else _effective_river(sql.strip())
    clauses = _split_into_clauses(sql.strip())
    lines: List[str] = []
    for clause in clauses:
        formatted = _format_clause(clause, extra_indent=extra_indent, effective_river=er)
        if formatted.strip():
            lines.append(formatted)
    return "\n".join(lines)

CTE_INDENT = 3


def _format_with_statement(sql: str) -> str:
    global_river = _effective_river(sql)
    ctes, remaining = _parse_ctes(sql)

    if not ctes:
        return _format_select_statement(sql, effective_river=global_river)

    cte_extra_indent = CTE_INDENT if global_river == RIVER else 0

    out_parts: List[str] = []
    for idx, cte in enumerate(ctes):
        body_formatted = _format_select_statement(
            cte.body_sql,
            extra_indent=cte_extra_indent,
            effective_river=global_river,
        )
        if idx == 0:
            header = f"WITH {cte.name} AS("
        else:
            header = f"{cte.name} AS("

        closing = ")," if idx < len(ctes) - 1 else ")"
        cte_block = f"{header}\n{body_formatted}\n{closing}"
        out_parts.append(cte_block)
        if idx < len(ctes) - 1:
            out_parts.append("")

    if remaining:
        out_parts.append("")
        main_formatted = _format_select_statement(remaining, effective_river=global_river)
        out_parts.append(main_formatted)

    return "\n".join(out_parts)


def _split_leading_comments(sql: str) -> Tuple[str, str]:
    i = 0
    prefix_end = 0
    while i < len(sql):
        # Skip blank/whitespace-only content
        while i < len(sql) and sql[i] in ' \t\r\n':
            i += 1
        if i >= len(sql):
            break
        # Consume a line comment
        if sql[i:i + 2] == '--':
            end = sql.find('\n', i)
            i = (end + 1) if end != -1 else len(sql)
            prefix_end = i
        else:
            break
    return sql[:prefix_end], sql[prefix_end:].lstrip()


def format_sql(sql: str) -> str:
    statements = sqlparse.split(sql)
    formatted: List[str] = []
    for raw in statements:
        raw = raw.strip()
        if not raw:
            continue

        raw = _uppercase_keywords(_strip_extra_whitespace(raw))
        raw = _strip_extra_whitespace(raw)

        comment_prefix, sql_body = _split_leading_comments(raw)

        if re.match(r'^WITH\b', sql_body, re.IGNORECASE):
            result = _format_with_statement(sql_body)
        else:
            result = _format_select_statement(sql_body)

        if comment_prefix.strip():
            result = comment_prefix.rstrip() + '\n' + result

        result = result.rstrip()
        if not result.endswith(';'):
            result += ';'
        formatted.append(result)

    return "\n\n".join(formatted)
