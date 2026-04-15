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


class TestCommentPreservation:
    def test_line_comment_preserved(self):
        sql = "select id -- primary key\n, name from users"
        result = fmt(sql)
        assert "-- primary key" in result

    def test_block_comment_preserved(self):
        sql = "select /* all cols */ id, name from users"
        result = fmt(sql)
        assert "/* all cols */" in result
