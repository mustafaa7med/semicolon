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

    # Operators that get exactly one space on each side
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
    # Collapse runs of whitespace (outside strings/comments) to single spaces.
    # sqlparse's format with strip_whitespace=True handles this safely.
    return sqlparse.format(sql, strip_whitespace=True)

@dataclass
class Clause:
    keyword: str          # e.g. "SELECT", "LEFT JOIN", "ORDER BY"
    content: str          # raw content after the keyword (stripped)


def _split_into_clauses(sql: str) -> List[Clause]:
    """
    Split *sql* into Clause objects at top-level keyword boundaries.

    Parentheses depth is tracked so that keywords inside sub-queries or
    CTEs are NOT treated as clause boundaries.

    Build a pattern that matches clause-starting keywords at word boundaries.
    Longer keywords first to avoid partial matches.
    """
    starters = sorted(NEWLINE_STARTERS, key=len, reverse=True)
    pat = re.compile(
        r'\b(' + '|'.join(re.escape(s) for s in starters) + r')\b',
        re.IGNORECASE,
    )

    # Walk token by token to honour nesting depth.
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


def _split_columns(content: str) -> List[Column]:
    """
    Split a comma-separated column list into Column objects.

    Respects parentheses so that function calls like
    ``COALESCE(a, b)`` are not split.
    """
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
    """Parse a single column expression (possibly with AS alias).
       Match trailing AS alias – be careful of CASE ... END AS alias
       We look for a top-level AS token.
    """
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
        return Column(expression=expr, alias=alias)
    # No AS: try implicit alias (last bare identifier after whitespace)
    return Column(expression=raw.strip())


def _format_select_columns(cols: List[Column], indent: str) -> str:
    """
    Format a SELECT column list with:
      • Trailing commas — comma immediately after each column except the last.
      • Subsequent columns indented to align with the first column.
      • AS vertical wall (all AS keywords at the same column).
      • Single space after AS.

    *indent* is the string that precedes the first column on its line
    (everything after "SELECT  ").
    """
    if not cols:
        return ""

    # Normalise each expression (remove space before '(', etc.)
    normed = [
        Column(
            expression=_FUNC_SPACE_RE.sub(r'\1(', c.expression),
            alias=c.alias,
        )
        for c in cols
    ]

    # Compute AS wall: max expression length among columns that have an alias.
    aliased = [c for c in normed if c.alias]
    as_col = max((len(c.expression) for c in aliased), default=0)

    # Indent for columns 2..N — align with the first column character.
    col_indent = " " * len(indent)

    lines: List[str] = []
    for i, col in enumerate(normed):
        if col.alias:
            expr_padded = col.expression.ljust(as_col)
            col_str = f"{expr_padded} AS {col.alias}"
        else:
            col_str = col.expression

        is_last = i == len(normed) - 1
        suffix = "" if is_last else ","

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
    """
    Split a WHERE/HAVING expression on top-level AND/OR while keeping
    BETWEEN...AND intact.
    """
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
    """
    Robust version: walk char-by-char to split on top-level AND/OR.
    """
    # Tokenise the content preserving original spacing.
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
    # Remove leading WITH keyword
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


def _normalize_expression(expr: str) -> str:
    result = _FUNC_SPACE_RE.sub(r'\1(', expr)
    return result


def _normalize_operators(expr: str) -> str:
    # Ensure exactly one space on each side of comparison operators.
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
        elif depth == 0 and _is_keyword_token(tok.ttype) and tok.value.upper() == 'SELECT':
            return True
    return False

def _format_clause(clause: Clause, extra_indent: int = 0) -> str:
    kw = clause.keyword
    content = clause.content
    padded_kw = pad_keyword(kw)
    ei = " " * extra_indent

    if not kw:
        return ei + content

    prefix = f"{ei}{padded_kw}{KEYWORD_SUFFIX}"  # e.g. "  SELECT  "

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
            sub_fmt = _format_subquery(inner, extra_indent=extra_indent + RIVER + 2)
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
            op = c.operator  # "", "AND", or "OR"
            expr = _normalize_expression(c.expression)
            if op == "":
                # Check for BETWEEN
                if re.search(r'\bBETWEEN\b', expr, re.IGNORECASE):
                    formatted_expr = _format_between(
                        expr,
                        col_offset=extra_indent + len(padded_kw) + len(KEYWORD_SUFFIX),
                    )
                    lines.append(f"{prefix}{formatted_expr}")
                else:
                    lines.append(f"{prefix}{expr}")
            else:
                op_padded = pad_keyword(op)
                op_prefix = f"{ei}{op_padded}{KEYWORD_SUFFIX}"
                if re.search(r'\bBETWEEN\b', expr, re.IGNORECASE):
                    formatted_expr = _format_between(
                        expr,
                        col_offset=extra_indent + len(op_padded) + len(KEYWORD_SUFFIX),
                    )
                    lines.append(f"{op_prefix}{formatted_expr}")
                else:
                    lines.append(f"{op_prefix}{expr}")
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


def _format_select_statement(sql: str, extra_indent: int = 0) -> str:
    """Format a single SELECT (or INSERT/UPDATE/DELETE) statement."""
    clauses = _split_into_clauses(sql.strip())
    lines: List[str] = []
    for clause in clauses:
        formatted = _format_clause(clause, extra_indent=extra_indent)
        if formatted.strip():
            lines.append(formatted)
    return "\n".join(lines)

CTE_INDENT = 3  # spaces inside CTE body


def _format_with_statement(sql: str) -> str:
    ctes, remaining = _parse_ctes(sql)

    if not ctes:
        return _format_select_statement(sql)

    # The name column starts right after "    WITH  " = RIVER + KEYWORD_SUFFIX chars.
    name_col = RIVER + len(KEYWORD_SUFFIX)           # 10 chars
    name_indent = " " * name_col                     # indent for subsequent CTEs

    out_parts: List[str] = []
    for idx, cte in enumerate(ctes):
        body_formatted = _format_select_statement(
            cte.body_sql,
            extra_indent=CTE_INDENT,
        )
        if idx == 0:
            header = f"{pad_keyword('WITH')}{KEYWORD_SUFFIX}{cte.name} AS ("
        else:
            header = f"{name_indent}{cte.name} AS ("

        closing = ")," if idx < len(ctes) - 1 else ")"
        cte_block = f"{header}\n\n{body_formatted}\n\n{closing}"
        out_parts.append(cte_block)
        if idx < len(ctes) - 1:
            out_parts.append("")  

    if remaining:
        main_formatted = _format_select_statement(remaining)
        out_parts.append(main_formatted)

    return "\n".join(out_parts)


def format_sql(sql: str) -> str:
    """
    Format *sql* according to the SemiColon Style and return the result.

    Multiple statements (separated by ``;``) are formatted individually and
    joined with a blank line.
    """
    # Split on top-level semicolons (sqlparse handles this).
    statements = sqlparse.split(sql)
    formatted: List[str] = []
    for raw in statements:
        raw = raw.strip()
        if not raw:
            continue

        raw = _uppercase_keywords(_strip_extra_whitespace(raw))
        raw = _strip_extra_whitespace(raw)


        if re.match(r'^WITH\b', raw, re.IGNORECASE):
            result = _format_with_statement(raw)
        else:
            result = _format_select_statement(raw)

        result = result.rstrip()
        if not result.endswith(';'):
            result += ';'
        formatted.append(result)

    return "\n\n".join(formatted)
