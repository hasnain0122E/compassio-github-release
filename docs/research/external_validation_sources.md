# External validation sources: feasibility assessment (Task 004.5)

Checked on 2026-11-09 by automated reading of the official pages and metadata endpoints listed.
**No new source data was downloaded or registered.** Only small metadata and single-record
responses were read to establish structure.

- **[verified]** means observed in this session.
- **[not verified]** means general background knowledge that a person must confirm before any
  reliance.

Absent climate markers are never treated as negative labels.

## Summary

| Source | Project text | Climate labels | Who labels | Rio-compatible? | Access | Best use |
| --- | --- | --- | --- | --- | --- | --- |
| A. OECD CRS / Rio markers | Project-level CRS records with short and long descriptions [not verified here] | Rio markers: climate mitigation and adaptation, 0/1/2 [not verified here] | The **reporting donor** (self-assessed) | Same 0/1/2 scheme as the research labels; different annotators and conventions | SDMX API (`sdmx.oecd.org`); the Data Explorer link is JS-only | **Most promising external label source**, after verification |
| B. IATI Datastore | Activity titles and descriptions [verified on our ADB file] | `policy-marker` (vocabularies 1 = OECD DAC incl. climate, 99 = publisher's own) | The **publisher** | Only vocabulary-1 markers with significance; ADB uses vocabulary 99 (Task 002) | API key required [verified]; JSON/CSV/XML | Project discovery; labels only where publishers report DAC markers |
| C. GCF approved funding proposals | Full proposal PDFs per project [verified on FP085's page] | GCF `Theme` (mitigation / adaptation / cross-cutting) | GCF | **Not** Rio: every GCF project is climate-dedicated, so there are no negatives | Public project pages; PDF documents | Positive-only, adaptation-rich external evaluation text; approval dates |
| D. World Bank projects and climate co-benefits | PDO and abstract per project [verified via API] | Climate co-benefit shares under the joint MDB methodology [not verified as project-level fields in the API] | World Bank (MDB methodology) | No: a co-benefit share is not a Rio score | Projects API, open, no key [verified] | Project discovery; negative-control and adaptation **candidates**, subject to human labelling |

## A. OECD Rio-marker / CRS data

- **Link given:** https://data-explorer.oecd.org/s/4bb. Automated reading returned an empty
  JavaScript shell [verified], so its content could not be read.
- **SDMX catalogue** (`https://sdmx.oecd.org/public/rest/dataflow/all/all/latest`, 10.4 MB
  metadata) [verified] lists:
  - `OECD.DCD.FSD / DSD_RIOMRKR@DF_RIOMARKERS` v1.7, "RioMarkers: Aid (ODA) activities targeting
    global environmental objectives";
  - `OECD.DCD.FSD / DSD_CRS@DF_CRS` v1.7, "CRS: Creditor Reporting System (flows)".
- **Not determined:** the structure query for these flows returned no readable dimension list,
  so it is **unverified** whether the SDMX flows are project-level or carry description text.
- **Background [not verified]:**
  - The OECD publishes project-level CRS microdata (bulk files) with titles, short and long
    descriptions, and `ClimateMitigation` / `ClimateAdaptation` markers, scored 0/1/2 by the
    reporting donor.
  - Coverage is official donors (DAC members and some others), roughly 2000 onwards.
  - The current OECD data licence must be read from the OECD terms page.
- **Compatibility:** the same 0/1/2 Rio semantics as Qi et al. However, labels are **donor
  self-reported**, which is known to be inconsistent across donors. China is not a CRS reporter,
  so there is **no direct overlap** with our AidData records [not verified].
- **Identifiers:** CRS has a `CRSid` and donor project numbers [not verified].
- **Assessment:** best candidate for an **external evaluation** with Rio-compatible labels. It
  is unsuitable as training data without a separate decision, because the labels come from
  different annotators.
- **Manual retrieval steps:**
  1. Open the OECD Data Explorer in a browser and locate the CRS / RioMarkers dataset.
  2. Download the project-level microdata for a bounded slice (e.g. recipient Pakistan, a few
     years).
  3. Record the URL, date and licence text.
  4. Register the file under `data/raw/oecd_crs/` with `compassio-manifest write`.

## B. IATI Datastore

- **Verified from the reference page:**
  - The Datastore v3 "provides access to data published by organisations on their resources and
    results".
  - Queries can filter "on all elements and attributes contained in the Standard".
  - Output is JSON, CSV or XML, and an Excel-friendly CSV, "without pagination".
  - An **API key is required** (sign-up linked).
  - The page shows only "Copyright IATI 2026"; licences are set **per publisher** inside each
    activity file.
- **We already hold one IATI file:** ADB Pakistan, 193 activities. Its `policy-marker`s use
  vocabulary 99 (ADB priorities) with **no significance** (Task 002), so ADB IATI provides no
  Rio labels.
- **Overlap:** Chinese lenders largely do not publish to IATI [not verified]. There is overlap
  with existing ADB, GCF and other sources for the same projects.
- **Identifier:** the `iati-identifier`, which is reliable.
- **Assessment:** useful for **project discovery** across publishers. It is useful for labels
  only where a publisher reports DAC vocabulary-1 climate markers with significance, and that
  must be verified per publisher.
- **Manual steps:** register for an API key, then query `recipient-country=PK` with
  `policy-marker` vocabulary 1. Treat any licence as per-publisher.

## C. GCF approved funding proposals

- **The resources page** lists templates and annexes only (funding proposal template v4.0,
  Annexes 1–17, Annual Performance Report and Project Completion Report templates). **No
  approved proposals are linked there** [verified].
- **Project pages carry the documents** [verified on FP085, Green BRT Karachi]:
  - date approved 20 Oct 2018 (board meeting B.21);
  - GCF financing USD 49,000,000 (loan 37.2 M, grant 11.8 M);
  - co-financing USD 534,500,000;
  - total project value USD 584 M;
  - theme "Mitigation";
  - documents: the **approved funding proposal** (28 Nov 2018, ADB), 2024 and 2025 Annual
    Performance Reports, gender assessment and action plan, and an ESS report.
- **Labels:** GCF `Theme`, assigned by GCF. It is **not** a Rio score and has no negative class.
- **Text date:** the proposal date is shown (e.g. 28 Nov 2018). These are **contemporaneous
  proposal texts**, exactly what the retrospective-text risk (R02) needs.
- **Licence:** only "© 2026 GCF" and a "Terms and conditions" link, whose content was not read
  [verified]. Rights are unknown.
- **Overlap:** the 379 GCF projects in `gcf_projects` share the FP/SAP identifier. Every GCF
  project is outside the research (AidData) population, so there is no training overlap.
- **Assessment:**
  - **External evaluation** of recall on adaptation and non-energy proposals (positives only;
    precision cannot be measured from GCF alone);
  - **approval dates** for the portfolio (risk R10).
- **Manual steps:**
  1. For selected FP/SAP codes, open `https://www.greenclimate.fund/project/<code>`.
  2. Download the approved funding proposal PDF.
  3. Record the URL, date and terms.
  4. Register it.

  Text extraction from PDFs needs a reviewed extraction step, because no PDF dependency is
  installed.

## D. World Bank development finance with climate co-benefits

- **Programme page** [verified]:
  - "We follow a strict methodology, shared by all Multilateral Development Banks";
  - sub-project-level disclosure effective 1 April 2025;
  - no dataset link or licence on that page.
- **Projects API** [verified]:
  - `https://search.worldbank.org/api/v3/projects?format=json&countrycode_exact=PK&fl=*`
    returned **640 Pakistan projects**, with no key;
  - one record had 59 fields, including `pdo` (project development objective), a
    `project_abstract`, `boardapprovaldate`, sector and `theme` fields, and commitment amounts.
- **No explicit climate co-benefit field** appeared in that record. Whether `theme` codes encode
  climate adaptation and mitigation was not examined.
- **Labels:** MDB climate co-benefit **shares** (the percentage of finance counted as climate)
  are a financing-accounting concept, **not** a Rio objective score, and are not interchangeable
  with the research labels.
- **Licence [not verified]:** World Bank datasets are commonly published under CC BY 4.0. Confirm
  this on the World Bank Terms of Use or the dataset page.
- **Assessment:**
  - **Project discovery** for Pakistan (PDO and abstract are proposal-stage text);
  - a source of **candidate** adaptation projects and **negative controls** (e.g. health,
    education, governance), which must be labelled by human reviewers under the Rio
    definitions.
- **Manual or automated steps:** the API is open. A bounded pull of Pakistan projects, and
  registering it, needs approval of the licence and a decision on scope, so it was not done in
  this task.

## Implications

1. **No external source gives drop-in labels in the research's annotation scheme.** OECD CRS
   comes closest (the same 0/1/2 Rio semantics, different annotators). GCF and World Bank need
   **human labelling** under the paper's definitions to serve as an evaluation set.
2. **Contemporaneous text is available** (GCF proposals, World Bank PDOs and abstracts). This is
   the evidence the retrospective-text risk calls for.
3. **More labelled training data is not the immediate need.** An **independent, adaptation-rich
   evaluation set** comes first, to measure the gap honestly
   (`external_validation_protocol.md`).
