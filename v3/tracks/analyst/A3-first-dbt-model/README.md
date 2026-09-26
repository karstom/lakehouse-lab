# A3 · Your first dbt model

**Time:** about 55 minutes · **Profile:** every profile (`core`, `engineer`, `full`) ·
**You need:** a lab login in the `analyst` group (or `engineer`/`lab-admin`); A1 done

## Goal

By the end you can turn a query into a **dbt model**: a named, tested, documented table that
dbt rebuilds for you in the right order, every time.

You will add one model, `segment_revenue` (net revenue per customer market segment and
year), to a copy of the lab's starter dbt project, give it tests and a description, and
build it into your own schema. In A4 you will chart it in Superset.

## Concepts in two minutes

- **Why dbt?** In A1 and A2 you saved answers with `CREATE OR REPLACE TABLE ... AS SELECT`.
  That works once. With ten such tables that depend on each other you need to remember the
  order, re-run them when data changes, and trust they are still right. **dbt** does that:
  you write each table as a `SELECT` in its own file (a **model**), and dbt creates the
  tables, in dependency order, and runs your **tests** on them.
- **`ref('model')`** is how one model uses another: `from {{ ref('fct_orders') }}`. dbt
  replaces it with the full table name (`lakehouse.dbt_<you>.fct_orders`) and learns that
  your model must be built *after* `fct_orders`.
- **Materialization:** whether dbt builds a model as a *view* or a *table*. In the starter
  project, `models/staging/` are views and `models/marts/` are tables (see
  `dbt_project.yml`).
- **Tests** are queries that must return no rows: `not_null` (no empty values),
  `accepted_values` (only values from a list), `unique`, `relationships`. A failing test
  tells you the data is not what you assumed, *before* someone builds a dashboard on it.
- **Docs:** descriptions in a `.yml` file next to the model. dbt turns them into a website
  and, with `persist_docs`, writes them onto the table itself, so people who find the table
  in Trino or Superset see them too.
- **Where it goes:** your own schema `lakehouse.dbt_<you>`, set in the project's
  `profiles.yml`. dbt connects to Trino **as you**, with your login token (the `dbt`
  command in the workspace adds it for you).

## Steps

Everything happens in a **terminal** (File → New → Terminal) and the **file editor**
(double-click a file in the left-hand file browser).

### 1. Your own copy of the starter project (5 min)

```bash
cd ~/tracks/analyst/A3-first-dbt-model
cp -r /opt/lakehouse/starter/dbt_lakehouse dbt_project
cd dbt_project
dbt debug
```

`/opt/lakehouse/starter/` is the pristine starter project that comes with the workspace.
Copying it here gives you a sandbox for this module (and `lab-tracks reset A3` can put it
away cleanly). Expected, at the end of `dbt debug`:

```
  Connection test: [OK connection ok]
All checks passed!
```

> **Why `dbt debug` first?** It checks your project files and the connection to Trino. When
> something is wrong later, you then know it is your SQL, not the setup.

### 2. Build the starter project and look around (10 min)

```bash
dbt build
```

Expected, after about 30 seconds: `Done. PASS=27 WARN=0 ERROR=0 SKIP=0 ... TOTAL=27`. You may
also see a yellow `[WARNING][DeprecationsSummary]` about `MissingArgumentsPropertyInGenericTest`:
it comes from the starter's older test syntax and is harmless.

`dbt build` = run every model, then its tests. Now open these files in the file browser
(`tracks/analyst/A3-first-dbt-model/dbt_project/`) and read them, in this order:

| File | What to notice |
|---|---|
| `models/staging/_sources.yml` | the **sources**: the raw tables in `lakehouse.samples` |
| `models/staging/stg_orders.sql` | a staging model: renames columns (`orderkey` → `order_id`); `{{ source(...) }}` points at a raw table |
| `models/marts/fct_orders.sql` | a mart: one row per order with its **net revenue**; `{{ ref('stg_orders') }}` points at another model |
| `models/marts/_marts.yml` | tests and descriptions for the marts |

### 3. Write the model (10 min)

Copy the skeleton into the marts folder and open it:

```bash
cp ../segment_revenue.sql models/marts/
```

`models/marts/segment_revenue.sql` has three blanks `___`:

```sql
select
    c.market_segment,
    year(o.order_date)            as order_year,
    count(*)                      as orders,
    count(distinct o.customer_id) as customers,
    round(sum(o.___), 2)          as net_revenue
from {{ ref('___') }} o
join {{ ref('dim_customers') }} c on o.customer_id = ___
group by 1, 2
```

Fill them in:
- which model has one row per order? (that is `o`)
- which of its columns holds the revenue after discount?
- which column of `dim_customers` (`c`) matches `o.customer_id`?

A model file is just a `SELECT`: no `CREATE TABLE`, no schema name. dbt adds those.

### 4. Build it (5 min)

```bash
dbt run --select segment_revenue
```

Expected: `1 of 1 OK created sql table model dbt_<you>.segment_revenue ... [CREATE TABLE (35
rows)]`. 35 rows = 5 segments × 7 years (1992 to 1998).

`--select segment_revenue` builds only your model. `dbt build --select +segment_revenue`
would also rebuild everything it depends on (the `+` in front means "and its parents").

Look at the result in Trino, from a notebook (`%%sql` as in A1) or in Superset SQL Lab:

```sql
SELECT market_segment, sum(net_revenue) AS net_revenue
FROM lakehouse.dbt_<you>.segment_revenue
GROUP BY market_segment
ORDER BY net_revenue DESC
```

Expected: BUILDING first with about 510.4 million, MACHINERY last with about 345.6 million.

### 5. Add tests (10 min)

```bash
cp ../segment_revenue.yml models/marts/
```

Open `models/marts/segment_revenue.yml`. It already has `not_null` tests. Complete the
`accepted_values` test: replace `[___]` with the list of market segments you saw in A1, for
example `[AUTOMOBILE, BUILDING, ...]`. Then:

```bash
dbt test --select segment_revenue
```

Expected: `Done. PASS=3 WARN=0 ERROR=0`. **Try it wrong on purpose:** leave out one segment
and run the test again. You get `FAIL 1`: one value in the table is not in your list. That is
exactly what a test is for: it catches data that breaks your assumptions. Put the segment
back.

### 6. Document it (10 min)

In the same `.yml` file, replace the model's `description: ___ ...` with one sentence that
says what **one row** is, for example: *One row per customer market segment and order year,
with its orders, customers and net revenue.* Then rebuild, and generate the docs site:

```bash
dbt run --select segment_revenue
dbt docs generate
dbt docs serve --port 8580 --no-browser
```

`persist_docs` (already in the `.yml`) wrote your description onto the table in Trino during
`dbt run`. `dbt docs serve` starts a small website; open it in a new browser tab at

```
https://jupyter.<your lab domain>/user/<you>/proxy/8580/
```

(the trailing `/` matters). Find `segment_revenue` in the left-hand tree: your description,
columns and tests are there. Click the blue **lineage** button (bottom right) to see how your
model depends on the starter's models. Press `Ctrl+C` in the terminal to stop the site.

### 7. Check your work (5 min)

```bash
lab-tracks check A3
```

You should see `RESULT: PASS`. The check reads your table through Trino and compares it with
numbers it computes from `samples`, runs your model's tests, and reads the table comment. It
does not grade your SQL text.

To start over: `lab-tracks reset A3`. It drops `segment_revenue` from your schema and moves
your `dbt_project/` folder to `~/.lakehouse/tracks-backup/` (nothing is deleted). The starter
models dbt built in your schema (`stg_*`, `fct_orders`, ...) stay.

## Common mistakes

| Symptom | Cause and fix |
|---|---|
| `depends on a node named '___' which was not found` | A blank is still in the file, or a model name is misspelled in `ref('...')`. |
| `depends on a node named '...'` although you filled everything in | dbt reads `{{ ... }}` even inside `--` comments. Remove the braces from comments. |
| `Column 'net_revenue' cannot be resolved` or similar | The blank got a column that the model does not have. Look at `fct_orders.sql` for the right name. |
| `Access Denied: Cannot create table lakehouse.dbt_...` | `profiles.yml` was changed. Copy the project again (step 1). |
| `dbt: command not found`, or `Env var required but not provided: 'DBT_ENV_SECRET_LAB_TOKEN'` | Use the workspace's `dbt` (in a JupyterLab terminal, not another shell); it adds your token. |
| `Could not find profile named 'lakehouse'` | Run dbt inside `dbt_project/` (where `profiles.yml` is). |
| `Nothing to do` / `The selection criterion 'segment_revenue' does not match any enabled nodes` | The file is not in `models/` (check the `cp` target), or has a different name. |
| Test `accepted_values ... FAIL 1` | A segment is missing from your list, or misspelled (they are upper case). |
| Checkpoint: "description is on the table" fails | You edited the `.yml` but did not `dbt run` again; `persist_docs` writes the comment at build time. |
| `proxy/8580` page shows an error | `dbt docs serve` is not running (or not yet: wait a few seconds), or the URL misses the trailing `/`. |

## What you learned

- A dbt model is a `SELECT` in a file; `ref()` links models and fixes the build order.
- `dbt run` builds, `dbt test` checks, `dbt build` does both; `--select` narrows it.
- Tests turn assumptions ("only these five segments") into checks that run every time.
- Descriptions become a docs website and, with `persist_docs`, comments on the table.

**Next:** A4 · a chart and a dashboard in Superset over your model (profile `full`).
