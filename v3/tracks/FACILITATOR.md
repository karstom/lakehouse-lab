# Facilitator guide: beginner sessions

The tracks are only done when real beginners can use them. This guide is for the person who
runs those sessions (the lab owner). Exit criterion 3 of Phase 4:

> At least **two real beginners** complete **module 1 of each track** (E1 and A1) **without
> help**.

A session takes about 2 hours per person: 10 minutes of setup, up to 60 minutes per module,
10 minutes for the feedback form. Run one person at a time, so you can watch closely.

## Who counts as a beginner

- **Analyst track (A1):** someone who has written little or no SQL. Spreadsheet users are
  ideal.
- **Engineer track (E1):** someone who can read basic Python (a loop, a function) but has not
  used Spark, Iceberg or a data lake.
- Not: anyone who helped build the lab, or who has read the lessons before.

The same person can do both modules, A1 first.

## Before the session

1. **A lab on profile `engineer` or `full`** (E1 needs Spark). `./lab status` shows every
   service healthy. `./lab test` passes (check 17 proves E1 and A1 work end to end).
2. **An account per participant**, created by you in Keycloak (`auth.<domain>`, realm
   `lakehouse`, Users → Add user; set a temporary password). Put them in group **`analyst`**
   for A1 and **`engineer`** for E1. Access is granted *only* through these groups; never
   share the seeded test accounts (alice, eddie, anna, victor).
3. **Their browser trusts the lab CA** (`./lab ca` prints how). Do this for them before the
   session: fighting certificate warnings is not what we are testing.
4. **A fresh start.** If the account was used before, open a terminal in their workspace and
   run `lab-tracks reset A1 --yes` and `lab-tracks reset E1 --yes`.
5. Print or open a copy of `FEEDBACK.md` for them, and one for your own notes.

## What to tell the participant (read it out)

> "We are testing the lessons, not you. Please think aloud: say what you are looking for and
> what you expect to happen. I will not help unless you are completely stuck, because every
> time you get stuck the lesson has a problem we need to find. You can stop at any time.
> You're done with a module when `lab-tracks check` says PASSED."

Then give them only:
- the URL `https://jupyter.<domain>/`, their username and password;
- "Open the `tracks` folder and start with the analyst track, module A1."

## During the session

- **Watch and write, don't talk.** Note the time and what happened at each moment of
  hesitation: which step, what they tried, what they expected.
- **What counts as help:** any hint about what to do, where to look or what a message means.
  Pointing at the screen is help. Answering "is this right?" is help.
- **Not help:** "Please keep thinking aloud", "Take your time", restarting a crashed browser,
  or fixing a lab outage (record it as an infrastructure incident, not a lesson problem).
- **If they are stuck for 5 minutes**, ask "What are you trying to do right now?" (not help).
  **At 10 minutes**, give the smallest hint that unblocks them and **mark the module as
  "completed with help"**. Write down the hint word for word.
- Let them run `lab-tracks check` as often as they like. Note each FAIL and whether its hint
  was enough.

## After the session

1. Give them `FEEDBACK.md` and 10 minutes. Stay out of the room if you can.
2. Fill in the facilitator part of the form yourself, straight away.
3. From the participant's terminal, save the evidence: `cat ~/.lab-progress.json`.
4. Store the forms without names (P1, P2, ...) in a private place. Do not commit them to the
   public repository.

## Counting the result

| Outcome for a module | Counts toward exit 3? |
|---|---|
| PASSED, no help, within 60 minutes | **yes** |
| PASSED, no help, over 60 minutes | yes, and the lesson needs shortening |
| PASSED with help | no |
| Not finished | no |

Exit 3 is met when **two participants each** have a "yes" for **E1 and for A1**. After each
session, fix what blocked people (lesson text, hints, checkpoint messages) before the next
one; a fix to a lesson restarts the count for that module only if it changes the steps, not
if it only clarifies wording.

## Resetting between participants

Each participant has their own account and workspace, so nothing carries over. To reuse an
account, run `lab-tracks reset <ID> --yes` in its workspace. `lab reset` (whole lab) is not
needed and deletes everyone's work. `lab-tracks reset` moves the previous participant's edited
files to `~/.lakehouse/tracks-backup/` in that home instead of deleting them; delete that
folder too if the next person should not see them.
