RIVER: int = 8

CLAUSE_KEYWORDS = [
    "FULL OUTER JOIN",
    "LEFT OUTER JOIN",
    "RIGHT OUTER JOIN",
    "CROSS JOIN",
    "INNER JOIN",
    "LEFT JOIN",
    "RIGHT JOIN",
    "FULL JOIN",
    "INSERT INTO",
    "UNION ALL",
    "EXCEPT ALL",
    "INTERSECT ALL",
    "ORDER BY",
    "GROUP BY",
    "SELECT",
    "DISTINCT",
    "FROM",
    "WHERE",
    "JOIN",
    "ON",
    "HAVING",
    "UNION",
    "EXCEPT",
    "INTERSECT",
    "LIMIT",
    "OFFSET",
    "WITH",
    "UPDATE",
    "DELETE",
    "INSERT",
    "SET",
    "VALUES",
    "RETURNING",
    "INTO",
    "AND",
    "OR",
    "BETWEEN",
    "CASE",
    "WHEN",
    "THEN",
    "ELSE",
    "END",
]

NEWLINE_STARTERS = {
    "SELECT", "DISTINCT", "FROM", "WHERE",
    "JOIN", "ON", "HAVING",
    "ORDER BY", "GROUP BY",
    "UNION", "UNION ALL", "EXCEPT", "EXCEPT ALL", "INTERSECT", "INTERSECT ALL",
    "LIMIT", "OFFSET",
    "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "CROSS JOIN",
    "LEFT OUTER JOIN", "RIGHT OUTER JOIN", "FULL OUTER JOIN", "FULL JOIN",
    "INSERT INTO", "UPDATE", "DELETE", "SET", "VALUES", "RETURNING", "WITH",
}

CONJUNCT_KEYWORDS = {"AND", "OR"}


def pad_keyword(kw: str, river: int = RIVER) -> str:
    if len(kw) <= river:
        return kw.rjust(river)
    return kw


# Pre-built padding table.
PADDED: dict[str, str] = {kw: pad_keyword(kw) for kw in CLAUSE_KEYWORDS}

KEYWORD_SUFFIX = "  "
AS_SUFFIX = " "

SQL_KEYWORDS = {
    "SELECT", "DISTINCT", "FROM", "WHERE", "JOIN", "ON", "HAVING",
    "ORDER", "GROUP", "BY", "UNION", "ALL", "EXCEPT", "INTERSECT",
    "LIMIT", "OFFSET", "WITH", "AS", "CASE", "WHEN", "THEN", "ELSE", "END",
    "AND", "OR", "NOT", "IN", "LIKE", "ILIKE", "BETWEEN", "IS", "NULL",
    "TRUE", "FALSE", "EXISTS", "ANY", "SOME", "ALL",
    "LEFT", "RIGHT", "INNER", "OUTER", "CROSS", "FULL", "NATURAL",
    "INSERT", "INTO", "UPDATE", "DELETE", "SET", "VALUES", "RETURNING",
    "CREATE", "DROP", "ALTER", "TABLE", "VIEW", "INDEX", "SCHEMA",
    "PRIMARY", "KEY", "FOREIGN", "REFERENCES", "UNIQUE", "CHECK",
    "DEFAULT", "NOT", "NULL", "CONSTRAINT",
    "ASC", "DESC", "NULLS", "FIRST", "LAST",
    "OVER", "PARTITION", "ROWS", "RANGE", "UNBOUNDED", "PRECEDING",
    "FOLLOWING", "CURRENT", "ROW",
    "CAST", "EXTRACT", "FILTER", "WITHIN", "INTERVAL",
    "COALESCE", "NULLIF", "GREATEST", "LEAST",
    "LATERAL", "RECURSIVE",
    "WINDOW",
    "FETCH", "NEXT", "ONLY", "TIES",
    "ROLLUP", "CUBE", "GROUPING", "SETS",
    "COUNT", "SUM", "AVG", "MIN", "MAX", "ARRAY_AGG", "STRING_AGG",
    "JSON_AGG", "JSONB_AGG", "BOOL_AND", "BOOL_OR", "EVERY",
    "RANK", "DENSE_RANK", "ROW_NUMBER", "NTILE", "LAG", "LEAD",
    "FIRST_VALUE", "LAST_VALUE", "NTH_VALUE", "PERCENT_RANK", "CUME_DIST",
    "LOWER", "UPPER", "TRIM", "LTRIM", "RTRIM", "LENGTH", "SUBSTR",
    "SUBSTRING", "POSITION", "REPLACE", "SPLIT_PART", "CONCAT",
    "TO_CHAR", "TO_DATE", "TO_TIMESTAMP", "TO_NUMBER",
    "NOW", "CURRENT_DATE", "CURRENT_TIME", "CURRENT_TIMESTAMP",
    "DATE_PART", "DATE_TRUNC", "AGE", "EXTRACT",
    "ROUND", "FLOOR", "CEIL", "CEILING", "ABS", "MOD", "POWER", "SQRT",
    "GENERATE_SERIES", "UNNEST", "ARRAY", "ROW",
}
