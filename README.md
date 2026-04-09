# SemiColon

## Philosophy

Most SQL formatters produce code that is syntactically correct but visually noisy.  
The *SemiColon Style* treats SQL as prose: it has a rhythm, a visible structure, and a
clear centre of gravity — the **River**.

The goal is not merely consistency; it is *readability at a glance*.

---

## The SemiColon Style — Rules

### 1. Keywords in UPPERCASE

All SQL keywords (`SELECT`, `FROM`, `WHERE`, `JOIN`, `AS`, …) are capitalised.
User identifiers and string literals are left exactly as written.

### 2. The River (Right-Alignment)

Every clause keyword is right-aligned so its **last character** sits at a fixed
column (the *river*).  This forms a clean right edge of keywords and a matching
left edge of code — the gap between them is the river.

```
ORDER BY  …   ← 8 chars, flush with river
   WHERE  …   ← 3 leading spaces
    FROM  …   ← 4 leading spaces
  SELECT  …   ← 2 leading spaces
```

The **'T'** in `SELECT` is directly above the **'M'** in `FROM`.

**Exception — compound JOIN keywords:**  
For `LEFT JOIN`, `INNER JOIN`, etc., the word `JOIN` aligns with the river and
the qualifier (`LEFT`, `INNER`, …) hangs naturally to the left:

```
LEFT JOIN  table_name
```

### 3. Double-Space Buffer

Every clause keyword is followed by **exactly two spaces** before the code begins.

```
    FROM  customers
```

**Exception:** the keyword `AS` is followed by **exactly one space**.

### 4. The AS Vertical Wall

Within a `SELECT` block, all `AS` keywords are vertically aligned.  
The formatter calculates the longest expression in the block and pads every
aliased expression to that length before placing `AS`.

```sql
  SELECT  id,
          customer_name     AS name,
          registration_date AS reg_date,
          status
```

### 5. Trailing Commas

The comma follows each column on the same line.  Subsequent columns are
indented to align with the first column.

```sql
  SELECT  id,
          name,
          email
```

### 6. Functions — No Space Before Parenthesis

```sql
COUNT(*)   -- correct
COUNT (*)  -- wrong
```

### 7. Operators — One Space Each Side

```sql
a = b        -- correct
a=b          -- wrong
a  =  b      -- wrong
```

### 8. CTE Structure

```sql
    WITH  cte_name AS (

       SELECT  col1,
               col2
         FROM  source_table

    ),

    other_cte AS (

       SELECT  col3
         FROM  other_table

    )
  SELECT  *
    FROM  cte_name
    JOIN  other_cte ON cte_name.id = other_cte.id
```

- The body opens on a new line after `WITH cte_name AS (`.
- One blank line after `(` and one blank line before `)`.
- Inner SQL is indented 3 spaces.
- The closing `),` is on its own line.
- One blank line between CTEs.

### 9. Subqueries

Subqueries use the River style with one blank line after the opening `(` and
one blank line before the closing `)`:

```sql
    FROM  (

            SELECT  *
              FROM  large_table
             WHERE  active = TRUE

          ) AS sub
```

### 10. BETWEEN … AND Alignment

The `'N'` of `BETWEEN` aligns vertically with the `'D'` of `AND`:

```sql
   WHERE  created_at BETWEEN '2024-01-01'
                         AND '2024-12-31'
```

---

## Installation

### From PyPI (once published)

```bash
pip install semicolon
```

### From source

```bash
git clone https://github.com/mustafaa7med/semicolon.git
cd semicolon
pip install -e .
```

### Verify

```bash
semicolon --version
```

---

## Usage

### Format a single file

```bash
semicolon query.sql
```

The file is formatted in-place.

### Format all `.sql` files in the current directory

```bash
semicolon .
```

### CI/CD check mode

```bash
semicolon query.sql --check   # exits 1 if formatting is needed
semicolon . --check           # check all .sql files
```

No files are written in `--check` mode — it is safe to use in pipelines.

---

## Before & After

### Before (messy, unformatted)

```sql
with
active_users as (
select u.id, u.name as user_name, u.email as user_email, u.created_at from users u where u.active = true and u.deleted_at is null
),
recent_orders as (
select o.user_id, count(*) as order_count, sum(o.total) as total_spent from orders o where o.created_at between '2024-01-01' and '2024-12-31' group by o.user_id
)
select au.user_name, au.user_email, ro.order_count, ro.total_spent from active_users au left join recent_orders ro on au.id = ro.user_id where ro.total_spent > 500 order by ro.total_spent desc limit 100;
```

### After (Alfie Style)

```sql
    WITH  active_users AS (

     SELECT  u.id,
             u.name  AS user_name,
             u.email AS user_email,
             u.created_at
       FROM  users u
      WHERE  u.active = TRUE
        AND  u.deleted_at IS NULL

),

          recent_orders AS (

     SELECT  o.user_id,
             COUNT(*)     AS order_count,
             SUM(o.total) AS total_spent
       FROM  orders o
      WHERE  o.created_at BETWEEN '2024-01-01'
                              AND '2024-12-31'
   GROUP BY  o.user_id

)
  SELECT  au.user_name,
          au.user_email,
          ro.order_count,
          ro.total_spent
    FROM  active_users au
LEFT JOIN  recent_orders ro
      ON  au.id = ro.user_id
   WHERE  ro.total_spent > 500
ORDER BY  ro.total_spent DESC
   LIMIT  100;
```

---

## Pre-commit Integration

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/mustafaa7med/semicolon
    rev: v0.1.0
    hooks:
      - id: semicolon
        args: [--check]
```

---

## License

Apache — see [LICENSE](LICENSE).

---

*Designed by Mostafa Ahmed (Alfie)*
