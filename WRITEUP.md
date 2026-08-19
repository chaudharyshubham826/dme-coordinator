# Writeup

## What I built and why in that order

The problem is coordination across three parties with bad handoffs. The naive implementation is a state machine: call supplier → if yes, get order → if signed, done. That's not a system, it's a script. It breaks the first time a supplier says something unexpected.

What actually eats time is the failure modes — no answer, Medicare census full, order sitting unsigned for three days, supplier agrees and then goes quiet. That's where a care advocate's judgment lives. So that's what I built: the thing that handles those failures and decides when to keep pushing vs. when to stop and get a human.

I deliberately didn't build delivery scheduling, patient SMS, or fax integration. Those are straightforward API calls once you have a confirmed supplier and a signed order. They're not the hard part.

**What's here:**
- Coordinator agent (Qwen via Groq) that works the case via tool calls — reads case state, decides what to do next, adapts to what each call returns
- Phone simulation with randomized outcomes — ~67% happy path, ~20% supplier exhaustion, ~13% PCP issues
- Pre-scripted dialogue for boring outcomes (no-answer, declines), LLM-generated for the interesting ones (supplier accepts, order gets signed)
- Escalation with full context handoff when the system genuinely can't proceed

## Architecture and stack choices

Python + Groq SDK. No framework, no database.

**The coordination loop:**

The coordinator is an LLM agent with 8 tools: get case, get supplier list, call supplier, call PCP, log note, notify patient, mark complete, escalate. It runs in a loop until it either resolves the case or hits a wall. It's not following a flowchart — it reads what happened and decides what to do. If a supplier says something outside the scripted scenarios, it handles it. A state machine wouldn't.

**Where I deliberately didn't use AI:**

This was the interesting design question. Things that are NOT AI:

- *Outcome randomization* — `random.choices()` with probability weights. The acceptance rate of Medicare suppliers is a business parameter, not a judgment call. Code is cheaper and auditable.
- *Case state* — typed dataclass. If the LLM tracked case state in its context it would drift. A `@dataclass` doesn't.
- *Tool routing* — plain `if/elif`. The model decides what to call; dispatching it is just plumbing.
- *Loop bounds* — `MAX_SUPPLIER_CALLS = 12`, `MAX_PCP_CALLS = 3`. These are policy decisions, not things an LLM should decide dynamically.
- *Most phone dialogue* — pre-scripted for no-answer, voicemail, and declines. There's no value in calling an LLM to say "we're not accepting Medicare patients." Only the accept and order-signed cases get LLM calls, because those are the conversations worth making natural.

**Two-tier phone simulation:**

Originally I was going to LLM-generate every call. I cut that when I realized it was slow and added no value for the boring outcomes. Now it's maybe 2 LLM calls for phone dialogue per run instead of 15. The coordinator makes ~5-8 calls. Total is manageable.

## What I cut and why

| Cut | Why |
|-----|-----|
| Twilio real calls | The actual automation gap. Biggest "day 2" item. |
| Retry scheduler | "Call Lakeshore back at 2pm" needs a job queue. The logic exists; the infra doesn't. |
| Persistent state | Nothing needs to survive the process for a demo. SQLite if this were real. |
| Multi-case | One coordinator, one case. Parallelism is a queue-and-worker problem. |
| Patient SMS | One Twilio line once the case resolves. Cut to keep deps minimal. |
| Web UI | Not what this demo is about. |

## What's next

**Day 2:** Real phone calls via Twilio Voice + Deepgram transcription. That's the actual product — right now we're simulating the most important part. Also: retry scheduling. No-answers need to come back into the queue at a later time, not just be skipped.

**Two weeks:** Supplier success-rate memory (call the ones that actually deliver, not just the ones that answer). PCP portal detection — if a practice uses Epic or Athena, go through the portal instead of calling. Multi-case queue with a real worker pool. Patient SMS at each milestone. Analytics on what's actually causing escalations.

The ordering matters: real calls first because everything else is better with real data. Retry scheduling second because it's the biggest source of dropped cases. Memory and analytics after that, once there's data to learn from.
