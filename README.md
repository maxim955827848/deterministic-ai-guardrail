# deterministic-ai-guardrail

[![CI](https://github.com/maxim955827848/deterministic-ai-guardrail/actions/workflows/ci.yml/badge.svg)](https://github.com/maxim955827848/deterministic-ai-guardrail/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**Turn a non-deterministic LLM into a deterministic, schema-validated, auditable component.**

A small, dependency-light reference implementation of the boundary that sits
between a Large Language Model and your application state. The model proposes;
this layer disposes. Same state in, same state out — every time — regardless of
how creatively the model misbehaves.

```
        ┌──────────────┐   raw text   ┌───────── the guardrail ─────────┐
        │     LLM      │ ───────────► │  1. parse   2. validate   3. apply │ ──► trusted state
        │ (untrusted)  │              │   JSON       Pydantic     clamps    │      + audit log
        └──────────────┘              └────────────────────────────────────┘
```

---

## The problem: non-deterministic models corrupting deterministic systems

An LLM is a probabilistic text generator. Point it at a database, a state
machine, or a ledger and you have wired a random number generator directly into
your source of truth. In production the failure modes are not exotic — they are
routine:

| Failure shape | What the model does | What it costs you |
|---|---|---|
| **Malformed** | Wraps JSON in ```` ```json ````, buries it in prose, truncates mid-field | Parse exception → dropped turn, or worse, a partial write |
| **Missing** | Omits a required field | `KeyError` deep in your business logic |
| **Invalid enum** | Invents an action (`"self_destruct"`) that isn't in your set | Dispatch to a code path that doesn't exist |
| **Out of range** | Emits `confidence: 1.7`, `priority: 99` | Silent logic corruption downstream |
| **Exaggerated** | Proposes multiplying a value by 1,000,000 in one step | Runaway, un-auditable state |
| **Injected keys** | Adds `__proto__` / unexpected fields | Prototype pollution, un-vetted data persisted |

Catching these ad-hoc — a `try/except` here, a `.get()` with a default there —
scatters trust decisions across your codebase and guarantees that one of them is
missing. The result is intermittent, hard-to-reproduce state corruption that
only shows up under the exact model output nobody tested.

## The solution: a strict JSON boundary with a deterministic validation layer

Treat the model as an **untrusted narrator**: it may *propose* structure and
numbers, but it authors nothing your system is obliged to trust. Every proposal
crosses a single, explicit boundary made of three composable layers, and the
application — never the model — has the last word.

### Layer 1 — the JSON boundary (`parser.py`)

`safe_parse_json` deterministically recovers a JSON **object** from messy model
text and rejects anything genuinely unusable:

- strips ```` ```json ```` markdown fences,
- extracts the outermost `{ … }` slice from prose-wrapped replies,
- rejects top-level arrays/strings (structurally wrong even when valid JSON),
- rejects dangerous keys (`__proto__`, `constructor`, `prototype`) at every depth.

### Layer 2 — the strict schema (`schema.py`)

A **Pydantic v2** model with `extra="forbid"`. This is where *well-formedness* is
proven:

- **enum validation** — `action` and `status` are closed `Enum` sets; a
  hallucinated value is a hard rejection, not a dispatch,
- **numerical range constraints** — `confidence` is `Field(ge=0.0, le=1.0)`,
  `priority` is `Field(ge=1, le=5)`,
- **required fields have no defaults** — a missing field fails validation and
  triggers a retry; a genuinely quiet turn must still *say* it is quiet,
- **no extra keys** — unexpected fields (a common injection vector) are refused.

### Layer 3 — deterministic state application (`clamps.py`)

The schema proves a directive is well-formed. It cannot prove it is *reasonable*.
`apply_directive` is pure, deterministic, and contains **no model** — it decides
what actually happens to state:

- **key ownership** — deltas for keys the world doesn't own are skipped (no key
  injection),
- **type safety** — non-numeric deltas are dropped, never blindly coerced,
- **growth caps** — a single step may move a positive value by at most
  `MAX_GROWTH_FACTOR` (default 3×); the model cannot 1,000,000× a number,
- **hard range clamps** — every result is clamped into a fixed `[min, max]` band,
- **an audit trail** — every intervention is recorded as a structured
  `Intervention`, so you know exactly what the model tried and what the system
  did instead.

### The orchestrator (`wrapper.py`)

`GuardedAgent.step` composes the three layers behind one call and guarantees one
of exactly two outcomes — never a half-parsed dict, never an exception from a bad
model output:

1. a **validated** directive + a deterministically-guarded new state, or
2. an explicit, safe **fallback** directive (`HOLD` / `BLOCKED`) with state left
   untouched.

The retry policy: call → parse → validate; on failure, re-prompt **once** with an
explicit "return only valid JSON" instruction (models frequently self-correct);
on a second failure, stop calling the model and return the deterministic
fallback. Non-determinism is quarantined to the model call. Everything downstream
is deterministic.

---

## Design notes

- **Zero domain business logic.** The example domain is a generic *Agent* that
  proposes an `action`, a `status`, and numeric `resource_delta`s against a
  shared *State*. Replace `AgentDirective`, `CLAMP_RANGES`, and `MAX_GROWTH_FACTOR`
  with your own; the parser, wrapper, and retry/fallback machinery are unchanged.
- **Provider-agnostic.** The guardrail depends only on a tiny `LLMClient`
  protocol (`complete(system_prompt, user_prompt) -> str`). Drop in any
  OpenAI / Anthropic / OpenRouter client that satisfies it. The bundled
  `ScriptedLLM` replays canned responses so the whole suite runs with **no API
  key and no network**.
- **Purity where it counts.** Layers 1 and 3 are pure functions; Layer 2 is a
  declarative schema. The only non-determinism in the system is the model call
  itself, and it is boxed in on all sides.

## Project layout

```
deterministic-ai-guardrail/
├── src/guardrail/
│   ├── parser.py      # Layer 1 — safe_parse_json
│   ├── schema.py      # Layer 2 — AgentDirective (strict Pydantic v2)
│   ├── clamps.py      # Layer 3 — apply_directive (deterministic)
│   ├── llm.py         # LLMClient protocol + ScriptedLLM fake
│   └── wrapper.py     # GuardedAgent.step — retry + fallback orchestration
├── tests/             # pytest suite exercising all four failure shapes
├── examples/demo.py   # runnable, network-free tour
├── Dockerfile
├── pyproject.toml     # (requirements.txt also provided)
└── README.md
```

## Quick start

Requires **Python 3.11+**.

```bash
git clone https://github.com/maxim955827848/deterministic-ai-guardrail.git
cd deterministic-ai-guardrail

python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'          # or: pip install -r requirements.txt

python examples/demo.py          # see all five scenarios, no API key needed
```

### Minimal usage

```python
from guardrail import GuardedAgent, ScriptedLLM

# In real use, pass any client with a .complete(system, user) -> str method.
client = ScriptedLLM(['{"action": "advance", "status": "active", '
                      '"summary": "on track", "confidence": 0.9, '
                      '"priority": 2, "resource_delta": {"energy": -5}}'])

agent = GuardedAgent(client)
state = {"energy": 50.0, "reputation": 40.0, "credits": 1000.0, "throughput": 100.0}

result = agent.step(state, "Decide the agent's next move.")

print(result.directive.action)     # AgentAction.ADVANCE  (validated enum)
print(result.state)                # deterministically-updated state
print(result.used_fallback)        # False
for i in result.apply_result.interventions:
    print(i.kind, i.key)           # audit trail of any corrections
```

## Running the tests

### With pytest (local)

```bash
pip install -e '.[dev]'
pytest
```

The suite (30 tests) is organized by layer and covers all four failure shapes:

- `tests/test_parser.py` — fences, prose-wrapping, non-objects, dangerous keys
- `tests/test_schema.py` — missing fields, invalid enums, out-of-range, extra keys
- `tests/test_clamps.py` — unknown keys, non-numeric, growth caps, range clamps, determinism
- `tests/test_wrapper.py` — happy path, retry recovery, deterministic fallback, no-mutation

### With Docker

```bash
docker build -t deterministic-ai-guardrail .
docker run --rm deterministic-ai-guardrail                 # runs pytest (default CMD)
docker run --rm deterministic-ai-guardrail python examples/demo.py
```

## License

MIT — see [LICENSE](LICENSE).
