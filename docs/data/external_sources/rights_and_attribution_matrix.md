# External sources (ML v2): rights, eligibility and attribution matrix

**Not legal advice and not a clearance.** Every source keeps `rights_status: not_reviewed`
(enforced by the registry validator). ML-use eligibility below is an **operational,
conservative restriction** recorded from observed evidence; it is machine-readable in
`configs/ml_rights_eligibility_v2.yaml` and enforced by the v2 partition rules, the pool
integrity check and the development loader. A person must review licences before any
release, publication or commercial use. Public availability is not treated as permission to
train models.

Evidence captured 2026-11-09 under `data/ml_v2/rights_evidence/20261109T155841Z/`
(git-ignored; `SHA256SUMS` inside) plus the `terms` files in each retrieval manifest.
**[observed]** = read in this project; **[unverified]** = not read.

## 1. ML-use eligibility (enforced)

| Source | ml_training | automated_evaluation | human_review_reference | Where its records go |
| --- | --- | --- | --- | --- |
| `aiddata` (+ Qi et al. labels) | permitted, pending review | permitted, pending review | permitted, pending review | v1 train/validation → v2 development; **consumed v1 tests excluded** |
| `iati_fcdo` | permitted, pending review | permitted, pending review | permitted, pending review | development pools (hash split) |
| `iati_ec_intpa` | permitted, pending review | permitted, pending review | permitted, pending review | development pools (hash split) |
| `worldbank_projects` | not applicable (by design) | permitted, pending review | permitted, pending review | sealed external test |
| `gcf_project_pages` | **restricted** | **restricted** | **restricted** | `restricted_reference/` only; no pool, no worksheet |
| `gcf_api_snapshot_backend` | **restricted** | **restricted** | **restricted** | never read (`V2Paths.readable` forbids `raw_db/`, `db/`) |
| any unlisted source | restricted (fail closed) | restricted | restricted | — |

## 2. Evidence

| Source | Licence / terms | robots.txt / AI signals | Attribution | Privacy |
| --- | --- | --- | --- | --- |
| `worldbank_projects` | The datasets-terms URL redirects to the general **WBG Terms & Conditions** (retrieved): API use to facilitate **non-commercial** uses; no commercial use or charging for derivatives; Data Catalog datasets have their own terms — whether that covers the Projects API is [unverified] | `search.worldbank.org/robots.txt` 404; `www.worldbank.org/robots.txt` has no AI rule or Content-Signal [observed] | "The World Bank Group authorizes the use of this material subject to the terms and conditions on its website" | staff names/IDs never requested |
| `gcf_project_pages` | GCF Terms and conditions (retrieved): private study, research, teaching and non-commercial use; no derivative works for commercial purposes without written consent; no AI-specific clause [observed] | **`www.greenclimate.fund/robots.txt`: `Content-Signal: ai-train=no, search=yes, ai-input=yes`** (sha256 `b99410ed…`) [observed]. The Task 006-ML registry note "robots.txt allows /" omitted this line; corrected. `data.greenclimate.fund/robots.txt` → 307 → 404 (none) | "First published by the Green Climate Fund" + link | named contacts never extracted |
| GCF API snapshot (backend, main checkout `data/raw_db/`) | Reported by the backend task to carry `ai-train=no` | — | — | never read by ML v2 |
| `iati_fcdo` | IATI Registry `license_id: uk-ogl` for 31/31 FCDO datasets [observed]; OGL v3 text not reviewed | `iati.fcdo.gov.uk/robots.txt` 403 (S3; none served); `iatiregistry.org/robots.txt` 404 [observed] | "Contains public sector information licensed under the Open Government Licence v3.0" + FCDO | contact elements not extracted |
| `iati_ec_intpa` | IATI Registry `license_id: other-at` (attribution) [observed]. Commission legal notice (retrieved with the data, sha256 `47cef732…`): EU-owned content is **CC BY 4.0** under Commission Decision 2011/833 unless otherwise indicated; credit and indication of changes required; third-party content may need separate clearance [observed]. A first retrieval got HTTP 429 for this page and 4 DNS failures; a second complete retrieval (0 failures) is the one used | `ec.europa.eu/robots.txt`: 201 `Disallow` rules for `*`, none matches `/international-partnerships/assets/iati/`; no Content-Signal [observed] | European Commission, per legal notice | contact elements not extracted |

## 3. Sources assessed but not acquired

| Candidate | Licence (registry) | Blocking evidence | Status |
| --- | --- | --- | --- |
| OECD CRS bulk files | OECD terms not read | Cloudflare challenge, HTTP 403 [observed] | manual download by a person |
| IATI Datastore v3 | — | subscription key required (HTTP 401) [observed] | needs key |
| Germany BMZ (DE-1) | `cc-by` | `teamwork.bmz.de/robots.txt`: `Disallow: /pub/` for `*`, where all files live [observed] | **not acquired automatically**; one probe file was fetched *before* robots.txt was read, then deleted unused |
| Australia DFAT (AU-5) | `other-at` | `data.gov.au/robots.txt`: `Disallow: /` [observed] | not acquired |
| JICA (XM-DAC-701-8) | `cc-by-sa` | reports **no** policy markers; titles largely Japanese [observed, probe] | no Rio labels; candidate pool only |
| Denmark, Ireland, New Zealand, Canada, Sida | `other-at` / `cc-zero` / `odc-pddl` / `other-at` / `other-pd` | robots not blocking (404/403/allowed) [observed]; Rio markers not yet checked | shortlist (see weak-sector plan) |

## 4. Other uses of restricted data

The ISO2→ISO3 country-code lookup used for linkage is read from the GCF ODL file. Only code
pairs (public standard identifiers) are used; no GCF text, label or record enters any pool,
worksheet or model input. A reviewer may decide to replace this lookup with a neutral source.

## Rules in force

1. Internal research use only; nothing leaves the machine; `data/ml_v2/` is git-ignored.
2. No public display of any v2-derived text until a person records a licence review.
3. A model trained on AidData + FCDO + EC text inherits all three sets of terms.
4. Reviewer worksheets contain source text and stay within the review team.
5. Changing any `restricted` entry requires written evidence and a committed config change.
