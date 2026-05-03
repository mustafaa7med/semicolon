"""
Tests for the SemiColon Style SQL formatter.
Each test validates one or more of the documented formatting rules.
"""

import pytest
from semicolon.formatter import format_sql


def fmt(sql: str) -> str:
    return format_sql(sql).rstrip()


def lines(sql: str) -> list[str]:
    return fmt(sql).splitlines()


class TestKeywordUppercase:
    def test_select_from_where_uppercased(self):
        result = fmt("select id from users where active = true")
        assert "SELECT" in result
        assert "FROM" in result
        assert "WHERE" in result
        assert "TRUE" in result

    def test_order_by_desc_uppercased(self):
        result = fmt("select id from t order by id desc")
        assert "ORDER BY" in result
        assert "DESC" in result

    def test_aggregate_functions_uppercased(self):
        result = fmt("select count(*), sum(amount) from orders")
        assert "COUNT(*)" in result
        assert "SUM(amount)" in result

    def test_string_literals_preserved(self):
        result = fmt("select id from t where status = 'active'")
        assert "'active'" in result  # lowercase preserved inside string

    def test_is_null_uppercased(self):
        result = fmt("select a from t where b is null")
        assert "IS NULL" in result


class TestRiverAlignment:
    def test_select_from_alignment(self):
        result = fmt("select a from t")
        ls = result.splitlines()
        assert ls[0].startswith("  SELECT  ")
        assert ls[1].startswith("    FROM  ")

    def test_m_below_t(self):
        result = fmt("select a from t")
        sel_line, from_line = result.splitlines()[0], result.splitlines()[1]
        t_col = sel_line.index("SELECT") + len("SELECT") - 1  
        m_col = from_line.index("FROM") + len("FROM") - 1     
        assert t_col == m_col

    def test_order_by_at_river(self):
        result = fmt("select a from t order by a")
        order_line = [l for l in result.splitlines() if "ORDER BY" in l][0]
        assert order_line.startswith("ORDER BY  ")

    def test_group_by_at_river(self):
        result = fmt("select a, count(*) from t group by a")
        group_line = [l for l in result.splitlines() if "GROUP BY" in l][0]
        assert group_line.startswith("GROUP BY  ")

    def test_where_alignment(self):
        result = fmt("select a from t where a = 1")
        where_line = [l for l in result.splitlines() if "WHERE" in l][0]
        assert where_line.startswith("   WHERE  ")

    def test_left_join_dynamic_river(self):
        result = fmt("select a from t left join u on t.id = u.id")
        ls = result.splitlines()
        join_line = [l for l in ls if "LEFT JOIN" in l][0]
        on_line = [l for l in ls if l.strip().startswith("ON")][0]
        assert join_line.startswith(" LEFT JOIN  ")
        n_join = join_line.index("LEFT JOIN") + len("LEFT JOIN") - 1
        n_on = on_line.index("ON") + len("ON") - 1
        assert n_join == n_on

    def test_full_outer_join_dynamic_river(self):
        result = fmt("select a from t full outer join u on t.id = u.id")
        ls = result.splitlines()
        join_line = [l for l in ls if "FULL OUTER JOIN" in l][0]
        on_line = [l for l in ls if l.strip().startswith("ON")][0]
        n_join = join_line.index("FULL OUTER JOIN") + len("FULL OUTER JOIN") - 1
        n_on = on_line.index("ON") + len("ON") - 1
        assert n_join == n_on

    def test_on_alignment_plain_join(self):
        result = fmt("select a from t join u on t.id = u.id")
        ls = result.splitlines()
        join_line = [l for l in ls if l.strip().startswith("JOIN")][0]
        on_line = [l for l in ls if l.strip().startswith("ON")][0]
        n_join = join_line.index("JOIN") + len("JOIN") - 1
        n_on = on_line.index("ON") + len("ON") - 1
        assert n_join == n_on


class TestASWallAndLeadingCommas:
    def test_trailing_commas(self):
        result = fmt("select a, b, c from t")
        ls = result.splitlines()
        select_block = [l for l in ls if "SELECT" in l or (ls.index(l) > 0 and "FROM" not in l and l.strip())]

        assert ls[0].rstrip().endswith(",")

        assert ls[1].rstrip().endswith(",")

        from_idx = next(i for i, l in enumerate(ls) if "FROM" in l)
        assert not ls[from_idx - 1].rstrip().endswith(",")

    def test_as_vertical_wall(self):
        # All AS keywords in a SELECT block must be at the same column.
        result = fmt("select id, name as customer_name, email as customer_email from t")
        as_cols = [line.index(" AS ") for line in result.splitlines() if " AS " in line]
        # All AS positions should be identical
        if as_cols:
            assert len(set(as_cols)) == 1, f"AS not aligned: cols={as_cols}"

    def test_no_alias_cols_unaffected(self):
        result = fmt("select id, name as n from t")
        # 'id' has no alias — should appear as-is on the SELECT line
        select_line = result.splitlines()[0]
        assert "id" in select_line

    def test_subsequent_cols_aligned_with_first(self):
        """Columns 2..N must be indented to align with the first column."""
        result = fmt("select alpha, beta, gamma from t")
        ls = result.splitlines()
        first_col_start = ls[0].index("alpha")
        for line in ls[1:]:
            if "FROM" in line:
                break
            # The second+ columns start at the same position as the first
            col_start = len(line) - len(line.lstrip())
            assert col_start == first_col_start, (
                f"Col misaligned: expected indent {first_col_start}, got {col_start}: {line!r}"
            )


class TestFunctionFormatting:
    def test_no_space_before_paren(self):
        result = fmt("select count (*) from t")
        assert "COUNT(*)" in result

    def test_nested_function(self):
        result = fmt("select coalesce (a, 0) from t")
        assert "COALESCE(a," in result or "COALESCE(a, 0)" in result


class TestBetweenAnd:
    def test_between_and_split(self):
        result = fmt("select id from t where d between '2024-01-01' and '2024-12-31'")
        ls = result.splitlines()
        # Should have BETWEEN on one line and AND on the next
        between_line = [l for l in ls if "BETWEEN" in l]
        and_line = [l for l in ls if l.strip().upper().startswith("AND")]
        assert between_line, "BETWEEN not found"
        assert and_line, "AND continuation not found"

    def test_n_d_vertical_alignment(self):
        """'N' of BETWEEN must align vertically with 'D' of AND."""
        result = fmt("select id from t where x between 1 and 100")
        ls = result.splitlines()
        between_line = next(l for l in ls if "BETWEEN" in l)
        # The AND that continues BETWEEN is on a new line and starts with 'AND'
        and_line = next(
            l for l in ls
            if l.strip().startswith("AND") and "BETWEEN" not in l
        )
        n_pos = between_line.index("BETWEEN") + len("BETWEEN") - 1
        d_pos = and_line.index("AND") + len("AND") - 1
        assert n_pos == d_pos, (
            f"'N' of BETWEEN at col {n_pos}, 'D' of AND at col {d_pos}"
        )


class TestCTEFormatting:
    def test_cte_with_keyword_present(self):
        result = fmt("with cte as (select 1 as n) select n from cte")
        assert "WITH" in result
        assert "cte AS(" in result

    def test_cte_header_no_space_before_paren(self):
        result = fmt("with cte as (select 1 as n) select n from cte")
        assert "AS(" in result
        assert "AS (" not in result

    def test_with_starts_at_column_zero(self):
        result = fmt("with cte as (select 1 as n) select n from cte")
        first_line = result.splitlines()[0]
        assert first_line.startswith("WITH")

    def test_cte_body_indented(self):
        result = fmt("with cte as (select 1 as n) select n from cte")
        ls = result.splitlines()
        in_body = False
        for line in ls:
            if "AS(" in line:
                in_body = True
                continue
            if in_body and line.strip() in (")", "),"):
                break
            if in_body and line.strip():
                assert line.startswith("   "), f"CTE body not indented: {line!r}"

    def test_cte_no_blank_line_after_open_paren(self):
        result = fmt("with cte as (select a from t) select a from cte")
        ls = result.splitlines()
        open_idx = next(i for i, l in enumerate(ls) if "AS(" in l)
        assert ls[open_idx + 1].strip() != "", "Expected no blank line after CTE '('"

    def test_multiple_ctes_no_double_comma(self):
        result = fmt(
            "with a as (select 1 as x), b as (select 2 as y) select * from a join b on a.x = b.y"
        )
        assert "),\n, " not in result
        assert result.count("AS(") == 2

    def test_subsequent_cte_at_column_zero(self):
        result = fmt(
            "with a as (select 1 as x), b as (select 2 as y) select * from a"
        )
        ls = result.splitlines()
        second_cte_line = next(l for l in ls if "b AS(" in l)
        assert second_cte_line.startswith("b AS(")

    def test_closing_paren_comma_own_line(self):
        result = fmt(
            "with a as (select 1 as x), b as (select 2 as y) select * from a"
        )
        assert any(l.strip() == ")," for l in result.splitlines())

    def test_with_single_space_after_keyword(self):
        result = fmt("with cte as (select 1 as n) select n from cte")
        first_line = result.splitlines()[0]
        assert first_line.startswith("WITH ")
        assert not first_line.startswith("WITH  ")

    def test_global_river_applied_to_cte_bodies(self):
        sql = (
            "with a as (select id from t), b as (select name from s) "
            "select a.id, b.name from a full outer join b on a.id = b.id"
        )
        result = fmt(sql)
        ls = result.splitlines()
        join_line = next(l for l in ls if "FULL OUTER JOIN" in l)
        n_col = join_line.index("FULL OUTER JOIN") + len("FULL OUTER JOIN") - 1
        cte_select_lines = [l for l in ls if l.lstrip().startswith("SELECT") and "WITH" not in l]
        cte_from_lines = [l for l in ls if l.lstrip().startswith("FROM")]
        for line in cte_select_lines + cte_from_lines:
            kw = line.lstrip().split()[0]
            kw_end = len(line) - len(line.lstrip()) + len(kw) - 1
            assert kw_end == n_col, f"CTE body line not at global river: {line!r}"


class TestOperatorSpacing:
    def test_gt_no_spaces(self):
        result = fmt("select id from t where salary>300")
        assert "salary > 300" in result

    def test_lt_no_spaces(self):
        result = fmt("select id from t where score<18")
        assert "score < 18" in result

    def test_eq_no_spaces(self):
        result = fmt("select id from t where status=1")
        assert "status = 1" in result

    def test_gte_no_spaces(self):
        result = fmt("select id from t where score>=90")
        assert "score >= 90" in result

    def test_lte_no_spaces(self):
        result = fmt("select id from t where price<=100")
        assert "price <= 100" in result

    def test_neq_bang_no_spaces(self):
        result = fmt("select id from t where status!=0")
        assert "status != 0" in result

    def test_neq_diamond_no_spaces(self):
        result = fmt("select id from t where category<>'admin'")
        assert "category <> 'admin'" in result

    def test_multiple_operators_in_where(self):
        result = fmt("select id from t where score>=18 and salary>300")
        assert "score >= 18" in result
        assert "salary > 300" in result

    def test_already_spaced_is_idempotent(self):
        result = fmt("select id from t where salary > 300")
        assert "salary > 300" in result
        assert "salary  > 300" not in result

    def test_on_clause_operator_spaced(self):
        result = fmt("select a from t join u on t.id=u.id")
        assert "t.id = u.id" in result


class TestIdempotency:
    def test_simple_select_idempotent(self):
        sql = "select id, name from users where active = true"
        once = fmt(sql)
        twice = fmt(once)
        assert once == twice

    def test_cte_idempotent(self):
        sql = (
            "with cte as (select id, name as n from users where active = true) "
            "select n from cte order by n"
        )
        once = fmt(sql)
        twice = fmt(once)
        assert once == twice

    def test_join_idempotent(self):
        sql = "select a.id, b.name from a left join b on a.id = b.a_id where a.x = 1"
        once = fmt(sql)
        twice = fmt(once)
        assert once == twice


class TestSubqueryFormatting:
    def test_scalar_subquery_in_select_expands(self):
        sql = "select name, (select count(*) from tasks where assigned_to = e.id) as cnt from employees e"
        result = fmt(sql)
        # Subquery should be multi-line
        assert "(SELECT  COUNT(*)" in result
        assert "FROM  tasks" in result
        assert "WHERE  assigned_to = e.id" in result

    def test_scalar_subquery_closing_paren_on_own_line(self):
        sql = "select (select count(*) from t) as n from s"
        result = fmt(sql)
        ls = result.splitlines()
        # There must be a line that is just indented ')' (possibly with AS alias)
        assert any(l.strip().startswith(")") for l in ls)

    def test_scalar_subquery_alias_after_closing_paren(self):
        sql = "select (select count(*) from t) as total from s"
        result = fmt(sql)
        # ') AS total' must be on the closing paren line
        paren_line = next(l for l in result.splitlines() if l.strip().startswith(")"))
        assert "AS total" in paren_line

    def test_scalar_subquery_river_alignment(self):
        """Keywords inside the subquery must be right-aligned to the same river column."""
        sql = "select (select id from t where x = 1) as v from s"
        result = fmt(sql)
        ls = result.splitlines()
        # The subquery SELECT is on a line containing '(SELECT'
        select_line = next(l for l in ls if "(SELECT" in l)
        from_line   = next(l for l in ls if l.strip().startswith("FROM") and "FROM  s" not in l)
        where_line  = next(l for l in ls if l.strip().startswith("WHERE"))
        # Right-edge of SELECT inside (SELECT, FROM, WHERE must all align
        sub_select_col = select_line.index("(SELECT") + len("(SELECT") - 1
        from_col  = from_line.index("FROM") + len("FROM") - 1
        where_col = where_line.index("WHERE") + len("WHERE") - 1
        assert sub_select_col == from_col == where_col

    def test_where_in_subquery_expands(self):
        sql = "select id from employees where department_id in (select id from departments where active = true)"
        result = fmt(sql)
        assert "IN (SELECT" in result
        assert "FROM  departments" in result
        assert "WHERE  active = TRUE" in result

    def test_exists_subquery_expands(self):
        sql = "select id from orders where exists (select 1 from payments where payments.order_id = orders.id)"
        result = fmt(sql)
        assert "EXISTS (SELECT" in result
        assert "FROM  payments" in result

    def test_where_in_subquery_with_and_conjunct(self):
        sql = "select id from t where id in (select id from s) and status = 1"
        result = fmt(sql)
        ls = result.splitlines()
        and_line = next(l for l in ls if l.strip().startswith("AND"))
        assert "status = 1" in and_line

    def test_subquery_column_does_not_affect_as_wall(self):
        """A subquery column should not inflate the AS-wall for regular columns."""
        sql = "select id as user_id, (select count(*) from t) as cnt from s"
        result = fmt(sql)
        # Regular column AS wall should align id's AS
        id_line = next(l for l in result.splitlines() if "user_id" in l)
        cnt_line = next(l for l in result.splitlines() if ") AS cnt" in l)
        # id AS should appear on the id line; ) AS cnt on its own line
        assert "AS user_id" in id_line
        assert cnt_line.strip().startswith(") AS cnt")

    def test_subquery_idempotent(self):
        sql = "select name, (select count(*) from tasks where assigned_to = e.id) as cnt from employees e"
        once = fmt(sql)
        twice = fmt(once)
        assert once == twice

    def test_implicit_alias_subquery_expands(self):
        """(SELECT ...) alias (no AS keyword) should expand and keep alias without AS."""
        sql = "select name, (select count(*) from tasks where assigned_to = e.id) cnt from employees e"
        result = fmt(sql)
        ls = result.splitlines()
        # Subquery must be multi-line
        assert any("(SELECT" in l for l in ls)
        # Closing paren line should have the alias WITHOUT AS
        paren_line = next(l for l in ls if l.strip().startswith(")"))
        assert "cnt" in paren_line
        assert "AS cnt" not in paren_line

    def test_implicit_alias_subquery_idempotent(self):
        sql = "select name, (select count(*) from tasks where assigned_to = e.id) cnt from employees e"
        once = fmt(sql)
        twice = fmt(once)
        assert once == twice

    def test_from_subquery_expands(self):
        """FROM (SELECT ...) AS t should be expanded to multi-line."""
        sql = "select u.id from (select id from users where active = true) as active_users"
        result = fmt(sql)
        ls = result.splitlines()
        # The subquery should not be on the same line as FROM
        from_line = next(l for l in ls if l.strip().startswith("FROM") and "active_users" not in l.strip()[5:])
        assert "(SELECT" not in from_line

    def test_join_subquery_expands(self):
        """LEFT JOIN (SELECT ...) AS t should be expanded to multi-line."""
        sql = "select u.id from users u left join (select user_id, max(ts) last_ts from logins group by user_id) l on l.user_id = u.id"
        result = fmt(sql)
        ls = result.splitlines()
        join_line = next(l for l in ls if "LEFT JOIN" in l)
        # The subquery content should not be inline on the JOIN line
        assert "SELECT" not in join_line

    def test_keyword_space_before_in_paren(self):
        """IN (SELECT ...) must keep the space — not become IN(SELECT."""
        sql = "select id from t where id in (select id from s)"
        result = fmt(sql)
        assert "IN (SELECT" in result
        assert "IN(SELECT" not in result

    def test_keyword_space_before_exists_paren(self):
        """EXISTS (SELECT ...) must keep the space — not become EXISTS(SELECT."""
        sql = "select id from t where exists (select 1 from s where s.id = t.id)"
        result = fmt(sql)
        assert "EXISTS (SELECT" in result
        assert "EXISTS(SELECT" not in result

    def test_leading_comment_with_cte_formats_body(self):
        """A leading -- comment before WITH must not prevent CTE body formatting."""
        sql = "-- report query\nwith cte as (select id, name from users where active = true) select id from cte"
        result = fmt(sql)
        ls = result.splitlines()
        # Comment is preserved on the first line
        assert ls[0].strip().startswith("--")
        # CTE body must be formatted (multi-line), not inline
        cte_header_idx = next(i for i, l in enumerate(ls) if "AS(" in l)
        body_lines = [l for l in ls[cte_header_idx + 1:] if l.strip() and l.strip() not in (")", "),")]
        assert len(body_lines) >= 2, "CTE body should be multi-line"


class TestCaseWhenFormatting:
    def test_when_conditions_on_separate_lines(self):
        """First WHEN is on the CASE line; subsequent WHENs each get their own line."""
        sql = "select CASE WHEN price < 20 THEN 'Low' WHEN price > 50 THEN 'High' ELSE 'Mid' END from t"
        result = fmt(sql)
        ls = result.splitlines()
        # First WHEN is on the CASE line; second WHEN is on its own indented line
        case_line = next(l for l in ls if "CASE WHEN" in l)
        assert "CASE WHEN" in case_line
        second_when_lines = [l for l in ls if l.lstrip().startswith("WHEN")]
        assert len(second_when_lines) == 1, "Second WHEN should be on its own line"

    def test_when_conditions_vertically_aligned(self):
        sql = "select CASE WHEN price < 20 THEN 'Low' WHEN price > 50 THEN 'High' END from t"
        result = fmt(sql)
        ls = result.splitlines()
        when_lines = [l for l in ls if "WHEN" in l]
        when_cols = [l.index("WHEN") for l in when_lines]
        assert len(set(when_cols)) == 1, f"WHEN keywords not aligned: cols={when_cols}"

    def test_then_keywords_vertically_aligned(self):
        sql = "select CASE WHEN price < 20 THEN 'Low' WHEN price BETWEEN 20 AND 50 THEN 'Medium' ELSE 'High' END from t"
        result = fmt(sql)
        ls = result.splitlines()
        then_lines = [l for l in ls if " THEN " in l]
        then_cols = [l.index(" THEN ") for l in then_lines]
        assert len(set(then_cols)) == 1, f"THEN keywords not aligned: cols={then_cols}"

    def test_else_aligns_with_when(self):
        sql = "select CASE WHEN x = 1 THEN 'a' ELSE 'b' END from t"
        result = fmt(sql)
        ls = result.splitlines()
        when_line = next(l for l in ls if "WHEN" in l)
        else_line = next(l for l in ls if l.lstrip().startswith("ELSE"))
        assert when_line.index("WHEN") == else_line.index("ELSE"), "ELSE should align with WHEN"

    def test_end_d_below_case_e(self):
        """'D' of END must sit directly below 'E' of CASE."""
        sql = "select CASE WHEN x = 1 THEN 'a' ELSE 'b' END from t"
        result = fmt(sql)
        ls = result.splitlines()
        case_line = next(l for l in ls if "CASE" in l)
        end_line = next(l for l in ls if l.lstrip().startswith("END"))
        e_of_case = case_line.index("CASE") + len("CASE") - 1  # col of 'E'
        d_of_end = end_line.index("END") + len("END") - 1      # col of 'D'
        assert e_of_case == d_of_end, f"'E' of CASE at col {e_of_case}, 'D' of END at col {d_of_end}"

    def test_case_alias_on_end_line(self):
        sql = "select CASE WHEN x = 1 THEN 'a' ELSE 'b' END AS label from t"
        result = fmt(sql)
        end_line = next(l for l in result.splitlines() if l.lstrip().startswith("END"))
        assert "AS label" in end_line

    def test_case_without_else(self):
        sql = "select CASE WHEN x = 1 THEN 'a' WHEN x = 2 THEN 'b' END from t"
        result = fmt(sql)
        assert "ELSE" not in result
        end_line = next(l for l in result.splitlines() if l.lstrip().startswith("END"))
        assert end_line is not None

    def test_between_in_case_condition_treated_as_single_condition(self):
        """BETWEEN...AND inside a WHEN condition must not split the condition."""
        sql = "select CASE WHEN price BETWEEN 20 AND 50 THEN 'Mid' ELSE 'Other' END from t"
        result = fmt(sql)
        when_lines = [l for l in result.splitlines() if "WHEN" in l]
        assert len(when_lines) == 1, "BETWEEN...AND in WHEN should not split into two WHEN lines"
        assert "BETWEEN 20" in when_lines[0] and "AND 50" in when_lines[0]

    def test_case_not_in_as_wall(self):
        """A CASE column should not inflate the AS wall for regular columns."""
        sql = "select id as user_id, CASE WHEN x = 1 THEN 'a' END AS label from t"
        result = fmt(sql)
        id_line = next(l for l in result.splitlines() if "user_id" in l)
        assert "AS user_id" in id_line
        # The AS for id should be right after id with only expression-length padding
        # (not inflated by the length of the CASE expression)
        as_pos = id_line.index(" AS user_id")
        assert as_pos < 30, f"AS wall inflated by CASE expr: position {as_pos}"

    def test_case_idempotent(self):
        sql = "select name, CASE WHEN price < 20 THEN 'Low' WHEN price BETWEEN 20 AND 50 THEN 'Medium' ELSE 'High' END AS category from products"
        once = fmt(sql)
        twice = fmt(once)
        assert once == twice

    def test_case_as_first_column(self):
        sql = "select CASE WHEN x = 1 THEN 'a' ELSE 'b' END AS v from t"
        result = fmt(sql)
        first_line = result.splitlines()[0]
        assert "CASE WHEN" in first_line

    def test_case_as_non_first_column_indented(self):
        """CASE as a non-first column must be indented to align with the first column."""
        sql = "select id, CASE WHEN x = 1 THEN 'a' ELSE 'b' END AS v from t"
        result = fmt(sql)
        ls = result.splitlines()
        first_col_start = ls[0].index("id")
        case_line = next(l for l in ls if "CASE WHEN" in l)
        case_col_start = case_line.index("CASE")
        assert case_col_start == first_col_start, (
            f"CASE not aligned with first column: expected col {first_col_start}, got {case_col_start}"
        )


class TestCommentPreservation:
    def test_line_comment_preserved(self):
        sql = "select id -- primary key\n, name from users"
        result = fmt(sql)
        assert "-- primary key" in result

    def test_block_comment_preserved(self):
        sql = "select /* all cols */ id, name from users"
        result = fmt(sql)
        assert "/* all cols */" in result
