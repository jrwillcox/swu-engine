# How this was built

This project was written with heavy use of [Claude Code](https://claude.com/claude-code).
That is worth stating plainly, because the interesting engineering problem here
was not "can an LLM write a card ability" — it obviously can — but **how do you
drive several thousand small, mechanical changes into one codebase without the
quality silently degrading?**

The answer is the machinery in this repository. It is checked in rather than
hidden, because it is the part that actually took design work.

## The problem

*Star Wars: Unlimited* has ~2,600 cards. Most carry rules text. Encoding them is
a long tail of small tasks that are individually easy and collectively enormous —
exactly the shape of work where an agent is useful and exactly the shape where
unsupervised output rots: a card "works" in isolation, quietly breaks an
interaction three sets away, and nobody notices for weeks.

So the work needed three properties:

1. **Bounded units.** Something small enough to verify completely in one sitting.
2. **A definition of done that a machine checks**, not a human's impression.
3. **A gate that refuses to ship** when the definition isn't met.

## 1. A deterministic, offline planner

`scripts/plan_encoding.py` reads the card database, finds everything not yet
playable, and clusters it into dependency-ordered **groups** of ~5–7 cards sharing
a theme (direct damage, card advantage, combat tricks…). It is a plain Python
program — no model involved — so the plan is reproducible and reviewable before
any code is written.

Each group gets a file (`encoding/<set>/group_NN_<theme>.md`) containing, per card:
its printed text, a mechanical analysis, **the existing primitives that should
suffice**, and explicit acceptance criteria. `encoding/<set>/MANIFEST.md` is the
resulting board.

That last point matters most. The prompt for each batch says *"these primitives
should be enough"* — so if they are not, that is a signal, not an inconvenience.

## 2. An escalation rule instead of a workaround

The failure mode to avoid is an agent inventing a bespoke one-off mechanism to
make one card pass. The standing instruction (the [escalation rule](dev/engine_seams.md#the-escalation-rule)) is the opposite:
if a card genuinely needs a new engine primitive, **stop and flag it** for a
dedicated design session rather than jamming it into a card batch.

The result is visible in the numbers: 2,176 cards are declarations composed from a
shared vocabulary, and **zero** use the `escape_hatch=True` opt-out into bespoke
logic. The vocabulary grew deliberately, in its own sessions, with its own tests.

## 3. A release gate that can say no

`scripts/verify_encoding.py --graduate` is the definition of done, and it is not
advisory. For a deck to be marked shippable it must clear, in order:

- **100% of its cards classified playable** by `scripts/audit_coverage.py` — an
  independent audit that re-derives the answer from the database and the registry,
  rather than trusting anything the encoding session claimed;
- **the fast test tier green** (~5,600 tests);
- **the medium tier green** — soak campaigns plus a Hypothesis stateful machine;
- **a deck-specific soak** — hundreds of full games with the invariant oracle
  (`src/swu/engine/invariants.py`) run after every single action.

Only then does it self-register the deck as playable. Measured evidence from those
runs is summarised in [`docs/soak_results.md`](soak_results.md).

## 4. An oracle strong enough to be worth passing

A gate is only as good as its checks. The invariant module asserts things a card
author would not think to test: card conservation by instance identity, zone and
tag consistency, decision-stack wellformedness, semantic modifier expiry — and
**hidden-information leak detection**, which serialises a player's redacted view
and string-scans it to prove the opponent's hand never appears.

`tests/test_hypothesis_engine.py` then drives whole games one legal action at a
time, running that same oracle after every move and shrinking any failure to a
minimal reproducer. The campaign runner waits for a bad state; this searches for
one.

## What I would keep

The planner and the gate, without hesitation. Once "done" is machine-checked and
the gate can refuse, the throughput of an agent stops being frightening — a bad
batch fails loudly and cheaply instead of landing quietly.

The honest caveat is that this only works because the domain has a crisp oracle. A
card game has rules; you can assert conservation and legality. Work without that
property would need a different answer, and I would not claim this one transfers
unchanged.

## The artifacts, if you want to read them

| Path | What it is |
|---|---|
| `scripts/plan_encoding.py` | The offline planner |
| `scripts/next_group.py` | Stateless walker over the remaining queue |
| `scripts/verify_encoding.py` | Per-group verification and the `--graduate` gate |
| `scripts/audit_coverage.py` | The independent coverage audit |
| `encoding/*/MANIFEST.md` | Per-set boards with per-card acceptance criteria |
| `CLAUDE.md` | The short brief every agent session loads: commands, workflow, and the rules that are easy to break |
| `docs/dev/encoding_guide.md`, `docs/dev/engine_seams.md` | The card recipe, and the catalogue of reusable patterns and decision kinds |
| `.claude/skills/encode-next/` | The batch workflow itself |
| `docs/soak_results.md` | Measured soak evidence per campaign |
