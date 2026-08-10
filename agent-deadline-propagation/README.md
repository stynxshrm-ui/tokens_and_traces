# agent-deadline-propagation
---

## Watch the video:

[Video Link](https://youtu.be/GIE7sBtbI10)

---
A minimal reference implementation of deadline propagation for LLM agent
tool chains — an absolute-epoch budget threaded through every nested
call, instead of per-call timeouts that don't know about each other.

**The problem:** every individual tool call can finish inside its own
timeout, and the agent can still finish long after the point anyone was
still waiting. In this example, a retry loop on a degraded dependency
pushes a 6.24s clean-path request out to 17.04s — 12.04s of it spent
after the user was gone.

**The fix isn't "detect disconnect and cancel."** That signal doesn't
exist for most agent call shapes (server-to-server calls, queued jobs,
async bots). It's a budget set proactively at request time, checked
before every new unit of work starts.

## Files

| File | Shows |
|---|---|
| `common.py` | `DeadlineContext`, tool mocks, cost math — single source of truth |
| `01_clean.py` | Baseline, no deadline |
| `02_broken.py` | Retry loop added, no budget awareness — the bug |
| `03_instrumented.py` | Deadline added — diagnoses the same bug live |
| `04_fixed.py` | Production shape: fails loud and closed, blocks new work, finishes in-flight calls |

## Run it

```bash
DEMO=1 python3 01_clean.py
DEMO=1 python3 02_broken.py
DEMO=1 python3 03_instrumented.py
DEMO=1 python3 04_fixed.py
```

No API key needed — `DEMO=1` runs deterministic mocks. Every number
printed is computed by the code, not hand-typed.

## Assumptions this depends on

Two numbers drive the whole example, both named and adjustable in one
place — see `README_INTERNAL.md` / code comments for the full list:

- User abandonment patience: `common.py` → `user_abandonment_time()`
- Deadline budget: `03_instrumented.py` / `04_fixed.py` → `DEADLINE_BUDGET_S`

Replace both with your own measured numbers before trusting this shape
in production.

## License

MIT.
