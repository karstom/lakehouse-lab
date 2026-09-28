# A2 · Exploring data with DuckDB and JupySQL: tutor notes

> For the Phase 5 AI tutor and for human facilitators. Do not paste the full answer; give
> the smallest hint that unblocks the learner, then let them run the checkpoint again.

## Learning objectives

After this module the learner can:

1. Follow a repeatable exploration routine: size (`count(*)`) → profile (`SUMMARIZE`) →
   definition ("late" = `receiptdate > commitdate`) → distribution → compare groups.
2. Say where DuckDB and Trino run, and choose one: DuckDB for private, fast exploring in the
   workspace; Trino for big/shared work and for anything others must see.
3. Explain, in one sentence, why DuckDB can read lab tables without a password (the catalog
   vends short-lived credentials to the logged-in user).
4. Pick the engine per `%%sql` cell (`%%sql duck` / `%%sql trino`) and recognize an
   engine-specific feature (`SUMMARIZE`) from its error in the other engine.
5. Use conditional counting (`count(*) FILTER (WHERE ...)`) and compute a percentage without
   integer division (`100.0 * a / b`).
6. Draw a bar chart from a DataFrame with Vega-Lite, and explain why bar axes start at zero.
7. Publish a result as a table in their own schema with Trino, and state the conclusion
   ("no meaningful difference") as a finding.

## Prerequisites

- A1 (or equivalent SQL: `SELECT`, `WHERE`, `GROUP BY`).
- A lab login in `analyst`/`engineer`/`lab-admin`; the workspace started.
- DuckDB here is read-only on the lakehouse; writes go through Trino into `dbt_<user>`.

## The expected answer

Table `lakehouse.dbt_<user>.a2_late_by_shipmode`, columns `ship_mode, line_items, late_items,
late_pct`, 7 rows. Every mode is 62.3–63.5 % late (FOB highest at 63.5, REG AIR lowest at
62.3). The checkpoint recomputes the reference from `samples` at check time; `late_pct` may be
off by at most 0.05 (rounding).

## Common mistakes and hints (most frequent first)

| What the learner sees | Likely cause | Hint to give |
|---|---|---|
| A `%%sql` cell does nothing or runs on the other engine | engine name not alone on the first line, or extra words after it | "What is on the very first line of that cell?" |
| `mismatched input 'SUMMARIZE'` | ran `SUMMARIZE` on Trino | "Which engine has `SUMMARIZE`? Look at the first line of the cell." |
| `Table with name lineitem does not exist` | short table name in DuckDB, or first cell not run | "Does the name have all three parts? Did the first cell run?" |
| `late_pct` = 63 (no decimal) | `100 *` instead of `100.0 *` in Trino | "What happens when Trino divides two whole numbers?" |
| `late_pct` ≈ 0.63 | fraction instead of percentage | "Is 0.63 a percentage?" |
| `late_items` too high by about 75 per mode | `>=` instead of `>` | "Is an item that arrives on the promised day late?" |
| checkpoint: 1 row, or dozens of rows | missing or wrong `GROUP BY` | "What should one row of your answer be?" |
| `Access Denied ... samples` | CTAS into `samples` | "Which schema is yours? The notebook prints it in the first cell." |
| DuckDB `non-200 status code` on CREATE | tried to publish with DuckDB | "Which engine can write lab tables?" |
| chart cell shows nothing | `bar_chart` cell not run, or notebook opened as text | "Run the cell that defines `bar_chart` first." |
| `401`/token error after a break | login token expired in the DuckDB connection | "Run the first cell again; it re-attaches with a fresh token." |

## Socratic prompts

- "Before comparing modes: what share of *all* items is late? Keep that number in mind."
- "If one mode were really worse, what would its bar look like next to the others?"
- "The spread is about one percentage point over ~8,600 items per mode. Is that a difference
  anyone should act on?"
- "Why is the answer saved with Trino and not with DuckDB?"

## Extensions for fast learners

- Is lateness different by **year** (`year(receiptdate)`)? By `shipinstruct`?
- Chart the average `days_late` of late items per mode (all about 41–42 days).
- Time the same `GROUP BY` on `lineitem` joined to `orders` in both engines.

## Checkpoint and reset

- `lab-tracks check A2` (or `python3 checkpoint.py`): schema exists → table exists → columns
  → 7 modes → counts → percentages (±0.05).
- `lab-tracks reset A2` (or `python3 checkpoint.py --reset`): drops only
  `dbt_<user>.a2_late_by_shipmode`; the notebook comes back as delivered.
