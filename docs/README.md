# Documentation

Start with the [top-level README](../README.md).

## Design

| Document | What it covers |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | The engine contract, state model and serialisation, and how to add a keyword, action or zone. Start here to read the code. |
| [ability_framework.md](ability_framework.md) | The design of the declarative card DSL: ability types, targeting, conditions, durations, and the rules behind each. |
| [methodology.md](methodology.md) | How the encoding campaign was run: the offline planner, the escalation rule and the automated release gate. |

## Reference

| Document | What it covers |
|---|---|
| [bots.md](bots.md) | Difficulty levels, the heuristic and LLM bots, and how to measure a bot change. |
| [testing.md](testing.md) | Test tiers, the invariant oracle, soak campaigns and regression tests. |
| [pipeline.md](pipeline.md) | Building `data/swu.db` from the publisher's API, and refreshing it for a new set. |
| [openapi.json](openapi.json) | Generated backend schema (`python -m swu.web --export-openapi docs/openapi.json`). |

## Evidence

| Document | What it shows |
|---|---|
| [coverage_report.md](coverage_report.md) | 100% card coverage, from `python scripts/audit_coverage.py`. Regenerate, don't edit. |
| [soak_results.md](soak_results.md) | 15,100 bot-vs-bot games with zero failures. |

## Internal

[dev/](dev/README.md) holds the working files: the card-encoding guide, LLM
prompts, runbooks, shipped feature plans and build logs.

> The *Star Wars: Unlimited* Comprehensive Rules are the rules authority for this
> engine, but they are the publisher's copyrighted document and are **not**
> redistributed here. Download the current version from
> <https://starwarsunlimited.com/rules>.
