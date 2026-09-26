# A4 · A chart and a dashboard in Superset

**Time:** about 45 minutes · **Profile:** `full` (the one with Superset) ·
**You need:** a lab login in the `analyst` group (or `engineer`/`lab-admin`); **A3 done**
(your table `segment_revenue`)

## Goal

By the end you can turn a table into charts and put them on a dashboard that other people
can open, all in the browser, without writing code.

You will chart your A3 model `lakehouse.dbt_<you>.segment_revenue`:

- **A4 Revenue by segment**: a bar chart, net revenue per market segment;
- **A4 Revenue by year**: a line chart, one line per segment over the years;
- both on a dashboard called **A4 Segment revenue**.

Use exactly these names: the checkpoint finds your work by them.

## Concepts in two minutes

- **Superset** is the lab's dashboard tool (a BI tool). It does not store data: every chart
  is a SQL query that Superset sends to **Trino as you**, so a chart shows only what you
  are allowed to read.
- A **dataset** tells Superset which table a chart uses (and which columns it has). You make
  one per table you want to chart.
- A **chart** = a dataset + a chart type + what goes on each axis + a **metric** (an
  aggregate such as `SUM(net_revenue)`). Superset writes the `GROUP BY` query for you.
- A **dashboard** is a page of charts. It re-runs the charts' queries when someone opens it,
  so it shows the table's current data.
- **Owner:** you own what you create. Other lab users can open your dashboard, but only you
  (and admins) can change or delete it.

## Steps

Open `https://superset.<your lab domain>/` and log in with your lab account (the same login
as JupyterLab).

### 1. Make sure your table is there (3 min)

In Superset: **SQL** → **SQL Lab**. Database **Lakehouse (Trino)**, then run:

```sql
SELECT count(*) FROM lakehouse.dbt_<you>.segment_revenue
```

Expected: `35`. If you get `Table ... does not exist`, go back to A3 (`lab-tracks check A3`).

### 2. Create a dataset (5 min)

1. Top menu **Datasets**, then the **+ Dataset** button (top right).
2. **Database:** `Lakehouse (Trino)`. **Schema:** `dbt_<you>`. **Table:** `segment_revenue`.
   (If your schema or table is not in the list, click the small refresh arrow next to the
   field: Superset caches the lists.)
3. The right side shows the table's columns. Click **Create and explore dataset**.

Superset opens the chart editor on your new dataset.

> **Why a dataset?** It is the bridge between a table and charts. Change it once (for
> example, give a column a nicer label) and every chart on it follows.

### 3. The bar chart (12 min)

In the chart editor:

1. In the **Data** panel, click **View all charts** (under the row of chart icons), type
   `Bar Chart` in **Search all charts**, click it, then **Select**.
2. **X-axis:** drag `market_segment` from the column list on the left into the X-axis box (or
   click the box and choose it).
3. **Metrics:** click the box, open the **Simple** tab, choose column `net_revenue` and
   aggregate `SUM`, then **Save**.
4. Click **Create chart** (or **Update chart**) at the bottom.

Expected: five bars. BUILDING is the tallest, with about 510 million; MACHINERY the lowest,
with about 346 million.

Now save it: **Save** (top right) → **Chart name:** `A4 Revenue by segment` → **Add to
dashboard:** type `A4 Segment revenue` and choose the "create" option that appears → **Save
& go to dashboard**.

> **Why SUM?** The table has one row per segment **and year**. The chart has one bar per
> segment, so the seven yearly values of each segment must be added up. `AVG` or `COUNT`
> would answer a different question.

### 4. The line chart (10 min)

1. Top menu **Charts** → **+ Chart**. Dataset: `segment_revenue`. Chart type: **Line Chart**.
   Click **Create new chart**.
2. **X-axis:** `order_year`. **Metrics:** `SUM(net_revenue)` (as before).
   **Dimensions:** `market_segment` (one line per segment).
3. **Create chart** / **Update chart**.

Expected: five lines from 1992 to 1998, BUILDING on top. All lines drop sharply in **1998**:
that is not a crisis, the sample data simply ends in August 1998. (Always ask "is the last
period complete?" before you read a trend.)

**Save** → name `A4 Revenue by year` → add to the dashboard `A4 Segment revenue` (choose it
from the list this time) → **Save & go to dashboard**.

### 5. Arrange the dashboard (8 min)

On the dashboard **A4 Segment revenue**:

1. Click **Edit dashboard**.
2. Drag the charts so they sit side by side (drop a chart next to the other one), and resize
   them with the handle at their bottom-right corner if you like.
3. Click **Save**.

Expected: both charts on one page, like this: a bar chart on the left, five lines on the
right. Share it by sending the page's address; other lab users can open it.

### 6. Check your work (2 min)

In a JupyterLab terminal:

```bash
lab-tracks check A4
```

You should see `RESULT: PASS`. The check talks to Superset **as you** (with your lab login),
finds your dataset, charts and dashboard by name, and runs your bar chart's query to compare
its numbers with numbers it computes from `samples`.

To start over: `lab-tracks reset A4`. It deletes, in Superset, the two charts, the dashboard
and your `segment_revenue` dataset (only ones you own). Your A3 table stays.

## Common mistakes

| Symptom | Cause and fix |
|---|---|
| Schema `dbt_<you>` or table `segment_revenue` not in the dataset lists | Click the refresh arrow next to the field. Still missing? Finish A3 first. |
| "Dataset already exists" | You already made one: open it from **Datasets** instead. |
| No **+ Dataset** button | Your lab group has no right to add datasets (viewers cannot). Ask your lab admin for the `analyst` group. |
| Bars are all the same height, or show small numbers | The metric is `COUNT(*)` or `AVG(...)`: use `SUM` of `net_revenue`. |
| More than five bars, or bars split in colours | A **Dimension** was added to the bar chart: remove it. |
| Numbers smaller than expected | A filter is set (for example on `order_year`): remove it. |
| Check: `no chart of yours has exactly that name` | Names must match exactly, including capitals and spaces: `A4 Revenue by segment`, `A4 Revenue by year`, `A4 Segment revenue`. Rename with **Edit chart properties** (chart list, pencil icon). |
| Check: chart not on the dashboard | Save the chart again with **Add to dashboard** `A4 Segment revenue`, or drag it in while editing the dashboard (right-hand list), then **Save**. |
| Check: `Superset refused your login token` | Open Superset in your browser and log in once, then run the check again. |
| The line chart shows one line | **Dimensions** is empty: add `market_segment`. |

## What you learned

- Dataset → chart → dashboard, the three layers of a BI tool.
- A metric is an aggregate; choosing `SUM` vs `AVG` vs `COUNT` changes the question.
- Read trends with care: a drop in the last period may just be an incomplete period.
- Dashboards run as the viewer: each person sees what their own access allows.

**You finished the analyst track.** Ideas for more: add a chart from A2's
`a2_late_by_shipmode`, or a filter on `market_segment` to your dashboard.
