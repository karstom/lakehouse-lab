#!/usr/bin/env python3
"""Reference solution for A5 (test-only; never copied into homes). Runs inside the user's
workspace, as the user: reads the NFL sample through Trino, computes the era
difference-in-differences, its naive p-value and a stratified permutation test, and publishes
the five numbers to lakehouse.dbt_<you>.a5_spread_test. Safe to run twice.

  python solve.py [<module dir>]
"""
import math

import lakehouse
import numpy as np
import pandas as pd

ONE_SCORE = 8
DRAWS = 1000

FLAGS = """
SELECT g.game_id, g.season, g.spread, f.margin, f.home_possession, f.game_seconds_remaining,
       CASE WHEN f.penalized_side = 'defense' THEN 1 ELSE 0 END AS on_defense
FROM lakehouse.samples.nfl_q4_flags f
JOIN lakehouse.samples.nfl_games g ON g.game_id = f.game_id
WHERE f.penalty_class = 'discretionary'
"""
GAMES = """
SELECT game_id, season, spread,
       ntile(10) OVER (PARTITION BY season ORDER BY elo_diff, game_id) AS strength_decile
FROM lakehouse.samples.nfl_games
"""


def frame(cur, sql):
    cur.execute(sql)
    rows = cur.fetchall()
    return pd.DataFrame(rows, columns=[d[0] for d in cur.description])


def did(flags: pd.DataFrame, spread: pd.Series) -> tuple[float, float]:
    d = flags.assign(spread=spread.to_numpy())
    d["lcm"] = d.margin + d.spread
    d = d[(d.game_seconds_remaining <= 600) & (d.margin.abs() <= 10) & (d.spread != 0)
          & (d.lcm.abs() <= ONE_SCORE) & (d.lcm != 0) & (d.season != 2018)]
    d["post"] = (d.season >= 2019).astype(int)
    d["needs_cover"] = np.where(d.home_possession == 1, d.lcm < 0, d.lcm > 0).astype(int)
    cell = d.groupby(["post", "needs_cover"]).on_defense.agg(["mean", "size"])
    p = cell["mean"]
    stat = (p[1, 1] - p[1, 0]) - (p[0, 1] - p[0, 0])
    se = math.sqrt(sum(cell.loc[k, "mean"] * (1 - cell.loc[k, "mean"]) / cell.loc[k, "size"] for k in cell.index))
    return float(stat), math.erfc(abs(stat / se) / math.sqrt(2))


def main():
    cur = lakehouse.trino_connection().cursor()
    flags = frame(cur, FLAGS)
    games = frame(cur, GAMES).set_index("game_id")
    observed, naive_p = did(flags, flags.game_id.map(games.spread))
    rng = np.random.default_rng(42)
    sims = []
    for _ in range(DRAWS):
        shuffled = games.groupby(["season", "strength_decile"]).spread.transform(
            lambda s: rng.permutation(s.to_numpy()))
        sims.append(did(flags, flags.game_id.map(shuffled))[0])
    sims = np.array(sims)
    results = {"observed_did": observed, "naive_p": naive_p, "perm_mean": float(sims.mean()),
               "perm_p": float(np.mean(np.abs(sims) >= abs(observed))), "draws": float(DRAWS)}
    print(results)
    schema = f"dbt_{lakehouse.whoami().lower()}"
    values = ", ".join(f"('{k}', CAST({v!r} AS double))" for k, v in results.items())
    for sql in (f"CREATE SCHEMA IF NOT EXISTS lakehouse.{schema}",
                f"CREATE OR REPLACE TABLE lakehouse.{schema}.a5_spread_test AS "
                f"SELECT * FROM (VALUES {values}) AS t(statistic, value)"):
        cur.execute(sql)
        cur.fetchall()
    assert results["perm_p"] > results["naive_p"], "the lesson's point did not reproduce"


if __name__ == "__main__":
    main()
