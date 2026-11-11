# Route inventory

All routes below existed in Claude's recovered checkpoints and are retained.

| Route | Function | Live backend contracts |
| --- | --- | --- |
| `/` | Product story, compass hero, entry links, live funding/source/model previews | overview, funding-by-country, coverage, models/comparison |
| `/dashboard` | Compatibility redirect to Discover | No inventory dashboard rendered |
| `/projects` | Discover: keyword search, topic suggestions, country/topic filters, cards, shortlist actions; advanced drawer | filters, projects |
| `/projects/[id]` | Understand: project story, source climate evidence, selected funding facts; full evidence and provenance on demand | projects/{id}, decision/evidence/{id} |
| `/screening` | Analyze a Project: description, real signal and explanation; model/v1/benchmark details on demand | models, models/comparison, screening/text, screening/projects/{id} |
| `/analytics` | Countries, sectors, institutions, approved/disbursed, climate labels, profile and freshness | metrics, trends, funding-by-country/sector, institutions, approved-vs-disbursed, climate-distribution, country-profile/{iso3}, coverage |
| `/workspace` | My Shortlist: saved cards, explicit comparison, climate/funding differences, warnings and optional missing-information matrix | decision/compare |
| `/workspace?tab=prioritize` | Prioritize only saved projects with plain-language presets and optional weights/evidence | decision/prioritize |
| `/scenarios` | Secondary simulation: budget, shortlist, allocation method; optional constraints, objectives and source-reference entry | projects/{id}, decision/evidence/{id}, decision/methodology, decision/scenarios |
| `/challenges` | Honest future integration registry | No invented challenge result endpoints |

API paths use `/api/v1`, except unversioned health. Source-derived screens show
access notices. Errors retain backend codes and distinguish access denial,
validation, missing resources and unreachability. Empty queries show honest
empty states. Scenario controls reject malformed budget/constraint input; the
backend remains the authoritative validator.

Human review persistence is optional and not implemented in the frontend. The
current local demo has review writes disabled. No save or review button claims
that those operations are available. Public deployment is outside this task.
