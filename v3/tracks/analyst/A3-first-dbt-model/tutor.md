# A3 · Your first dbt model: tutor notes

> For the Phase 5 AI tutor and for human facilitators. Do not paste the full answer; give
> the smallest hint that unblocks the learner, then let them run the checkpoint again.

## Learning objectives

After this module the learner can:

1. Explain what dbt adds over a hand-run `CREATE TABLE AS` (dependency order, repeatable
   rebuilds, tests, docs).
2. Read a dbt project: sources, staging models (views), marts (tables), `dbt_project.yml`
   materializations, `profiles.yml` (target schema `dbt_<user>`, connects as the user).
3. Write a model as a plain `SELECT` using `ref()` to other models, and build it with
   `dbt run --select`.
4. Add generic tests (`not_null`, `accepted_values`) in a `.yml`, run them, and read a
   failing test.
5. Document a model and use `persist_docs` so the description reaches the table in Trino;
   generate and view the docs site and lineage graph.

## Prerequisites

- A1 (SQL, own schema). Terminal basics: `cd`, `cp`.
- The module works in `~/tracks/analyst/A3-first-dbt-model/dbt_project/`, a copy of
  `/opt/lakehouse/starter/dbt_lakehouse` the learner makes in step 1.

## The expected answer

`models/marts/segment_revenue.sql`: `sum(o.net_revenue)`, `from {{ ref('fct_orders') }} o`,
`on o.customer_id = c.customer_id`. Table `lakehouse.dbt_<user>.segment_revenue`, 35 rows
(5 segments × 1992–1998), columns `market_segment, order_year, orders, customers,
net_revenue`. `.yml`: accepted values `AUTOMOBILE, BUILDING, FURNITURE, HOUSEHOLD,
MACHINERY`; a real model description. The checkpoint compares rows with a reference computed
from `samples` (net revenue within 0.1 %), runs `dbt test --select segment_revenue` in the
learner's project (needs a passing `not_null` and `accepted_values` test), and reads the table
comment from `system.metadata.table_comments`.

## Common mistakes and hints (most frequent first)

| What the learner sees | Likely cause | Hint to give |
|---|---|---|
| `depends on a node named '___'` | blank left in `ref('___')` | "Which model has one row per order?" |
| `depends on a node named '...'` after filling blanks | `{{ ref('...') }}` inside a `--` comment (Jinja renders comments) | "dbt reads curly braces even in comments. Is there one left?" |
| `Column '...' cannot be resolved` | wrong column in `sum(o.___)` or join | "Open `fct_orders.sql`: which column is the revenue after discount?" |
| `does not match any enabled nodes` | file not under `models/`, or named differently | "Where did the `cp` put the file? `ls models/marts`" |
| `Could not find profile named 'lakehouse'` / `dbt_project.yml not found` | running dbt outside `dbt_project/` | "Which folder is your terminal in? `pwd`" |
| `accepted_values ... FAIL 1` | a segment missing or misspelled | "Which values does the table have? `SELECT DISTINCT market_segment ...`" |
| checkpoint: row counts wrong | joined on the wrong key, or grouped by the wrong columns | "How many rows should one segment have? (one per year)" |
| checkpoint: net revenue far off | summed another column of `fct_orders` (`total_quantity`, `line_count`) | "Which column is the revenue *after discount*?" |
| checkpoint: description not on the table | `.yml` edited but model not rebuilt; or `persist_docs` removed | "When does dbt write the comment? Run the model again." |
| `proxy/8580` error page | `dbt docs serve` not running, still starting, or URL missing the trailing `/` | "Is the terminal still showing 'Serving docs'? Wait a few seconds." |
| Access denied on create | `profiles.yml` edited (wrong schema) | "Copy the project again from `/opt/lakehouse/starter/`." |

## Socratic prompts

- "What would break if someone renamed `fct_orders`? How would dbt tell you?"
- "Your test says only five segments may appear. What would a sixth one mean for a
  dashboard built on this table?"
- "Why is it useful that the description is on the table itself, not only in the `.yml`?"

## Extensions for fast learners

- Add a `unique`-style check: a singular test in `tests/` that returns rows when a
  `(market_segment, order_year)` pair appears twice.
- Add `avg_order_value` (`net_revenue / orders`) and a test that it is never negative.
- Run `dbt build --select +segment_revenue` and compare with `dbt run --select segment_revenue`.

## Checkpoint and reset

- `lab-tracks check A3` (or `python3 checkpoint.py`): table exists and is a table → columns
  → 35 (segment, year) rows → counts → net revenue → `dbt_project/` present → tests
  `not_null` + `accepted_values` exist and all pass → table comment set.
- `lab-tracks reset A3` (or `python3 checkpoint.py --reset`): drops only
  `dbt_<user>.segment_revenue`; `lab-tracks` moves `dbt_project/` to
  `~/.lakehouse/tracks-backup/`. The starter models in `dbt_<user>` stay (A4, the starter
  notebook and other lessons use them).
