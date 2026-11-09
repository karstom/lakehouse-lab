#!/usr/bin/env python3
"""A5 checkpoint: your table lakehouse.dbt_<you>.a5_spread_test holds the right answers.

Checks the OUTCOME (the published table, read through Trino as you), not your notebook. The
expected numbers are computed from lakehouse.samples at check time, not stored here: the
observed difference-in-differences and its naive p-value exactly, and the permutation mean
and p-value from a fresh permutation run of the checkpoint's own (they are random, so the
check allows for sampling noise).

  python3 checkpoint.py [--json]    check        python3 checkpoint.py --reset    start over
"""
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "_shared"))
import trackkit as tk  # noqa: E402

TABLE = "a5_spread_test"
STATS = ["observed_did", "naive_p", "perm_mean", "perm_p", "draws"]
ONE_SCORE = 8

FLAGS = """
SELECT g.game_id, g.season, g.spread, f.margin, f.home_possession, f.game_seconds_remaining,
       CASE WHEN f.penalized_side = 'defense' THEN 1 ELSE 0 END AS on_defense
FROM lakehouse.samples.nfl_q4_flags f
JOIN lakehouse.samples.nfl_games g ON g.game_id = f.game_id
WHERE f.penalty_class = 'discretionary'
"""
GAMES = """
SELECT game_id, season, spread, ntile(10) OVER (PARTITION BY season ORDER BY elo_diff, game_id)
FROM lakehouse.samples.nfl_games
"""


def did_stat(spread, margin, home_pos, secs, era, on_def):
    """Difference-in-differences of P(flag on defense) between flags where the offense needs
    the cover and where it does not, post era (2019-2026) minus pre era (2010-2017). Returns
    (did, naive two-sided p). Works on numpy arrays."""
    import numpy as np
    lcm = margin + spread
    keep = ((secs <= 600) & (np.abs(margin) <= 10) & (spread != 0) & (np.abs(lcm) <= ONE_SCORE)
            & (lcm != 0) & (era >= 0))
    onc = np.where(home_pos == 1, lcm < 0, lcm > 0)[keep].astype(int)
    e, y = era[keep], on_def[keep]
    p, n = {}, {}
    for a in (0, 1):
        for b in (0, 1):
            m = (e == a) & (onc == b)
            n[a, b] = int(m.sum())
            p[a, b] = float(y[m].mean()) if n[a, b] else float("nan")
    did = (p[1, 1] - p[1, 0]) - (p[0, 1] - p[0, 0])
    se = math.sqrt(sum(p[k] * (1 - p[k]) / n[k] for k in p))
    naive = math.erfc(abs(did / se) / math.sqrt(2))
    return did, naive


def reference(draws=1000, seed=7):
    import numpy as np
    _, flags = tk.query(FLAGS)
    _, games = tk.query(GAMES)
    gidx = {g[0]: i for i, g in enumerate(games)}
    gs = np.array([float(g[2]) for g in games])
    strata = {}
    for i, g in enumerate(games):
        strata.setdefault((g[1], g[3]), []).append(i)
    fi = np.array([gidx[r[0]] for r in flags])
    season = np.array([r[1] for r in flags])
    era = np.where(season <= 2017, 0, np.where(season >= 2019, 1, -1))
    args = (np.array([r[3] for r in flags], float), np.array([r[4] for r in flags]),
            np.array([r[5] for r in flags], float), era, np.array([r[6] for r in flags], float))
    obs, naive = did_stat(gs[fi], *args)
    rng = np.random.default_rng(seed)
    sims = []
    for _ in range(draws):
        perm = gs.copy()
        for idx in strata.values():
            perm[idx] = gs[rng.permutation(idx)]
        sims.append(did_stat(perm[fi], *args)[0])
    sims = np.array(sims)
    return {"observed_did": obs, "naive_p": naive, "perm_mean": float(sims.mean()),
            "perm_sd": float(sims.std()), "perm_p": float(np.mean(np.abs(sims) >= abs(obs)))}


def checks(ck):
    schema = tk.user_schema()
    fq = f"lakehouse.{schema}.{TABLE}"
    if not ck.check(f"table {fq} exists", tk.table_type(schema, TABLE) is not None,
                    f"no table named {TABLE} in {schema}",
                    "step 8: publish your results with CREATE OR REPLACE TABLE ... AS SELECT * FROM "
                    f"(VALUES ...) in a %%sql trino cell. Check the name: {TABLE}"):
        return
    cols = [c for c, _ in tk.columns(schema, TABLE)]
    if not ck.check("it has the columns statistic, value", cols == ["statistic", "value"],
                    f"found columns: {', '.join(cols) or '(none)'}",
                    "step 8: two columns, AS t(statistic, value)"):
        return
    _, rows = tk.query(f"SELECT statistic, value FROM {fq}")
    got = {r[0]: (float(r[1]) if r[1] is not None else None) for r in rows}
    missing = [s for s in STATS if got.get(s) is None]
    if not ck.check(f"one row for each of {', '.join(STATS)}", not missing,
                    f"missing: {', '.join(missing)}", "step 8 lists the five rows and their names"):
        return
    want = reference()
    ck.check("observed_did is the difference-in-differences of step 4",
             abs(got["observed_did"] - want["observed_did"]) < 1e-6,
             f"yours {got['observed_did']:.4f}, expected {want['observed_did']:.4f}",
             "step 4: (post, needs cover - post, not) - (pre, needs cover - pre, not), as a fraction "
             "(0.14), not a percentage. Check the window in step 2: last 600 seconds, |margin| <= 10, "
             "spread live within 8, no pick'em, and drop pushes (live_cover_margin = 0)")
    ck.check("naive_p is the two-sided p-value of step 5",
             abs(got["naive_p"] - want["naive_p"]) < 1e-4,
             f"yours {got['naive_p']:.5f}, expected {want['naive_p']:.5f}",
             "step 5: z = did / se with se = sqrt(sum of p(1-p)/n over the four cells); "
             "p = erfc(|z| / sqrt(2))")
    ck.check("draws is at least 500", got["draws"] >= 500, f"draws = {got['draws']:.0f}",
             "step 6: run at least 500 shuffles (1000 in the lesson)")
    tol_mean = 4 * want["perm_sd"] / math.sqrt(max(got["draws"], 1)) + 0.002
    ck.check("perm_mean matches the permutation null", abs(got["perm_mean"] - want["perm_mean"]) <= tol_mean,
             f"yours {got['perm_mean']:.4f}, expected about {want['perm_mean']:.4f}",
             "step 6: shuffle the spread across games WITHIN season x strength decile, then recompute "
             "the statistic with the shuffled spread (needs-cover and the window both depend on it)")
    ck.check("perm_p matches the permutation p-value", abs(got["perm_p"] - want["perm_p"]) <= 0.07,
             f"yours {got['perm_p']:.3f}, expected about {want['perm_p']:.3f}",
             "step 7: the share of shuffles whose |statistic| is at least |observed_did|")


def reset():
    return [tk.drop_own(TABLE)]


if __name__ == "__main__":
    sys.exit(tk.Checkpoint("A5", "a permutation test").run(checks, reset))
