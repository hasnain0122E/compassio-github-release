# Source rights matrix (Task 004.5)

**This is not legal advice and not a clearance.** Every source remains `rights_status:
not_reviewed` in `data/manifests/source_manifest.json` until a person completes a legal review
and records evidence. Public access to a file is not permission to redistribute it.

Evidence was checked on 2026-11-09:

- **[verified]** means the licence or terms text was read from the publisher.
- **[unverified]** means it could not be read or was not found.

| Source | Licence / terms evidence | Internal research use | Model training | Public display of project facts | Redistribution of full records | Attribution required | Unresolved |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `research_paper` (Figshare 30015124 v1) | **CC0** per the Figshare API record [verified]. Article CC BY 4.0. | Likely permitted (CC0) | Likely permitted | Likely permitted | Likely permitted **for the annotation layer**, but the text fields are AidData's (see next row) | Cite Qi et al. 2026 (scholarly norm) | Whether CC0 can cover AidData-derived text and fields |
| `aiddata` (GCDF 3.0) | **ODC-By 1.0** in the workbook's `License` sheet [verified]. The web page states no licence and names the official citations [verified]. | Permitted under ODC-By (verify) | Permitted under ODC-By (verify) | Permitted with attribution (verify) | ODC-By allows redistribution with attribution and the licence notice kept intact (verify) | **Yes**: AidData attribution, the licence notice and the official citation | Formal confirmation of ODC-By scope; check that the ODC-By version on the website is current |
| `adb_pakistan` (IATI XML) | Not readable: the page returned 403, and the data portal API sits behind a bot challenge [unverified]. IATI files carry no licence element in our file (Task 002). | Unknown | Unknown | Unknown | **Do not redistribute** | Likely (ADB) | ADB data terms; IATI publisher licence |
| `gcf_projects`, `gcf_readiness`, `gcf_countries` | GCF Terms and conditions [verified]: use for "private study, research and teaching purposes" and non-commercial purposes; **commercial use, redistribution or derivatives for commercial purposes need prior written consent**; third-party material needs its owner's permission | Permitted (research) | Arguably research or non-commercial; confirm | Non-commercial display with attribution; **commercial use needs consent** | Not for commercial purposes without consent | **"First published by the Green Climate Fund"** plus a link to greenclimate.fund; no implied endorsement; no logo | Whether Compassio is commercial (e.g. hackathon prize or product); the exports were rewritten by openpyxl (provenance) |
| `climate_funds_update` | Dashboard shows "© Copyright Climate Funds Update 2026"; no licence or reuse terms found [verified absence on that page] | Unknown (generally tolerated for research) | Unknown | Unknown | **Do not redistribute** | Likely (CFU, ODI / HBS) | Terms of use; who authored this copy (author metadata names an individual) |
| `climate_project_explorer` | Not checked [unverified] | Unknown | Unknown | Unknown | **Do not redistribute** | Unknown | Terms of use; rights in the linked documents, which belong to the funds |
| `gcf_historical` (archive `mjcszv9t52-1`) | Origin unconfirmed; the Mendeley Data API returned 404 for that id [unverified] | Unknown | Unknown | Unknown | **Do not redistribute** | Unknown | Identify the dataset and its licence |

## Rules in force until review

1. **Internal research use only.** No raw or processed dataset leaves the machine.
   `data/raw`, `data/processed`, `artifacts/` and `experiments/` are git-ignored, which is
   verified each task.
2. **Public display is blocked** for every source until `rights_status` is updated with
   evidence. The manifest model rejects a decision without `rights_evidence`.
3. **Attribution set prepared** for when display is cleared:
   - AidData: ODC-By plus the official citation;
   - Qi et al. 2026;
   - "First published by the Green Climate Fund" plus a link;
   - Climate Funds Update and ADB as their terms require.
4. **Model artifacts** are trained on research_paper and AidData text, so they inherit those
   terms. Do not distribute the model publicly until both are confirmed.

**Compassio is not legally cleared for public redistribution of any source.**
