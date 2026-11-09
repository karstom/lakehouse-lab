# NFL sample data

Loaded by `bootstrap/samples.py` into `lakehouse.samples.nfl_games` and `lakehouse.samples.nfl_q4_flags`. Used by the analyst module A5 (`v3/tracks/analyst/A5-permutation-test`).

## Source and license

Derived from **[nflverse](https://github.com/nflverse/nflverse-data)** play-by-play and schedule data, which nflverse publishes under the **[Creative Commons Attribution 4.0 International license (CC-BY-4.0)](https://creativecommons.org/licenses/by/4.0/)**. These files are shared under the same license. Please keep this attribution when you reuse them.

Changes from the nflverse data (all made by the [NFL spread-bias study](https://github.com/karstom) pipeline):

- one row per penalty flag, parsed from the play descriptions, so declined, offsetting and picked-up flags are included (nflverse's penalty columns hold only the enforced penalty);
- each penalty type classified as `discretionary`, `mechanical` or `other`;
- the closing spread converted to the home team's perspective, negative when the home team is favored (nflverse's `spread_line` is positive when the home team is favored);
- a pre-game team-strength rating (`elo_diff`) computed from game results only, with no betting input;
- only fourth-quarter flags on plays from scrimmage, seasons 2010–2026 (2026 through week 9).

Referee names are not included. No betting-market data other than nflverse's closing spread and total is included.

## `nfl_games` (one row per game, 4,498 rows)

| Column | Meaning |
| --- | --- |
| `game_id` | nflverse game id, e.g. `2015_01_PIT_NE` |
| `season`, `week`, `game_type`, `gameday` | when it was played; `game_type` is `REG` or a playoff round |
| `home_team`, `away_team` | team codes as of that season (`OAK`, `SD`, `STL` before relocation) |
| `home_score`, `away_score` | final score |
| `spread` | closing spread, **home perspective, negative = home favored** (home −3 = home favored by 3) |
| `total` | closing over/under |
| `elo_diff` | home minus away pre-game Elo rating (results only, no betting input) |
| `roof` | `outdoors`, `dome`, `closed`, `open` |
| `neutral_site`, `div_game` | 1/0 |

## `nfl_q4_flags` (one row per penalty flag, 14,598 rows)

| Column | Meaning |
| --- | --- |
| `game_id`, `play_id`, `flag_seq` | which flag (a play can have more than one) |
| `margin` | home score minus away score **before** the play |
| `home_possession` | 1 if the home team had the ball |
| `game_seconds_remaining` | seconds left in the game at the snap |
| `down`, `ydstogo` | down and distance |
| `penalty_type` | e.g. `Defensive Holding`, `False Start` |
| `penalty_class` | `discretionary` (a judgment call), `mechanical` (procedural, hard to miss or invent) or `other` |
| `penalized_side` | `offense` or `defense` |
| `penalty_status` | `accepted`, `declined`, `offsetting` or `picked_up` |
