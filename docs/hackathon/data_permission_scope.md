# Data permission scope for BATTLEVERSE 2026 (Task 009)

**Not legal advice and not a licence clearance.** This page records an event-specific
authorization *as the team reported it* and the narrow technical policy built on it. Nothing
here changes any source's `rights_status`; all sources remain `not_reviewed`
(`data/manifests/source_manifest.json`, unchanged and hash-pinned).

## 1. The reported authorization

| Item | Recorded value |
| --- | --- |
| Event | BATTLEVERSE 2026 (Battle of Intelligence) |
| Who reports it | The Compassio team (user statement in the Task 009 request, 2026-11-10) |
| What was reported | The organizers **verbally confirmed** that the extracted datasets may be used for this hackathon, and that they accept responsibility for this event authorization |
| Evidence status | `user_reported_verbal_confirmation`: reported by the team, not independently verified. No written statement is on file (`evidence_reference: null`) |
| Event dates | **Unknown, not set** (`valid_from: null`, `valid_until: null`). No date has been assumed |
| Recorded in | `configs/event_data_authorizations.yaml` (`battleverse_2026`) |

The authorization is treated as **asserted, event-specific permission from the organizers**.
The organizers cannot grant third-party licences on behalf of AidData, the Green Climate Fund,
Climate Funds Update, ADB or the Climate Project Explorer. Their terms still apply
(`docs/data/source_rights_matrix.md`).

**Written confirmation is not a blocker** for local development or the local demo. If the
organizers later provide a written statement (email or published rules), record a reference to
it (title and date, not personal data) in `evidence_reference` and set
`evidence_status: written_evidence_on_file`. When the actual event dates are known, set
`valid_from` / `valid_until`; the policy then serves no source data outside that window.

## 2. What the event policy permits and what it does not

| Use | Status under the event policy |
| --- | --- |
| Running Compassio on the team's own machine and showing it to judges and mentors at the venue | **Permitted** (`hackathon_event` mode, loopback clients only) |
| ML v1 / ML v2 screening during the local demonstration | Permitted with the existing Task 007 safeguards (ML v2 only with `COMPASSIO_ML_V2_LOCAL_DEMO=true`, `environment=development`) |
| Showing source records, amounts and analytics on screen during judging | Permitted, with source attribution shown (section 4) |
| Public deployment (internet-reachable server, public URL) | **Not permitted.** `environment=production` always forces `public` mode (403 for source data). Event mode refuses non-loopback clients |
| Publishing screenshots, videos or slides containing record-level data outside the event | **Not covered.** Use aggregate, attributed figures only, and check each source's terms first |
| Redistributing the database, raw files, processed data or model artifacts | **Not permitted.** `data/`, `models/` stay git-ignored; do not upload them |
| Commercial use (product, paid service, investor material) | **Not covered.** GCF terms require prior written consent for commercial use; CFU, ADB and Climate Project Explorer terms are unverified |
| Sending source records to external AI services | **Not permitted** without each provider's and source's permission (unchanged Task 006-ML rule) |
| Using GCF API / GCF page data for ML training | **Not permitted** (robots `ai-train=no`; `configs/ml_rights_eligibility_v2.yaml` unchanged) |
| Serving `gcf_historical` (restricted internal staging) | **Never** (excluded in every mode, including event mode) |

## 3. Technical policy (`COMPASSIO_SOURCE_DATA_ACCESS=hackathon_event`)

Implemented in `compassio_api.services.access` and `compassio_api.core.config`, tested in
`tests/api/test_event_access.py`.

1. **Opt-in and named.** It requires `COMPASSIO_EVENT_AUTHORIZATION=battleverse_2026`, which
   must match an entry in `configs/event_data_authorizations.yaml`. A missing or unknown entry
   stops the API at startup with a configuration error.
2. **Never in production.** `environment=production` forces `public` mode whatever is set.
3. **Time-boxed when dates are set.** If `valid_from` / `valid_until` are set, the policy
   serves no source data outside that window (403 `source_rights_not_cleared`). Both are
   currently `null` because the event dates are unknown; `null` means "not set", never an
   assumed date.
4. **Source-scoped.** Only the sources listed in the entry are served. `restricted_internal`
   sources (`gcf_historical`) are excluded even if listed.
5. **Loopback only.** Requests to `/api/v1/*` from non-loopback clients get 403
   `event_access_local_only`, except the metadata routes `/api/v1/meta`, `/api/v1/sources` and
   `/api/v1/decision/methodology`. Run uvicorn with `--host 127.0.0.1`.
6. **Honest labelling.** Every source-derived response carries
   `access.mode = "hackathon_event"`, the header `X-Compassio-Data-Access: hackathon_event`
   and a notice stating the scope and that sources are not licence-cleared.
7. **Nothing else changes.** `rights_status`, `rights_evidence`, the manifests, the ML rights
   config, the finance contract and the restricted-source exclusion are untouched.

### Which existing controls blocked event use

| Control | Blocked event use? | Decision |
| --- | --- | --- |
| `public` mode returns 403 for all source data | Yes, by design | Kept: correct for any public deployment |
| `local_development` mode | Technically allows local use, but its notice says "do not expose, screenshot for publication", which conflicts with showing the product to judges | Kept unchanged for development; event mode adds an accurate, event-specific notice and stricter guards (loopback, time box, source list) |
| Screening needs a local mode | Yes in `public` | Event mode counts as a local mode for inference (loopback-only); ML v2 still needs its own demo flag |
| `gcf_historical` restriction | No (not needed for the demo) | Kept |
| ML rights eligibility (only AidData records are model input) | No | Kept |

## 4. Attribution to show in the UI (Task 010)

Every screen that shows source data must show its source and, at least once per page, these
attributions (`docs/data/source_rights_matrix.md`):

- **AidData:** "AidData's Global Chinese Development Finance Dataset, Version 3.0", the
  official citation and the ODC-By 1.0 notice.
- **Qi et al. 2026** (research annotations): scholarly citation.
- **Green Climate Fund:** "First published by the Green Climate Fund" with a link to
  greenclimate.fund; no GCF logo; no implied endorsement.
- **Climate Funds Update** (ODI / Heinrich Böll Stiftung) and **ADB (IATI)**: name the
  publisher; terms unverified.
- **Climate Project Explorer:** name the publisher; terms unverified.

`GET /api/v1/sources` returns each source's publisher, reference URL, version, rights status
and licence notes for this purpose.
