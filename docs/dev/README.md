# Internal docs

Working files for developing the engine. For the design docs, see
[the docs index](../README.md).

## Encoding cards

| Document | What it covers |
|---|---|
| [encoding_guide.md](encoding_guide.md) | How to encode a card: the workflow, the recipe, gotchas and rules notes. |
| [engine_seams.md](engine_seams.md) | The reusable encoding patterns, every decision kind, and the engine internals worth knowing. |
| [new_releases.md](new_releases.md) | Runbook for new cards, sets, keywords and decks. |
| [decks_status.md](decks_status.md) | Shippable decks, written by `python scripts/verify_encoding.py <slug> --graduate`. |

## Prompts and checklists

| Document | What it is |
|---|---|
| [encode_group_prompt.md](encode_group_prompt.md) | The standing prompt for encoding one card group. |
| [bug_triage_prompt.md](bug_triage_prompt.md) | The prompt for processing a bug report. |
| [reprint_escalation_prompt.md](reprint_escalation_prompt.md) | The prompt for an ambiguous reprint. |
| [ui_qa.md](ui_qa.md) | Manual web-UI QA checklist. |

## Plans and design notes

Each was written before the feature was built, and all have shipped.

| Document | Feature |
|---|---|
| [plans/bug_reporting_plan.md](plans/bug_reporting_plan.md) | In-app bug reports and threaded messaging |
| [plans/deck_builder_plan.md](plans/deck_builder_plan.md) | Per-user custom deck builder |
| [plans/tutorial_plan.md](plans/tutorial_plan.md) | In-app tutorial |
| [plans/reprint_duplicates_plan.md](plans/reprint_duplicates_plan.md) | Reprint aliasing: one encoding serving every printing |
| [plans/phase6b_llm_handoff.md](plans/phase6b_llm_handoff.md) | The LLM opponent |
| [design_when_you_draw_observer.md](design_when_you_draw_observer.md), [design_when_you_use_force_observer.md](design_when_you_use_force_observer.md) | Two framework changes made outside a card batch |

## Build logs

Kept for precedent: search them for a card id or primitive name.

| Document | What it records |
|---|---|
| [history/seams_log.md](history/seams_log.md) | Every engine primitive added, by encoding batch |
| [history/encoding_history.md](history/encoding_history.md) | The encoding campaign |
| [history/reprint_sweep_history.md](history/reprint_sweep_history.md) | The reprint sweep |
