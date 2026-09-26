# A4 · A chart and a dashboard in Superset: tutor notes

> For the Phase 5 AI tutor and for human facilitators. Do not click through the UI for the
> learner; name the menu or field that is wrong, then let them run the checkpoint again.

## Learning objectives

After this module the learner can:

1. Name the three layers of a BI tool (dataset → chart → dashboard) and what each stores.
2. Create a dataset on their own table (`dbt_<user>.segment_revenue`).
3. Build a bar chart (X-axis + one metric) and a line chart (X-axis + metric + dimension),
   and explain why the metric is `SUM(net_revenue)` rather than `AVG`/`COUNT`.
4. Save charts to a dashboard and arrange it.
5. Explain that Superset runs every chart's query in Trino **as the viewer**, so a shared
   dashboard shows each person only what they may read.
6. Recognize an incomplete last period (1998 ends in August) before reading a trend.

## Prerequisites

- Profile `full` (Superset). A3 done: `lakehouse.dbt_<user>.segment_revenue` exists (35 rows).
- Group `analyst`, `engineer` or `lab-admin`: their Superset roles include `lab_author`,
  which may add datasets (plain Gamma cannot). Viewers cannot do this module.
- The learner has logged in to Superset once in the browser (Superset creates its user at the
  first login; the checkpoint needs that user).

## The expected answer

- Dataset: physical, database `Lakehouse (Trino)`, schema `dbt_<user>`, table
  `segment_revenue`, owned by the learner.
- Chart `A4 Revenue by segment`: Bar Chart, X-axis `market_segment`, metric
  `SUM(net_revenue)`, no dimension, no filter → 5 rows: BUILDING ≈ 510.4 M, AUTOMOBILE
  ≈ 406.1 M, FURNITURE ≈ 403.8 M, HOUSEHOLD ≈ 379.3 M, MACHINERY ≈ 345.6 M.
- Chart `A4 Revenue by year`: Line Chart, X-axis `order_year`, metric `SUM(net_revenue)`,
  dimension `market_segment`.
- Dashboard `A4 Segment revenue` with both charts, owned by the learner.

The checkpoint uses Superset's REST API **as the learner** (their Keycloak token as a Bearer
token; Superset accepts tokens issued to the workspace's `jupyterhub` client for existing,
active users), finds the objects by exact name + ownership, and runs the bar chart's saved
query (`/api/v1/chart/<id>/data/`), comparing it with a reference computed from `samples`
(0.5 % tolerance).

## Common mistakes and hints (most frequent first)

| What the learner sees | Likely cause | Hint to give |
|---|---|---|
| Schema/table missing in the dataset form | Superset's cached lists; or A3 not done | "Try the refresh arrow next to the field. Does `lab-tracks check A3` pass?" |
| check: `no chart of yours has exactly that name` | name typo, extra space, other capitals | "Compare the name letter by letter with the lesson." |
| check: values differ | metric `COUNT(*)`/`AVG`, or a filter on `order_year` | "One bar adds up seven years. Which aggregate adds things up?" |
| check: not 5 rows | a Dimension on the bar chart, or X-axis on another column | "What is on the X-axis? Is anything in Dimensions?" |
| check: chart not on the dashboard | saved without "Add to dashboard" | "Open the chart, Save, and pick the dashboard in 'Add to dashboard'." |
| check: `Superset refused your login token` | never logged in to Superset | "Open Superset in the browser once, then check again." |
| No **+ Dataset** button | the user is only in `viewer` (or their roles did not refresh) | "Which lab group are you in? Log out of Superset and back in." |
| "Dataset already exists" | created it earlier | "Open it from the Datasets list." |
| Line chart shows one line | Dimensions empty | "How does Superset know to draw one line per segment?" |
| "The revenue collapsed in 1998!" | incomplete last year | "When does the data end? `SELECT max(orderdate) FROM lakehouse.samples.orders`" |

## Socratic prompts

- "If victor (a viewer) opens your dashboard, whose permissions decide what he sees?"
- "Your table has 35 rows but the bar chart has 5 bars. What did Superset do in between?"
- "What would you tell a manager who points at 1998 on the line chart?"

## Extensions for fast learners

- Add a native filter on `market_segment` to the dashboard.
- Chart A2's `a2_late_by_shipmode` (needs its own dataset) and add it to the dashboard.
- Open **SQL Lab**, write a query over `segment_revenue`, and **Save dataset** from the
  result (a virtual dataset).

## Checkpoint and reset

- `lab-tracks check A4` (or `python3 checkpoint.py`): A3 table exists → Superset knows the
  learner → own dataset on `dbt_<user>.segment_revenue` → bar chart exists, uses it, 5
  segments, right sums → line chart exists, uses it, has rows → dashboard exists, has both.
- `lab-tracks reset A4` (or `python3 checkpoint.py --reset`): deletes, in Superset, only the
  learner's own dashboard `A4 Segment revenue`, charts `A4 Revenue by segment` / `A4 Revenue
  by year`, and their dataset on `dbt_<user>.segment_revenue` (kept if other charts of theirs
  still use it). The A3 table stays.
