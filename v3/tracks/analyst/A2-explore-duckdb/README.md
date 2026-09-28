# A2 · Exploring data with DuckDB and JupySQL

**Time:** about 50 minutes · **Profile:** every profile (`core`, `engineer`, `full`) ·
**You need:** a lab login in the `analyst` group (or `engineer`/`lab-admin`); A1 done (you
know `SELECT`, `WHERE`, `GROUP BY`)

## Goal

By the end you can explore an unfamiliar table quickly, check a hunch with numbers and a
chart, and publish what you found as a table other people can use.

The question for this module:

> The operations team believes that **some shipping modes deliver much later than
> others**. Is that true?

You will answer it with a notebook, `a2_explore.ipynb` in this folder, and save the answer
as the table `a2_late_by_shipmode` in your own schema.

## Concepts in two minutes

- **Exploratory analysis** is what you do *before* you know the answer: look at the size of
  the data, profile the columns, try a definition, look at a distribution, then compare
  groups. Most of it is thrown away; the point is to learn what the data can and cannot say.
- **DuckDB** is a SQL engine that runs **inside your workspace** (a library, like pandas).
  In this lab it reads the lakehouse tables directly: the catalog gives *you* short-lived,
  read-only credentials for exactly the table you query ("vended credentials"). There is no
  password or key in your notebook.
- **Trino** (from A1) is the lab's **shared** engine. It runs on the lab's servers, for
  everyone.
- **JupySQL** gives the notebook `%%sql` cells. The first line picks the engine:
  `%%sql duck` or `%%sql trino`.
- **Vega-Lite** is a small language for charts: you say which column goes on which axis, and
  JupyterLab draws it. It is built into JupyterLab, so there is nothing to install.

| | DuckDB (`duck`) | Trino (`trino`) |
|---|---|---|
| Runs | in your workspace (your CPU and memory) | on the lab's shared servers |
| Good for | fast, interactive exploring of small and medium tables; DuckDB-only helpers such as `SUMMARIZE` | big tables and joins; anything other people or tools (dbt, Superset) must see |
| Can write lab tables | no (read-only here) | yes, in your own schema `dbt_<you>` |

## Steps

Open `a2_explore.ipynb` (double-click it in the file browser) and run the cells from the top
with `Shift+Enter`. Each step below matches a section of the notebook.

### 0. Connect (2 min)

The first cell connects both engines and prints your schema. Expected:
`You are <you>. Your schema is lakehouse.dbt_<you>`.

> **Why two connections?** You will explore with DuckDB, then publish with Trino. Having
> both open side by side makes it easy to compare them.

### 1. How big is the table? (2 min)

```sql
%%sql duck
SELECT count(*) AS line_items
FROM lakehouse.samples.lineitem
```

Expected: `60175`. `lineitem` has one row per item of an order: what was shipped, how, and
three dates (shipped, promised, received).

### 2. Profile every column: `SUMMARIZE` (5 min)

```sql
%%sql duck
SELECT column_name, column_type, min, max, approx_unique, null_percentage
FROM (SUMMARIZE lakehouse.samples.lineitem)
```

Expected: 16 rows, one per column. Read it like a doctor's chart:

- `shipmode` has 7 different values: `AIR`, `FOB`, `MAIL`, `RAIL`, `REG AIR`, `SHIP`, `TRUCK`.
- `commitdate` (promised) and `receiptdate` (received) run from 1992 to 1998.
- `null_percentage` is `0.00` everywhere, so nothing is missing.

> **Why profile first?** It catches surprises (missing values, odd ranges, text where you
> expected numbers) before they sneak into your answer.

### 3. Define "late" (5 min)

Before you can count late items you must say what "late" means. Here: **received after the
promised date**, `receiptdate > commitdate`.

```sql
%%sql duck
SELECT orderkey, shipmode, commitdate, receiptdate,
       date_diff('day', commitdate, receiptdate) AS days_late
FROM lakehouse.samples.lineitem
LIMIT 5
```

Expected: 5 rows. `days_late` is negative for early deliveries and positive for late ones.
Writing the definition down (and using the same one everywhere) is half of every analysis.

### 4. Look at the whole distribution, as a chart (10 min)

A count per value of `days_late` is kept in Python as a pandas DataFrame, then drawn:

```python
delays = duck.sql("""
    SELECT date_diff('day', commitdate, receiptdate) AS days_late, count(*) AS line_items
    FROM lakehouse.samples.lineitem
    GROUP BY days_late
    ORDER BY days_late
""").df()
bar_chart(delays, "days_late", "line_items", "How many days late (negative = early)")
```

`bar_chart` is defined in that cell: about ten lines that describe a Vega-Lite bar chart
(`mark: bar`, which column is `x`, which is `y`). Read it; you will reuse it in step 6.

Expected: `206 different values of days_late`, and a wide hill of bars from about -90 to
+120 days. **Most items arrive late, often by weeks.** That is worth knowing, but it does not
answer the question yet: is it worse for some modes?

### 5. Same question, two engines (8 min)

The notebook runs one `GROUP BY shipmode` query on both engines and prints the time and
whether the answers match. Expected: `Same answer: True`, both well under a second.

When to use which:

- Exploring, trying things, profiling, a table that fits in your workspace: **DuckDB**.
  Nobody waits for you and you wait for nobody.
- A big table, a heavy join, or a result that others (or dbt, or Superset) must see:
  **Trino**.

The next cell sends `SUMMARIZE` to Trino. Expected: `Trino says: line 1:1: mismatched input
'SUMMARIZE'`. The two engines share most SQL, but each has extras. When a query that worked in
one engine fails in the other, this is the first thing to suspect.

### 6. Exercise: late items per shipping mode (10 min)

Complete the query in the notebook (replace `...`):

```sql
SELECT shipmode                                              AS ship_mode,
       count(*)                                              AS line_items,
       count(*) FILTER (WHERE receiptdate > commitdate)      AS late_items,
       round(100.0 * count(*) FILTER (WHERE receiptdate > commitdate)
             / count(*), 1)                                  AS late_pct
FROM lakehouse.samples.lineitem
GROUP BY ...
ORDER BY late_pct DESC
```

- `count(*) FILTER (WHERE ...)` counts only the rows where the condition holds.
- `100.0 * late / all` is a percentage. Write `100.0`, not `100`: with whole numbers only,
  Trino divides without decimals and you would get `63` instead of `63.5`.

Expected output:

| ship_mode | line_items | late_items | late_pct |
|---|---|---|---|
| FOB | 8641 | 5484 | 63.5 |
| MAIL | 8669 | 5467 | 63.1 |
| RAIL | 8566 | 5402 | 63.1 |
| SHIP | 8482 | 5354 | 63.1 |
| AIR | 8491 | 5346 | 63.0 |
| TRUCK | 8710 | 5474 | 62.8 |
| REG AIR | 8616 | 5370 | 62.3 |

Then chart it with `bar_chart(by_mode, "ship_mode", "late_pct", ..., x_type="nominal")`
(`nominal` = categories, not numbers). The bars start at 0 and look almost identical.

> **Honest charts.** A chart whose axis started at 62 % would make 62.3 vs 63.5 look like a
> huge difference. Bar charts start at zero.

### 7. Publish the answer with Trino (5 min)

`by_mode` lives only in your notebook: nobody else can see it, and it is gone when the kernel
stops. To share the answer, save it as a table in your schema. In the `%%sql trino` cell, put
your step-6 `SELECT` (without `ORDER BY`) after `AS`:

```sql
%%sql trino
CREATE OR REPLACE TABLE lakehouse.{{schema}}.a2_late_by_shipmode AS
SELECT shipmode AS ship_mode, ...
```

The notebook fills in `{{schema}}` for you. Run the next cell to look at the table.
Expected: the same 7 rows. Trino prints `late_pct` as `63.5000000000000000`: the same
number, kept as an exact decimal by Trino. (A small engine difference again.)

### 8. The answer (3 min)

Every shipping mode delivers about **63 %** of its items late (62.3 % to 63.5 %). The spread
is about one percentage point: **the data does not support the hunch.** Lateness is a problem
for every mode, so the team should look elsewhere (suppliers, order size, time of year).
Ruling a suspicion out, with numbers, is a real result.

## Check your work

In the notebook's last cell, or in a terminal:

```bash
lab-tracks check A2
```

You should see `RESULT: PASS`. The check reads your table `a2_late_by_shipmode` through Trino
and compares it with numbers it computes itself. It does not look at your notebook.

To start over: `lab-tracks reset A2`. It restores the notebook and drops
`a2_late_by_shipmode` from your schema (nothing else).

## Common mistakes

| Symptom | Cause and fix |
|---|---|
| `Catalog Error: Table with name lineitem does not exist` (DuckDB) | Use the full name `lakehouse.samples.lineitem`, and run the first cell (it attaches the catalog as `lakehouse`). |
| A `%%sql` cell prints nothing, or runs on the wrong engine | The engine goes on the **first line** of the cell: `%%sql duck` or `%%sql trino`, nothing else on that line. |
| `mismatched input 'SUMMARIZE'` | `SUMMARIZE` is DuckDB-only. Run it in a `%%sql duck` cell. |
| `NameError: name 'duck' is not defined` | The kernel restarted. Run the first cell again. |
| `late_pct` is `63` instead of `63.5`, or `0.63` | Whole-number division, or a fraction instead of a percentage: use `100.0 * late / all`. |
| `late_items` a bit too high | `>=` counts on-time deliveries as late. Late means strictly `>`. |
| `Access Denied: Cannot create table lakehouse.samples...` | Publish into **your** schema: `lakehouse.{{schema}}....` |
| DuckDB error mentioning `non-200 status code` when creating a table | DuckDB is read-only here: publish with a `%%sql trino` cell. |
| The chart cell shows `<IPython.core.display...>` or nothing | Open the notebook in JupyterLab (not a plain text editor), and run the cell that defines `bar_chart` first. |
| A token or `401` error after a long break | Your login expired. Run the first cell again (it reconnects with a fresh token); if that fails, log out of JupyterLab and back in. |

## What you learned

- A repeatable way to explore: size → profile (`SUMMARIZE`) → definition → distribution →
  compare groups.
- DuckDB for fast, private exploring; Trino for shared, big or published work; the same SQL
  mostly works on both.
- A chart that tells the truth (bars from zero), and that "no difference" is an answer.
- Publishing a result as a table in your own schema.

**Next:** A3 · your first dbt model.
