# A5 tutor notes: a result that isn't

## Learning objectives

The learner can:

1. turn a verbal idea ("the team that needs to cover") into a precise SQL definition, and say
   which plays it includes and why;
2. compute a difference-in-differences from a grouped table and read it as percentage points;
3. explain why a formula p-value assumes the null is "difference = 0", and why that can be
   wrong when the sample definition itself depends on the variable under test;
4. build a stratified permutation test (shuffle the spread across games within season ×
   strength decile, recompute everything that depends on it) and read its mean and p-value;
5. state the conclusion carefully: "the data do not show an effect at this power", not "there
   is no effect".

## Common mistakes and what to say

| Symptom | Likely cause | Hint (do not give the code) |
| --- | --- | --- |
| `observed_did` about 14, not 0.14 | percentages | "Is your share a fraction or a percentage? The check wants fractions." |
| `observed_did` a little off | pushes kept, 2018 kept, or `<` vs `<=` in the window | "Walk through the step-2 list one condition at a time. Which rows have `margin + spread = 0`?" |
| `perm_mean` near 0 | shuffled across all games, or shuffled the flags | "What does one shuffle keep fixed? Season and strength should stay with the game; only the spread moves." |
| `perm_mean` equals `observed_did` | the window or `offense_needs_cover` still uses the real spread | "After shuffling, which columns did you recompute? Both the window and needs-cover depend on the spread." |
| `perm_p` far from the check's | too few draws, or one-sided | "How many shuffles? Are you comparing absolute values?" |
| Checkpoint: table missing | wrong schema or name | "Run `SELECT current_user` and look at step 8's table name." |

## Hints, in order of strength

1. "What would the statistic look like if referees could not see the spread at all?"
2. "You can simulate that world: keep every game exactly as it was, but give it another
   game's spread from the same season and strength band."
3. "For each shuffle, run the same function you used for the real `did`."

## Questions to ask the learner

- Why shuffle within season and strength decile instead of across every game?
- The shuffled worlds have no betting effect, yet their average `did` is about 0.10. Where
  does that 0.10 come from?
- What would you need to see to believe officials really do lean toward the cover?

## Keep in mind

Do not imply that officials are corrupt or that the result proves they are honest. The lesson
is about the method: an apparently significant effect that mostly comes from how the sample
is built.
