# A1 · SQL basics: tutor notes

> For the Phase 5 AI tutor and for human facilitators. Do not paste the full answer; give
> the smallest hint that unblocks the learner, then let them run the checkpoint again.

## Learning objectives

After this module the learner can:

1. Explain what `catalog.schema.table` means, and name the lab's catalog (`lakehouse`),
   the sample schema (`samples`) and their own schema (`dbt_<user>`).
2. Explore an unfamiliar table safely with `SELECT * ... LIMIT`.
3. Filter rows with `WHERE`, including text in single quotes and a half-open date range.
4. Summarize with `GROUP BY` and aggregates, and state the "grouped or aggregated" rule.
5. Combine two tables with `JOIN ... ON` on a shared key, and recognize the symptom of a
   wrong join (too many rows, inflated sums).
6. Save a result with `CREATE OR REPLACE TABLE ... AS SELECT` into their own schema, and
   explain why they cannot write into `samples` (group-based permissions, runs as them).

## Prerequisites

- A lab login in group `analyst` (or `engineer`/`lab-admin`); the workspace started.
- Analysts can write only in `lakehouse.dbt_<their user name>`; that is by design.

## The expected answer

Table `lakehouse.dbt_<user>.a1_segment_revenue_1996`, columns `market_segment, orders,
total_price`, 5 rows. BUILDING 557 / 80313228.33 is the top segment. The checkpoint
recomputes the reference from `samples` at check time.

## Common mistakes and hints (most frequent first)

| What the learner sees | Likely cause | Hint to give |
|---|---|---|
| `Access Denied: Cannot create table lakehouse.samples.…` | wrote into `samples` | "Which schema is yours? Look at the first cell's output." |
| `Schema 'dbt_x' does not exist` | skipped `CREATE SCHEMA IF NOT EXISTS` | "Is there a step before the CREATE TABLE?" |
| `Access Denied: Cannot create schema` | typo in the schema name, or upper case | "The schema is `dbt_` + your user name, all lower case." |
| `must be an aggregate expression or appear in GROUP BY clause` | extra column in SELECT | "Every selected column is grouped or aggregated. Which one is neither?" |
| `Column 'mktsegment' cannot be resolved` | JOIN missing, so customer columns are unknown | "Which table has `mktsegment`? Is it in your FROM/JOIN?" |
| Totals ~100x too big, or many more than 5 rows | join without a correct ON, or grouped by the wrong column | "How many rows does the query return before GROUP BY? What should one row be?" |
| Counts a little off (e.g. includes 1997-01-01) | `<=` on the end date, or `year(orderdate) = 1996` with a typo | "Say 'the year 1996' as a range: from Jan 1st, and before the next Jan 1st." |
| checkpoint: columns differ | missing `AS` aliases, or wrong column order | "The checkpoint wants `market_segment, orders, total_price`, in that order." |
| `mismatched input` in SQL Lab | ran two statements at once | "SQL Lab runs what is selected; run one statement at a time." |
| `Table ... already exists` | used `CREATE TABLE` twice | "Use `CREATE OR REPLACE TABLE` to rebuild it." |

## Socratic prompts

- "Before you join: how many orders are there in 1996? Keep that number in mind."
- "After the join and the filter, does the sum of `orders` over all segments still equal
  2297? What would it mean if it didn't?"
- "Why do you think the lab lets you create tables only in your own schema?"

## Extensions for fast learners

- Add the average order value per segment (`round(avg(o.totalprice), 2)`).
- Which **nation** ordered the most in 1996? (join `customer` → `nation`)
- Rank segments with `rank() OVER (ORDER BY sum(o.totalprice) DESC)`.

## Checkpoint and reset

- `lab-tracks check A1` (or `python3 checkpoint.py`): schema exists → table exists →
  columns → 5 segments → 1996 order counts → totals (1% tolerance).
- `lab-tracks reset A1` (or `python3 checkpoint.py --reset`): drops only
  `dbt_<user>.a1_segment_revenue_1996`; the schema and other tables stay.
- Reset also puts the lesson files back as they were. Any file the learner changed is moved
  (never deleted) to `~/.lakehouse/tracks-backup/A1-<time>/`, so their own SQL is not lost.
