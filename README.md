# SemiColon

## Philosophy
Most SQL formatters produce code that is syntactically correct but visually noisy.  
The *SemiColon Style* treats SQL as prose: it has a rhythm, a visible structure, and a
clear centre of gravity — the **River**.

The goal is not merely consistency; it is *readability at a glance*.
---
## Installation

### From PyPI

```bash
pip install semicolonfmt
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
### After
```sql
WITH active_users AS(
    SELECT  u.id,
            u.name  AS user_name,
            u.email AS user_email,
            u.created_at
      FROM  users u
     WHERE  u.active = TRUE
       AND  u.deleted_at IS NULL
),

recent_orders AS(
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
    rev: v0.1.3
    hooks:
      - id: semicolon
        args: [--check]
```
---
## License
Apache — see [LICENSE](LICENSE).
---
*Designed by Mostafa Ahmed (Alfie)*
