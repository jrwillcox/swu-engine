# Documentation index

Start with the [top-level README](../README.md). This directory holds the deeper
design notes and the generated evidence behind the coverage and quality claims.

## Design & reference

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | The engine contract, state model, serialisation, and how to add a mechanic or encode a card. Start here to read the code. |
| [ability_framework.md](ability_framework.md) | The original design document for the declarative card DSL — ability types, targeting, conditions, durations, and the rules citations behind each. |
| [methodology.md](methodology.md) | How the encoding campaign was run: the offline planner, the escalation rule, and the automated release gate. |
| [pipeline.md](pipeline.md) | Building `data/swu.db` from the publisher's API, and refreshing it when a set releases. |
| [new_releases.md](new_releases.md) | Runbook for new cards, sets, keywords and decks — detection, implementation, and publishing hygiene. |
| [openapi.json](openapi.json) | Generated backend schema (`python -m swu.web --export-openapi docs/openapi.json`). |

## Feature design notes

Staged implementation plans, all of which shipped. Useful as worked examples of
how a feature was specified before it was built.

| Document | Feature |
|---|---|
| [bug_reporting_plan.md](bug_reporting_plan.md) | In-app bug reports and two-way threaded messaging |
| [deck_builder_plan.md](deck_builder_plan.md) | Per-user custom deck builder |
| [tutorial_plan.md](tutorial_plan.md) | In-app tutorial |
| [reprint_duplicates_plan.md](reprint_duplicates_plan.md) | Reprint aliasing — one encoding serving every printing |
| [phase6b_llm_handoff.md](phase6b_llm_handoff.md) | The LLM opponent |
| [design_when_you_draw_observer.md](design_when_you_draw_observer.md) · [design_when_you_use_force_observer.md](design_when_you_use_force_observer.md) | Two framework escalations — worked examples of the "don't jam it into a card batch" rule |

## Generated evidence

Regenerate rather than edit these.

| Document | Produced by |
|---|---|
| [coverage_report.md](coverage_report.md) | `python scripts/audit_coverage.py` — the 100% card-coverage number |
| [decks_status.md](decks_status.md) | `python scripts/verify_encoding.py <slug> --graduate` |
| `soak_*.md` / `soak_*.json` | `python scripts/soak.py` — measured soak campaigns per deck |
| [history/](history/) | Per-session encoding and reprint-sweep logs, kept for provenance |

## Operational

| Document | What it covers |
|---|---|
| [bug_triage_prompt.md](bug_triage_prompt.md) | The paste-ready prompt for processing a bug report out of band |
| [encode_group_prompt.md](encode_group_prompt.md) | The standing prompt for encoding one card group |
| [reprint_escalation_prompt.md](reprint_escalation_prompt.md) | Escalation prompt for an ambiguous reprint |
| [ui_qa.md](ui_qa.md) | Manual web-UI QA checklist |

> The *Star Wars: Unlimited* Comprehensive Rules are the rules authority for this
> engine, but they are the publisher's copyrighted document and are **not**
> redistributed here. Download the current version from
> <https://starwarsunlimited.com/rules>.
