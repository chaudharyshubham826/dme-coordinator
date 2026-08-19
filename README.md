# DME Coordinator

Automated DME back-end coordination. Runs Eleanor Martinez's wheelchair case without a care advocate — calls suppliers, chases the PCP order, escalates if it hits a wall.

Built as a take-home for a care navigation company. 3-hour time box.

## Setup

```bash
make install
```

This creates a venv, installs deps, and drops a `.env` file. Add your Groq API key to it — free at [console.groq.com](https://console.groq.com), no credit card.

```bash
make run
```

Expect 1–3 minutes depending on how many suppliers get called before one accepts.

## What you'll see

The coordinator thinks out loud before each action. Phone calls print as transcripts. Outcomes are randomized — each run is genuinely different.

Most runs (~67%) end with a confirmed supplier and signed order. About 1 in 3 hits some kind of escalation. Run it a couple times to see both.

## Models

- Coordinator: `qwen/qwen3.6-27b` via Groq (tool use + reasoning)
- Phone dialogue: same model, but only for the two interesting cases — supplier accepting and PCP signing the order. Everything else (no-answer, declines, voicemail) is pre-scripted. No point burning API calls on "no, we're full."

Override via `COORDINATOR_MODEL` / `PHONE_MODEL` in `.env`.

---

See `WRITEUP.md` for why things are built the way they are.
