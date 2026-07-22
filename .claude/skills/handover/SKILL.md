---
name: handover
description: End-of-session handover. Surveys what actually happened (git log, uncommitted changes, in-flight work), filters aggressively to keep only the 5% that's load-bearing for the next session, updates HANDOVER.md in the repo with persistent notes worth carrying forward, asks before committing anything, and prints a tight structured note (Shipped / In flight / Watch-outs / Open questions) readable in under 30 seconds. Invoke when the user types /handover or asks to wrap up / hand off the session.
---

<!-- הועתק מ-sessions-archive/toolkit/process/skills/handover/SKILL.md@9801386 -->

# /handover — End-of-session handover

The user is wrapping up. Produce a short, high-signal note that future-them (or a cold-reading Claude) can absorb in under 30 seconds. **Filter aggressively.** Most of a session is forgettable execution — keep only what's load-bearing.

## Environment constraint

This repo is used exclusively via **Claude Code on the web** (GitHub integration). There is no terminal access for the user. `~/.claude/` does NOT persist between sessions — everything durable must be committed into the repo.

## Step 1 — Survey what actually happened

Run these in parallel:

- `git log --since="10 hours ago" --oneline` (commits this session; widen to 24h if empty)
- `git status --short` (uncommitted changes)
- `git diff --stat && git diff --stat --cached` (scope of uncommitted work)

Do **not** dump raw output to the user. This is reconnaissance — synthesize it.

## Step 2 — Identify load-bearing items

Keep:
- Decisions that constrain future work ("we chose X because Y").
- Discovered constraints, gotchas, broken assumptions, surprising state.
- Half-finished work with enough context for a cold reader to resume.
- Open questions only the user can answer.

Drop:
- Routine execution (files read, greps run, tests that passed).
- Anything fully captured by a commit message.
- Anything the next session would rediscover in 30 seconds.

When in doubt: **leave it out.**

## Step 3 — Update HANDOVER.md (selectively)

`HANDOVER.md` in the repo root is the persistent memory file. Update it **only** if this session produced something durable — a stable constraint, a recurring footgun, a convention the next session needs.

- Do **not** log daily activity, per-session progress, or routine execution.
- Use `Edit` to surgically update an existing entry; only add a new entry if it's genuinely new and durable.
- If the project's `PROCESS.md` or `LESSONS.md` is a better home for an item, **ask** the user rather than touching it silently.
- If nothing meets the bar, **don't touch the file**. Say so in the final note.
- After updating, propose a commit for the change.

## Step 4 — Uncommitted changes

If `git status` shows uncommitted work worth saving:

- Summarize what's uncommitted (one sentence).
- **Ask** the user whether to commit, and propose a commit message.
- Do not commit silently. Do not use `git add -A` without confirmation.
- If the user says no, mention it in "In flight."

## Step 5 — Print the handover note

Output exactly this structure. Keep it tight — if a section is empty, write `—`. Target: ~15 lines total.

```
## Handover — <YYYY-MM-DD HH:MM>

### Shipped
- <short-sha> <commit subject>   (or: deploy, merged PR, etc.)

### In flight
- <what's half-done> — <enough context to resume cold>

### Watch-outs
- <gotcha, surprising state, broken assumption, footgun>

### Open questions
- <question only the user can answer>

Memory: <"updated HANDOVER.md: <one line>" | "no changes — nothing durable">
Uncommitted: <"none" | "<N> files — <decision taken>">
```

## Calibration

- If the session was 90% execution with no durable decisions, the note should be **mostly dashes**. Correct, not a failure.
- More than ~15 lines = not filtered enough. Cut.
- Never narrate the survey. Just produce the note.
