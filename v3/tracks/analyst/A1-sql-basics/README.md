# A1 · SQL basics: asking questions of the sample data

**Time:** about 45 minutes · **Profile:** every profile (`core`, `engineer`, `full`) ·
**You need:** a lab login in the `analyst` group (or `engineer`/`lab-admin`)

## Goal

By the end you can answer a business question with SQL, and save the answer as a table
that other people (and tools such as Superset) can use.

The question for this module:

> **Which customer market segment spent the most in 1996, and how many orders was that?**

You will build the answer in small steps (`SELECT` → `WHERE` → `GROUP BY` → `JOIN`) and
save it as the table `a1_segment_revenue_1996` in your own schema.

## Concepts in two minutes

- **Trino** is the lab's shared SQL engine. You send it SQL; it reads the tables for you.
  Every query runs **as you**, so what you may read or write depends on your lab group.
- **A table name has three parts:** `catalog.schema.table`, for example
  `lakehouse.samples.orders`. `lakehouse` is the lab's data catalog, `samples` is a
  *schema* (a folder of tables), `orders` is the table.
- **The sample data** is a small copy of the TPC-H benchmark, a made-up wholesale business:
  `customer` places `orders`; each order has several `lineitem`s; customers live in a
  `nation`, and nations belong to a `region`. It is the same in every lab, so your numbers
  will match the ones shown here.
- **Your own schema** is `lakehouse.dbt_<your user name>` (for example `dbt_anna`). It is
  the one place an analyst can create tables. Everything else is read-only for you, so you
  cannot break the shared data. (The `dbt_` prefix is there because dbt, which you meet in
  A3, writes to the same schema.)

## Where to type SQL

You can do the whole module in either tool. Pick one; the checkpoint only looks at the
result table.

| | JupyterLab (every profile) | Superset SQL Lab (profile `full`) |
|---|---|---|
| Open | `jupyter.<your lab domain>` → `tracks/analyst/A1-sql-basics/a1_sql_basics.ipynb` | `superset.<your lab domain>` → **SQL** → **SQL Lab** |
| Connection | the notebook's first cell sets it up | database **Lakehouse (Trino)**, schema `samples` |
| Run | `Shift+Enter` in a `%%sql` cell | select the text, then **Run** (`Ctrl+Enter`) |
| Your schema | the notebook fills in `{{schema}}` for you | type `dbt_<you>` yourself (for example `dbt_anna`) |

The steps below show plain SQL. In the notebook every step is already a cell.

## Steps

### 1. Look before you ask (5 min)

Always look at a few rows first. It tells you the column names and what the values look
like, which saves you from guessing later.

```sql
SELECT *
FROM lakehouse.samples.customer
LIMIT 5
```

Expected: 5 rows with columns `custkey, name, address, nationkey, phone, acctbal,
mktsegment, comment`. `mktsegment` is the customer's market segment.

> **Why `LIMIT`?** Without it Trino returns every row. That is fine for 1,500 customers but
> not for a real table with billions of rows. Make `LIMIT` a habit while exploring.

### 2. Choose columns and filter rows: `SELECT` and `WHERE` (5 min)

```sql
SELECT name, mktsegment, acctbal
FROM lakehouse.samples.customer
WHERE mktsegment = 'BUILDING' AND acctbal > 9000
ORDER BY acctbal DESC
LIMIT 10
```

Expected: 10 customers from the `BUILDING` segment, richest first, all with
`acctbal` above 9000.

- `WHERE` keeps only the rows where the condition is true.
- Text values go in **single quotes** (`'BUILDING'`). Double quotes mean a column name.
- `ORDER BY ... DESC` sorts from largest to smallest.

### 3. Count and summarize: `GROUP BY` (10 min)

How many customers does each segment have?

```sql
SELECT mktsegment, count(*) AS customers
FROM lakehouse.samples.customer
GROUP BY mktsegment
ORDER BY customers DESC
```

Expected: 5 rows, one per segment, each with roughly 300 customers.

`GROUP BY mktsegment` puts all rows with the same segment into one group, and `count(*)`
counts the rows in each group. **Rule of thumb:** every column in the `SELECT` list is
either in the `GROUP BY` or inside an aggregate such as `count`, `sum`, `avg`, `min` or
`max`. `AS customers` just names the result column.

### 4. Combine tables: `JOIN` (10 min)

Orders do not say which segment the customer is in; customers do. A `JOIN` combines them
on the column they share, the customer key:

```sql
SELECT o.orderkey, o.orderdate, o.totalprice, c.name, c.mktsegment
FROM lakehouse.samples.orders o
JOIN lakehouse.samples.customer c ON o.custkey = c.custkey
LIMIT 5
```

Expected: 5 orders, each now showing the customer's name and segment.

`o` and `c` are short aliases, so `o.custkey` means "the `custkey` column of orders". The
`ON` condition says which rows belong together. Forgetting it (or joining on the wrong
column) is the most common SQL mistake: you get far too many rows.

### 5. Filter on dates (5 min)

```sql
SELECT count(*) AS orders_1996
FROM lakehouse.samples.orders
WHERE orderdate >= DATE '1996-01-01' AND orderdate < DATE '1997-01-01'
```

Expected: `2297`.

`DATE '1996-01-01'` is a date literal. "From January 1st, and before the next January 1st"
is the safest way to say "the year 1996": it works for dates and for timestamps.

### 6. Exercise: answer the question and save it (10 min)

Put steps 3 to 5 together: join orders to customers, keep only 1996 orders, and group by
segment. Then save the answer as a table in your schema.

First make sure your schema exists (safe to run again):

```sql
CREATE SCHEMA IF NOT EXISTS lakehouse.dbt_<you>
```

Then write the query. The result must have exactly these columns:

| column | meaning |
|---|---|
| `market_segment` | the customer's `mktsegment` |
| `orders` | number of 1996 orders in that segment |
| `total_price` | sum of those orders' `totalprice`, rounded to 2 decimals |

Start from this skeleton and fill in the `...`:

```sql
CREATE OR REPLACE TABLE lakehouse.dbt_<you>.a1_segment_revenue_1996 AS
SELECT
    c.mktsegment                 AS market_segment,
    count(*)                     AS orders,
    round(sum(o.totalprice), 2)  AS total_price
FROM lakehouse.samples.orders o
JOIN ...
WHERE ...
GROUP BY ...
```

`CREATE OR REPLACE TABLE ... AS SELECT` runs the query and stores its result as a new
table. `OR REPLACE` lets you run it again after a fix without an "already exists" error.

Look at your table:

```sql
SELECT * FROM lakehouse.dbt_<you>.a1_segment_revenue_1996 ORDER BY total_price DESC
```

Expected output:

| market_segment | orders | total_price |
|---|---|---|
| BUILDING | 557 | 80313228.33 |
| FURNITURE | 472 | 65238850.11 |
| AUTOMOBILE | 452 | 61700951.28 |
| HOUSEHOLD | 416 | 61550669.49 |
| MACHINERY | 400 | 55680541.33 |

So the answer is **BUILDING**: 557 orders worth about 80.3 million in 1996.

## Check your work

In a JupyterLab terminal (**File → New → Terminal**):

```bash
lab-tracks check A1
```

or run the last cell of the notebook. You should see `RESULT: PASS`. If a check fails, the
output says what it found and what to try.

To start this module over: `lab-tracks reset A1`. It restores the notebook and drops
`a1_segment_revenue_1996` from your schema (nothing else).

## Common mistakes

| Symptom | Cause and fix |
|---|---|
| `Access Denied: Cannot create table lakehouse.samples...` | You tried to write into `samples`. Write into **your** schema, `lakehouse.dbt_<you>`. |
| `Access Denied: Cannot create schema lakehouse.dbt_...` | The name after `dbt_` must be exactly your user name, in lower case. |
| `Schema 'dbt_...' does not exist` | Run the `CREATE SCHEMA IF NOT EXISTS` line first. |
| `Column 'mktsegment' cannot be resolved` | The column is on `customer`, so it needs the `c.` alias once two tables are joined, or the `JOIN` is missing. |
| `... must be an aggregate expression or appear in GROUP BY clause` | A column in `SELECT` is neither grouped nor aggregated. Add it to `GROUP BY`. |
| Numbers far too large | A missing or wrong `ON` condition multiplies rows. Join on `o.custkey = c.custkey`. |
| Orders slightly off | The date filter includes 1997-01-01 (`<=`) or starts at 1995. Use `>= DATE '1996-01-01' AND < DATE '1997-01-01'`. |
| `line 1:1: mismatched input` in SQL Lab | Select only one statement before pressing **Run**, or put each statement in its own tab. |

## What you learned

- Look first (`LIMIT`), then filter (`WHERE`), summarize (`GROUP BY` with aggregates) and
  combine (`JOIN ... ON`).
- Save an answer with `CREATE OR REPLACE TABLE ... AS SELECT` in your own schema, where
  other tools can use it.

**Next:** A2 · exploratory analysis with DuckDB and JupySQL.
