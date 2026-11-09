# A5 · A result that isn't: testing with permutations

**Time:** about 55 minutes · **Profile:** any · **You need:** A1 and A2 (SQL over the lab's
tables, JupySQL and DuckDB in a notebook).

## Goal

Sports bettors talk about referees "protecting the number": calls that seem to help the team
that needs a few points to cover the betting spread. Since 2018, legal betting has grown
fast in the US. Did NFL officiating start leaning toward the team that needs to cover?

You will find a striking number that says yes, with a p-value of about 0.001. Then you will
test it properly and watch most of it disappear. By the end, your table
`lakehouse.dbt_<you>.a5_spread_test` holds five numbers that tell that story.

You will learn:

- how to turn a betting idea ("needs to cover") into a SQL definition you can check;
- how to compute a difference-in-differences from a `GROUP BY`;
- why a standard p-value can be badly wrong when the **sample itself depends on the variable
  you are testing**;
- how to build a **permutation test**: shuffle the thing you care about, keep everything
  else, and see what "no effect" really looks like.

## The data (read this first, 5 minutes)

Two tables in `lakehouse.samples`, derived from [nflverse](https://github.com/nflverse)
data (CC-BY-4.0; see `bootstrap/sample_data/nfl/README.md` in the lab repository):

- **`nfl_games`**: one row per game, 2010–2026, with the closing **`spread`** from the home
  team's point of view (**negative = home team favored**: `-3` means the home team was
  expected to win by 3) and `elo_diff`, a pre-game strength rating gap (home minus away).
- **`nfl_q4_flags`**: one row per penalty flag thrown in a fourth quarter, with the score
  margin before the play (`margin`, home minus away), who had the ball (`home_possession`),
  the clock (`game_seconds_remaining`), whether the foul was a **`discretionary`** judgment
  call (holding, pass interference, roughness…) or **`mechanical`** (false start, offside…),
  and who was flagged (`penalized_side`: `offense` or `defense`).

**Covering.** The home team covers if its final margin plus the spread is positive. During
the game, `live_cover_margin = margin + spread` says who is covering right now: positive, the
home team is; negative, the away team is.

**Needs the cover.** On a play, the team that is *not* covering needs a score to cover. We say
the spread is "live" if one score (8 points) could change who covers:
`abs(live_cover_margin) <= 8`.

**The question, as a number.** A flag on the defense helps the offense. If officials lean
toward the team that needs the cover, flags should land on the defense more often when the
*offense* needs the cover, and more so after 2018 than before.

## Steps

Open `a5_permutation.ipynb` in this folder. Each step below has a cell there.

### 1. Look at the tables

```sql
%%sql trino
SELECT * FROM lakehouse.samples.nfl_games LIMIT 5
```

Do the same for `nfl_q4_flags`. Find a game you remember and check its `spread`.

### 2. Define the window and "needs the cover" in SQL

Keep discretionary flags in close, late situations where the spread is live:

- the last 10 minutes: `game_seconds_remaining <= 600`;
- a close game: `abs(margin) <= 10`;
- a real favorite: `spread <> 0` (no pick'em games);
- the spread is live: `abs(margin + spread) <= 8`, and not a push: `margin + spread <> 0`;
- eras: **pre** = seasons 2010–2017, **post** = 2019–2026 (2018 is left out: betting became
  legal during it).

The offense needs the cover when it is the team not covering:

```sql
CASE WHEN home_possession = 1 THEN (margin + spread) < 0
     ELSE (margin + spread) > 0 END AS offense_needs_cover
```

### 3. One number per cell

Group by era and `offense_needs_cover`; compute the share of flags on the defense
(`avg(CASE WHEN penalized_side = 'defense' THEN 1 ELSE 0 END)`) and the count. You get four
rows. Expected (rounded): about 2,300 flags in all.

### 4. The difference-in-differences

```
did = (post, needs cover − post, not)  −  (pre, needs cover − pre, not)
```

as a fraction (0.14 means 14 percentage points). Expected: about **0.14**. Officials seem to
have swung 14 points toward the team that needs to cover. That would be a scandal.

### 5. The naive p-value

Treat the four cells as independent proportions: `se = sqrt(Σ p(1 − p) / n)` over the four
cells, `z = did / se`, and the two-sided p-value `p = erfc(|z| / sqrt(2))` (`math.erfc`).
Expected: about **0.001**. Very "significant".

### 6. What does "no effect" look like? Shuffle the spreads

Here is the catch. The spread decides *which plays are in your sample* (the window) and *who
"needs" the cover*. Games with big and small spreads differ in many ways (team strength,
how close games stay, what kind of fouls happen late), and those differences changed between
eras for reasons that have nothing to do with betting. A formula p-value assumes "no effect"
means `did = 0`. Maybe it doesn't.

Find out by **breaking the link** between the spread and the game, and nothing else:

1. Put the games in strata of the same season and similar strength:
   `ntile(10) OVER (PARTITION BY season ORDER BY elo_diff, game_id) AS strength_decile`.
2. Within each stratum, shuffle the spreads across games (a random permutation).
3. Recompute `did` with the shuffled spread (the window and `offense_needs_cover` both change).
4. Repeat 1,000 times and keep every `did`.

In a shuffled world, the spread cannot influence any call. The 1,000 numbers are what "no
effect" looks like **for this data and this definition**. Compute their mean (`perm_mean`).
Expected: about **0.10**. "No effect" is not zero here: most of the 0.14 is built into the
way the sample is defined.

### 7. The permutation p-value

`perm_p` = the share of shuffles whose `|did|` is at least your observed `|did|`.
Expected: about **0.13**. Not significant: the data do not show officials favoring the team
that needs to cover.

### 8. Publish your five numbers

```sql
%%sql trino
CREATE OR REPLACE TABLE lakehouse.dbt_<you>.a5_spread_test AS
SELECT * FROM (VALUES
  ('observed_did', CAST(0.1397 AS double)),
  ('naive_p',      CAST(0.0007 AS double)),
  ('perm_mean',    CAST(0.1043 AS double)),
  ('perm_p',       CAST(0.13   AS double)),
  ('draws',        CAST(1000   AS double))
) AS t(statistic, value)
```

with your own numbers (the notebook builds this statement for you from your variables).

### 9. Check your work

```
lab-tracks check A5
```

The check recomputes `observed_did` and `naive_p` exactly, and runs its own permutation test to
compare your `perm_mean` and `perm_p` (they are random, so it allows for noise).

## Common mistakes

- **A percentage instead of a fraction**: `did` is 0.14, not 14.
- **Forgetting pushes**: drop `margin + spread = 0` (nobody needs the cover).
- **Shuffling flags instead of games**: the spread belongs to a game; shuffle it across games,
  then join it back to every flag of that game.
- **Shuffling across all games**: shuffle within season × strength decile. Across everything,
  you would also scramble team strength and era, which is not the "no betting effect" world.
- **Not recomputing the window**: a shuffled spread changes which plays are "live". Apply the
  whole step-2 definition again for every shuffle.

## Start again

`lab-tracks reset A5` drops your table `lakehouse.dbt_<you>.a5_spread_test` and restores this
folder's files.

## Going further

This lesson is a small version of a pre-registered study, which used logistic models with
game-state controls, referee fixed effects, a mechanical-foul placebo and the same
permutation idea. It reached the same conclusion: the apparent post-2018 lean is mostly
structural, and no pre-registered test survived the correction for multiple testing.
