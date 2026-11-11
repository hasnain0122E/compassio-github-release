# Demo API examples (real responses, Task 009)

Captured on 2026-11-11 with `uv run python scripts/smoke_api.py --base http://127.0.0.1:8000 --capture <file>` against the promoted `main` (`5a7a08d`), started with the official `scripts/start_api.ps1` (`hackathon_event` mode, ML v2 authorized local demo, models preloaded, one worker, `UV_OFFLINE=1`). Database SHA-256 `d2b39add...d385`. All 25 smoke checks passed. (The same journey also passed on a clean checkout containing only the five runtime artifacts; see `docs/hackathon/local_demo_runbook.md`.)

**Trimmed for documentation:** strings are cut at 110 characters, lists show 2 items plus a count, and nesting below depth 4 is elided. The live API returns full responses. Source records appear only to illustrate the contract: every source is `not_reviewed`, so do not republish them (`docs/hackathon/data_permission_scope.md`). The screening text is example text written for the demo. Timings are single wall-clock samples from the smoke client.

## 1. Health

`GET /health` -> **200** (107.9 ms)

Response (trimmed):

```json
{
 "status": "ok",
 "service": "compassio-api",
 "version": "0.1.0"
}
```

## 2. Models and operational mode

`GET /api/v1/models` -> **200** (49.8 ms)

Response (trimmed):

```json
{
 "models": [
  {
   "model_key": "ml_v2",
   "engine_label": "Compassio Climate Intelligence — ML v2",
   "model_version": "ml2fast_49317056_c76204127550",
   "status": "development_candidate",
   "artifact_sha256": "654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574",
   "model_fingerprint": "c76204127550fb299c11704de61bd07cce3eae6635193e608a42897c5f995ad2",
   "threshold": 0.44474326842740053,
   "representation": "character TF-IDF 2-5-grams (char_wb) + logistic regression (C=2, balanced)",
   "training_data": "FCDO + EC IATI activities with publisher-reported Rio markers (v2 TRAIN, 13,317)",
   "intended_use": "Authorized local demonstration and internal research screening with human review.",
   "evaluation": {
    "kind": "development_validation_used_for_selection",
    "population": "2,550 eligible FCDO + EC v2 development-validation records (827 positive)",
    "headline": "{...}",
    "document": "docs/research/model_v2/development_champion_card.md",
    "independent_generalization_evidence": false
   },
   "artifact_present": true,
   "selectable_now": true
  },
  {
   "model_key": "ml_v1",
   "engine_label": "Compassio Climate Relevance Classifier v1 — MVP Research Screening",
   "model_version": "compassio-ccrc-1.0.0-mvp-research-screening",
   "status": "trusted_research_release",
   "artifact_sha256": "53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656",
   "model_fingerprint": "3023fe3d148b605c3ed9079c93f07296193fd2d8d5f77b8a82a163e58ccdc495",
   "threshold": 0.4740212723792222,
   "representation": "word TF-IDF 1-2-grams + logistic regression (C=16, balanced)",
   "training_data": "AidData GCDF 3.0 records with Qi et al. 2026 Rio annotations (primary TRAIN, 14,654)",
   "intended_use": "Human-reviewed research screening; reliable mainly for energy-sector text.",
   "evaluation": {
    "kind": "one_shot_frozen_test",
    "population": "AidData primary group-disjoint test (3,142 records, 202 positive)",
    "headline": "{...}",
    "document": "docs/research/task005_model_card.md",
    "independent_generalization_evidence": true
   },
   "artifact_present": true,
   "selectable_now": true
  }
 ],
 "operational": {
  "inference_authorized": true,
  "mode": "authorized_local_demo",
  "default_model": "ml_v2",
  "fallback_model": "ml_v1",
  "review_writes_enabled": false,
  "notice": "Authorized local demonstration: ML v2 (development candidate) is the default engine; ML v1 (trusted researc..."
 },
 "prediction_scope": "Climate-relevance screening of project text only. Compassio does not predict funding approval, financial re..."
}
```

## 3. Search (PAK, hydropower)

`GET /api/v1/projects?q=hydropower&country=PAK&page_size=5` -> **200** (63.6 ms)

Response (trimmed):

```json
{
 "items": [
  {
   "id": "adb_pakistan:XM-DAC-46004-34339-023-LN2286",
   "source_id": "adb_pakistan",
   "source_project_id": "XM-DAC-46004-34339-023-LN2286",
   "record_level": "adb_financing_instrument",
   "title": "Renewable Energy Development Sector Investment Program - Project I",
   "description_excerpt": "To develop indigenous, nonpolluting, and renewable sources of energy to help meet Pakistan&apos;s power sho...",
   "countries": [
    "{...}"
   ],
   "multi_country": false,
   "region": null,
   "sector_name": null,
   "year": 2007,
   "year_type": "activity_actual_start",
   "status": "Finalisation",
   "climate_annotations": []
  },
  {
   "id": "adb_pakistan:XM-DAC-46004-34339-023-LN2287",
   "source_id": "adb_pakistan",
   "source_project_id": "XM-DAC-46004-34339-023-LN2287",
   "record_level": "adb_financing_instrument",
   "title": "Renewable Energy Development Sector Investment Program - Project I",
   "description_excerpt": "To develop indigenous, nonpolluting, and renewable sources of energy to help meet Pakistan&apos;s power sho...",
   "countries": [
    "{...}"
   ],
   "multi_country": false,
   "region": null,
   "sector_name": null,
   "year": 2007,
   "year_type": "activity_actual_start",
   "status": "Finalisation",
   "climate_annotations": []
  },
  "... 2 more"
 ],
 "pagination": {
  "page": 1,
  "page_size": 5,
  "total_items": 26,
  "total_pages": 6
 },
 "applied_filters": {
  "q": "hydropower",
  "country": "PAK"
 },
 "sort": "id",
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 },
 "empty_result_message": null
}
```

## 4. Pagination (page 2)

`GET /api/v1/projects?country=PAK&source=aiddata&page=2&page_size=5` -> **200** (130.6 ms)

Response (trimmed):

```json
{
 "items": [
  {
   "id": "aiddata:35099",
   "source_id": "aiddata",
   "source_project_id": "35099",
   "record_level": "aiddata_record",
   "title": "China donates Computers and Books to Pakistan",
   "description_excerpt": "In 2000, the Chinese Embassy in Pakistan donated computers and books to Pakistan. Some organizations that r...",
   "countries": [
    "{...}"
   ],
   "multi_country": false,
   "region": "Asia",
   "sector_name": "EDUCATION",
   "year": 2000,
   "year_type": "commitment_year",
   "status": "Completion",
   "climate_annotations": [
    "{...}"
   ]
  },
  {
   "id": "aiddata:35101",
   "source_id": "aiddata",
   "source_project_id": "35101",
   "record_level": "aiddata_record",
   "title": "China grants RMB 2 million to Afghan refugees in Pakistan",
   "description_excerpt": "In April 2001, China pledged 2 million RMB yuan to support Afghan refugees living in Peshawar, Pakistan, wh...",
   "countries": [
    "{...}"
   ],
   "multi_country": false,
   "region": "Asia",
   "sector_name": "EMERGENCY RESPONSE",
   "year": 2001,
   "year_type": "commitment_year",
   "status": "Completion",
   "climate_annotations": [
    "{...}"
   ]
  },
  "... 2 more"
 ],
 "pagination": {
  "page": 2,
  "page_size": 5,
  "total_items": 496,
  "total_pages": 100
 },
 "applied_filters": {
  "country": "PAK",
  "source": "aiddata"
 },
 "sort": "id",
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 },
 "empty_result_message": null
}
```

## 5. Project detail

`GET /api/v1/projects/aiddata:35266` -> **200** (24.4 ms)

Response (trimmed):

```json
{
 "id": "aiddata:35266",
 "source": {
  "source_id": "aiddata",
  "name": "AidData's Global Chinese Development Finance Dataset, Version 3.0",
  "publisher": "AidData (William & Mary)",
  "rights_status": "not_reviewed",
  "reference_url": "https://www.aiddata.org/data/aiddatas-global-chinese-development-finance-dataset-version-3-0"
 },
 "source_project_id": "35266",
 "record_level": "aiddata_record",
 "title": "China Eximbank provides $448 million buyer’s credit loan for 969MW Neelum-Jhelum Hydroelectric Project (Lin...",
 "description": "On May 22, 2013, China Eximbank and the Government of Pakistan signed a $448 million buyer’s credit loan (B...",
 "recipient_label": "Pakistan",
 "countries": [
  {
   "country_name": "Pakistan",
   "iso3": "PAK",
   "mapping_method": "aiddata_recipient_iso3"
  }
 ],
 "multi_country": false,
 "region": "Asia",
 "sector_name": "ENERGY",
 "sector_code": "230",
 "sector_vocabulary": "aiddata_crs_sector",
 "year": 2013,
 "year_type": "commitment_year",
 "date_value": "2013-05-22",
 "date_precision": "day",
 "date_estimated": false,
 "status": "Completion",
 "source_reference": "AidData GCDF 3.0 AidData Record ID 35266; research workbook row 12390",
 "attributes": {
  "flow_type": "Loan",
  "flow_class": "OOF-like",
  "intent": "Mixed",
  "funding_agencies": "Export-Import Bank of China (China Eximbank)",
  "funding_agencies_type": "State-owned Policy Bank",
  "recommended_for_aggregates": true,
  "umbrella": false,
  "aiddata_parent_id": "1648",
  "research_row_id": "12390",
  "research_eligibility_status": "eligible"
 },
 "climate_annotations": [
  {
   "scheme": "rio_marker_qi_et_al_2026",
   "kind": "research_annotation",
   "annotation_source_id": "research_paper",
   "is_model_prediction": false,
   "overall": 2,
   "mitigation": 2,
   "adaptation": 0,
   "is_climate_related": true,
   "label": null,
   "raw_value": "2,2,0",
   "provenance": "Rio marker (overall, mitigation, adaptation; 0 = not targeted, 1 = significant, 2 = principal) annotated by..."
  }
 ],
 "financial_observations": [
  {
   "observation_key": "35266:amount_original_currency",
   "flow_kind": "commitment",
   "metric_label": "Commitment (project level)",
   "level": "project",
   "financing_type": "Loan",
   "is_component": false,
   "amount": "448000000",
   "raw_value": "448000000",
   "value_status": "reported",
   "unit": "units",
   "currency": "USD",
   "unit_status": "stated_in_source",
   "price_basis": "nominal",
   "effective_date": "2013-05-22",
   "effective_year": 2013,
   "date_meaning": "AidData commitment date",
   "multi_country": false,
   "estimated": null,
   "recommended_for_aggregates": true,
   "source_reference": "AidData 'Amount (Original Currency)' + 'Original Currency'"
  },
  {
   "observation_key": "35266:amount_constant_usd_2021",
   "flow_kind": "commitment",
   "metric_label": "Commitment (project level)",
   "level": "project",
   "financing_type": "Loan",
   "is_component": false,
   "amount": "505360375.381046",
   "raw_value": "505360375.381046",
   "value_status": "reported",
   "unit": "units",
   "currency": "USD",
   "unit_status": "stated_in_source",
   "price_basis": "constant_2021_usd",
   "effective_date": "2013-05-22",
   "effective_year": 2013,
   "date_meaning": "AidData commitment date",
   "multi_country": false,
   "estimated": null,
   "recommended_for_aggregates": true,
   "source_reference": "AidData 'Amount (Constant USD 2021)' (AidData's own conversion; not re-derived)"
  }
 ],
 "data_quality_warnings": [
  {
   "code": "retrospective_description",
   "field": "description",
   "message": "The description was written after the fact (reports outcomes or later events)."
  }
 ],
 "group": {
  "group_key": "aiddata_parent:1648",
  "meaning": "AidData Parent ID package: related financing records (tranches, umbrella and component agreements). Related...",
  "member_count": 2,
  "member_ids": [
   "aiddata:35266",
   "aiddata:54087"
  ]
 },
 "relationships": [],
 "disclaimers": [
  "Amounts are as published by the source; commitments, approvals and disbursements are different things and a...",
  "Historical finance is not evidence of project success, environmental benefit or financial return.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 },
 "enrichments": [],
 "documents": []
}
```

## 6. Screen text: ML v2 (default engine)

`POST /api/v1/screening/text` -> **200** (32.7 ms)

Request:

```json
{
 "title": "Example solar mini-grid for rural health clinics",
 "description": "Example text: install solar photovoltaic panels and battery storage to replace diesel generators at district health facilities."
}
```

Response (trimmed):

```json
{
 "screening_id": null,
 "saved": false,
 "model": {
  "model_key": "ml_v2",
  "engine_label": "Compassio Climate Intelligence — ML v2",
  "model_version": "ml2fast_49317056_c76204127550",
  "status": "development_candidate",
  "artifact_sha256": "654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574",
  "model_fingerprint": "c76204127550fb299c11704de61bd07cce3eae6635193e608a42897c5f995ad2",
  "threshold": 0.44474326842740053,
  "representation": "character TF-IDF 2-5-grams (char_wb) + logistic regression (C=2, balanced)",
  "training_data": "FCDO + EC IATI activities with publisher-reported Rio markers (v2 TRAIN, 13,317)",
  "intended_use": "Authorized local demonstration and internal research screening with human review.",
  "evaluation": {
   "kind": "development_validation_used_for_selection",
   "population": "2,550 eligible FCDO + EC v2 development-validation records (827 positive)",
   "headline": {
    "average_precision": 0.839,
    "f1": 0.738,
    "non_energy_recall": 0.766
   },
   "document": "docs/research/model_v2/development_champion_card.md",
   "independent_generalization_evidence": false
  },
  "artifact_present": true,
  "selectable_now": true
 },
 "operational_mode": "authorized_local_demo",
 "fallback_used": false,
 "prediction": {
  "is_climate_related": true,
  "label_score": 0.7885340825673351,
  "threshold": 0.44474326842740053,
  "band": "clearly_flagged",
  "score_semantics": "Model label score (agreement with climate annotations), not a probability of approval, impact or return."
 },
 "explanation": {
  "method": "Exact linear decomposition: logit = intercept + sum(tf-idf value x coefficient); word attributions redistri...",
  "intercept": -0.8159692235493075,
  "logit": 1.3161117914208869,
  "faithfulness_abs_error": 2.220446049250313e-16,
  "nonzero_features": 435,
  "feature_contribution_total": 2.1320810149701943,
  "word_contribution_total": 2.1320810149701948,
  "top_positive_features": [
   {
    "feature": "olar ",
    "contribution": 0.09036758003243807
   },
   {
    "feature": "solar",
    "contribution": 0.0894568032669096
   },
   "... 2 more"
  ],
  "top_negative_features": [
   {
    "feature": "lt",
    "contribution": -0.038027978388233574
   },
   {
    "feature": "ties.",
    "contribution": -0.03779678178436413
   },
   "... 2 more"
  ],
  "word_attribution_available": true,
  "top_words": [
   {
    "word": "mini-grid",
    "field": "title",
    "start": 14,
    "end": 23,
    "contribution": 0.5139038096308182
   },
   {
    "word": "photovoltaic",
    "field": "description",
    "start": 28,
    "end": 40,
    "contribution": 0.3993637762415134
   },
   "... 2 more"
  ]
 },
 "input_sha256": "0fb15586e3da8a1d78ff8045dc1979ed05e46e8cf605495d6233389737233ce9",
 "source_evidence": null,
 "guidance": [
  "Screening aid only: a person must review every flagged and unflagged record.",
  "Check the highlighted words against the full description before deciding."
 ],
 "limitations": [
  "DEVELOPMENT CANDIDATE: not an independently validated release.",
  "Trained on FCDO + EC publisher-reported Rio markers (not human-verified).",
  "... 2 more"
 ],
 "not_predicted": [
  "funding approval or eligibility",
  "financial return or profit",
  "... 2 more"
 ],
 "generated_at": "2026-11-10T20:13:09.158898Z"
}
```

## 7. Screen text: ML v1 (fallback)

`POST /api/v1/screening/text` -> **200** (20.7 ms)

Request:

```json
{
 "title": "Example solar mini-grid for rural health clinics",
 "description": "Example text: install solar photovoltaic panels and battery storage to replace diesel generators at district health facilities.",
 "model": "ml_v1"
}
```

Response (trimmed):

```json
{
 "screening_id": null,
 "saved": false,
 "model": {
  "model_key": "ml_v1",
  "engine_label": "Compassio Climate Relevance Classifier v1 — MVP Research Screening",
  "model_version": "compassio-ccrc-1.0.0-mvp-research-screening",
  "status": "trusted_research_release",
  "artifact_sha256": "53b226f6e866bd5377b951aaeb87f9be86c72dc9ac444a807bf0d49c857d3656",
  "model_fingerprint": "3023fe3d148b605c3ed9079c93f07296193fd2d8d5f77b8a82a163e58ccdc495",
  "threshold": 0.4740212723792222,
  "representation": "word TF-IDF 1-2-grams + logistic regression (C=16, balanced)",
  "training_data": "AidData GCDF 3.0 records with Qi et al. 2026 Rio annotations (primary TRAIN, 14,654)",
  "intended_use": "Human-reviewed research screening; reliable mainly for energy-sector text.",
  "evaluation": {
   "kind": "one_shot_frozen_test",
   "population": "AidData primary group-disjoint test (3,142 records, 202 positive)",
   "headline": {
    "average_precision": 0.751,
    "f1": 0.67,
    "non_energy_recall": 0.368
   },
   "document": "docs/research/task005_model_card.md",
   "independent_generalization_evidence": true
  },
  "artifact_present": true,
  "selectable_now": true
 },
 "operational_mode": "authorized_local_demo",
 "fallback_used": false,
 "prediction": {
  "is_climate_related": true,
  "label_score": 0.966024660637679,
  "threshold": 0.4740212723792222,
  "band": "clearly_flagged",
  "score_semantics": "Model label score (agreement with climate annotations), not a probability of approval, impact or return."
 },
 "explanation": {
  "method": "Exact linear decomposition: logit = intercept + sum(tf-idf value x coefficient); word attributions redistri...",
  "intercept": -4.051300066398322,
  "logit": 3.347554413920496,
  "faithfulness_abs_error": 0.0,
  "nonzero_features": 31,
  "feature_contribution_total": 7.398854480318818,
  "word_contribution_total": 7.398854480318818,
  "top_positive_features": [
   {
    "feature": "solar",
    "contribution": 4.655762322921227
   },
   {
    "feature": "photovoltaic",
    "contribution": 0.902105211477841
   },
   "... 2 more"
  ],
  "top_negative_features": [
   {
    "feature": "health",
    "contribution": -0.4060093026692121
   },
   {
    "feature": "diesel",
    "contribution": -0.19688156517244115
   },
   "... 2 more"
  ],
  "word_attribution_available": true,
  "top_words": [
   {
    "word": "solar",
    "field": "description",
    "start": 22,
    "end": 27,
    "contribution": 2.4500546200305253
   },
   {
    "word": "solar",
    "field": "title",
    "start": 8,
    "end": 13,
    "contribution": 2.3278811614606134
   },
   "... 2 more"
  ]
 },
 "input_sha256": "0fb15586e3da8a1d78ff8045dc1979ed05e46e8cf605495d6233389737233ce9",
 "source_evidence": null,
 "guidance": [
  "Screening aid only: a person must review every flagged and unflagged record.",
  "Check the highlighted words against the full description before deciding."
 ],
 "limitations": [
  "Trained on AidData Chinese official-finance descriptions with Qi et al. 2026 labels.",
  "Reliable mainly for energy text; misses most adaptation and non-energy projects.",
  "... 1 more"
 ],
 "not_predicted": [
  "funding approval or eligibility",
  "financial return or profit",
  "... 2 more"
 ],
 "generated_at": "2026-11-10T20:13:09.179884Z"
}
```

## 8. Screen a permitted DB record (AidData)

`POST /api/v1/screening/projects/aiddata:35266` -> **200** (144.0 ms)

Request:

```json
{}
```

Response (trimmed):

```json
{
 "screening_id": null,
 "saved": false,
 "model": {
  "model_key": "ml_v2",
  "engine_label": "Compassio Climate Intelligence — ML v2",
  "model_version": "ml2fast_49317056_c76204127550",
  "status": "development_candidate",
  "artifact_sha256": "654336052ba75aae97a5c20db1c3ce9bb06792640abe6f660973318852358574",
  "model_fingerprint": "c76204127550fb299c11704de61bd07cce3eae6635193e608a42897c5f995ad2",
  "threshold": 0.44474326842740053,
  "representation": "character TF-IDF 2-5-grams (char_wb) + logistic regression (C=2, balanced)",
  "training_data": "FCDO + EC IATI activities with publisher-reported Rio markers (v2 TRAIN, 13,317)",
  "intended_use": "Authorized local demonstration and internal research screening with human review.",
  "evaluation": {
   "kind": "development_validation_used_for_selection",
   "population": "2,550 eligible FCDO + EC v2 development-validation records (827 positive)",
   "headline": {
    "average_precision": 0.839,
    "f1": 0.738,
    "non_energy_recall": 0.766
   },
   "document": "docs/research/model_v2/development_champion_card.md",
   "independent_generalization_evidence": false
  },
  "artifact_present": true,
  "selectable_now": true
 },
 "operational_mode": "authorized_local_demo",
 "fallback_used": false,
 "prediction": {
  "is_climate_related": true,
  "label_score": 0.5944628600004439,
  "threshold": 0.44474326842740053,
  "band": "clearly_flagged",
  "score_semantics": "Model label score (agreement with climate annotations), not a probability of approval, impact or return."
 },
 "explanation": {
  "method": "Exact linear decomposition: logit = intercept + sum(tf-idf value x coefficient); word attributions redistri...",
  "intercept": -0.8159692235493075,
  "logit": 0.38244578152491804,
  "faithfulness_abs_error": 0.0,
  "nonzero_features": 6536,
  "feature_contribution_total": 1.1984150050742255,
  "word_contribution_total": 1.1984150050742257,
  "top_positive_features": [
   {
    "feature": " wa",
    "contribution": 0.0442035227697057
   },
   {
    "feature": " was",
    "contribution": 0.0360252998251884
   },
   "... 2 more"
  ],
  "top_negative_features": [
   {
    "feature": "ju",
    "contribution": -0.02162074312069905
   },
   {
    "feature": "pa ",
    "contribution": -0.02149438154002565
   },
   "... 2 more"
  ],
  "word_attribution_available": true,
  "top_words": [
   {
    "word": "energy",
    "field": "description",
    "start": 4174,
    "end": 4180,
    "contribution": 0.08813140072264239
   },
   {
    "word": "energy",
    "field": "description",
    "start": 7260,
    "end": 7266,
    "contribution": 0.08813140072264239
   },
   "... 2 more"
  ]
 },
 "input_sha256": "c298e076954341f37ee50504765b9e7346a920ec541669ed93d28341a3416d85",
 "source_evidence": {
  "project_id": "aiddata:35266",
  "source_id": "aiddata",
  "source_reference": "AidData GCDF 3.0 AidData Record ID 35266; research workbook row 12390",
  "title": "China Eximbank provides $448 million buyer’s credit loan for 969MW Neelum-Jhelum Hydroelectric Project (Lin...",
  "description": "On May 22, 2013, China Eximbank and the Government of Pakistan signed a $448 million buyer’s credit loan (B...",
  "rights_status": "not_reviewed",
  "model_input_permission": "aiddata: automated_evaluation permitted_pending_review"
 },
 "guidance": [
  "Screening aid only: a person must review every flagged and unflagged record.",
  "Check the highlighted words against the full description before deciding."
 ],
 "limitations": [
  "DEVELOPMENT CANDIDATE: not an independently validated release.",
  "Trained on FCDO + EC publisher-reported Rio markers (not human-verified).",
  "... 2 more"
 ],
 "not_predicted": [
  "funding approval or eligibility",
  "financial return or profit",
  "... 2 more"
 ],
 "generated_at": "2026-11-10T20:13:09.323496Z"
}
```

## 9. Screen a non-permitted source (refused)

`POST /api/v1/screening/projects/gcf_projects:FP085` -> **403** (24.8 ms)

Request:

```json
{}
```

Response (trimmed):

```json
{
 "code": "source_not_permitted_for_model_input",
 "message": "Records from 'gcf_projects' are not permitted as model input (automated_evaluation is not permitted for thi..."
}
```

## 10. Decision evidence

`GET /api/v1/decision/evidence/aiddata:35266` -> **200** (113.8 ms)

Response (trimmed):

```json
{
 "project": {
  "project_id": "aiddata:35266",
  "title": "China Eximbank provides $448 million buyer’s credit loan for 969MW Neelum-Jhelum Hydroelectric Project (Lin...",
  "source": {
   "source_id": "aiddata",
   "name": "AidData's Global Chinese Development Finance Dataset, Version 3.0",
   "publisher": "AidData (William & Mary)",
   "rights_status": "not_reviewed",
   "access_tier": "standard",
   "reference_url": "https://www.aiddata.org/data/aiddatas-global-chinese-development-finance-dataset-version-3-0"
  },
  "source_project_id": "35266",
  "record_level": "aiddata_record",
  "description": "On May 22, 2013, China Eximbank and the Government of Pakistan signed a $448 million buyer’s credit loan (B...",
  "countries": [
   {
    "country_name": "Pakistan",
    "iso3": "PAK",
    "mapping_method": "aiddata_recipient_iso3"
   }
  ],
  "multi_country": false,
  "country_note": "Single recipient as published.",
  "sector": {
   "name": "ENERGY",
   "code": "230",
   "vocabulary": "aiddata_crs_sector"
  },
  "institutions": [
   {
    "role": "funding agency (as stated by AidData)",
    "name": "Export-Import Bank of China (China Eximbank)"
   }
  ],
  "year": 2013,
  "year_type": "commitment_year",
  "source_status": "Completion",
  "verified_approval": null,
  "climate_relevance": {
   "status": "research_annotation_climate_related",
   "basis": "Qi et al. 2026 Rio-marker research annotation (label)",
   "is_model_prediction": false,
   "statement": "A climate-relevance label or classification, not measured environmental impact.",
   "annotations": [
    "{...}"
   ],
   "model_screening": "Not run here. Use POST /api/v1/screening/projects/{project_id} (local only)."
  },
  "headline_facts": [
   {
    "fact_id": "35266:amount_constant_usd_2021",
    "fact_type": "source_reported",
    "source_id": "aiddata",
    "flow_kind": "commitment",
    "financial_meaning": "historical_commitment",
    "is_funding_flow": true,
    "meaning_label": "Historical commitment (not a disbursement) - Commitment (project level)",
    "level": "project",
    "financing_type": "Loan",
    "is_component": false,
    "amount": "505360375.381046",
    "amount_in_units": "505360375.381046",
    "unit": "units",
    "currency": "USD",
    "price_basis": "constant_2021_usd",
    "value_status": "reported",
    "date": "2013-05-22",
    "year": 2013,
    "date_meaning": "AidData commitment date",
    "multi_country": false,
    "country_iso3": null,
    "country_attribution": "single_country_project",
    "estimated": null,
    "recommended_for_aggregates": true,
    "transactions_summed": null,
    "first_year": null,
    "last_year": null,
    "comparability_key": "aiddata|commitment|project|USD|constant_2021_usd|stated_total",
    "source_reference": "AidData 'Amount (Constant USD 2021)' (AidData's own conversion; not re-derived)"
   },
   {
    "fact_id": "35266:amount_original_currency",
    "fact_type": "source_reported",
    "source_id": "aiddata",
    "flow_kind": "commitment",
    "financial_meaning": "historical_commitment",
    "is_funding_flow": true,
    "meaning_label": "Historical commitment (not a disbursement) - Commitment (project level)",
    "level": "project",
    "financing_type": "Loan",
    "is_component": false,
    "amount": "448000000",
    "amount_in_units": "448000000",
    "unit": "units",
    "currency": "USD",
    "price_basis": "nominal",
    "value_status": "reported",
    "date": "2013-05-22",
    "year": 2013,
    "date_meaning": "AidData commitment date",
    "multi_country": false,
    "country_iso3": null,
    "country_attribution": "single_country_project",
    "estimated": null,
    "recommended_for_aggregates": true,
    "transactions_summed": null,
    "first_year": null,
    "last_year": null,
    "comparability_key": "aiddata|commitment|project|USD|nominal|stated_total",
    "source_reference": "AidData 'Amount (Original Currency)' + 'Original Currency'"
   }
  ],
  "breakdown_facts": [],
  "linked_records": [],
  "documents": [],
  "data_quality_warnings": [
   {
    "code": "retrospective_description",
    "field": "description",
    "message": "The description was written after the fact (reports outcomes or later events)."
   }
  ],
  "completeness": {
   "has_description": true,
   "has_sector": true,
   "has_year": true,
   "has_mapped_country": true,
   "has_source_status": true,
   "has_institution": true,
   "has_reported_amount": true,
   "has_amount_with_currency": true,
   "has_dated_amount": true,
   "has_documents": false,
   "has_verified_approval": false,
   "missing": [
    "has_documents",
    "has_verified_approval"
   ]
  },
  "source_reference": "AidData GCDF 3.0 AidData Record ID 35266; research workbook row 12390",
  "group_key": "aiddata_parent:1648",
  "group_meaning": "AidData Parent ID package: related financing records (tranches, umbrella and component agreements). Related...",
  "current_funding_opportunity": "not_determinable",
  "limitations": [
   "Historical record: not evidence that funding is currently available.",
   "Climate labels are classifications, not measured environmental outcomes.",
   "... 1 more"
  ]
 },
 "methodology_version": "compassio-comparison-1.1.0",
 "disclaimers": [
  "Decision support only: Compassio does not approve, recommend or allocate real funding.",
  "Historical project funding is not a currently available funding opportunity.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 11. Funding by country (ADB disbursements)

`GET /api/v1/analytics/funding-by-country?metric=adb_disbursements_usd` -> **200** (204.7 ms)

Response (trimmed):

```json
{
 "dimension": "country",
 "status": "available",
 "unavailable_reason": null,
 "declaration": {
  "metric_id": "adb_disbursements_usd",
  "label": "ADB Pakistan disbursements (IATI transaction type 3, USD)",
  "universe": "Sum of ADB disbursement transactions (including published reversals) by year. Grouped by country; years all...",
  "financial_meaning": "disbursed funds as published",
  "source_id": "adb_pakistan",
  "flow_kind": "disbursement",
  "level": "transaction",
  "currency": "USD",
  "price_basis": "nominal",
  "unit": "units of USD",
  "year_basis": "IATI transaction date (year)",
  "is_funding": true,
  "known_exclusions": [
   "Includes negative reversal transactions as published."
  ],
  "excluded_records": {}
 },
 "year_from": null,
 "year_to": null,
 "groups": [
  {
   "key": "PAK",
   "label": "Pakistan",
   "status": "available",
   "total": "21549925012.94",
   "summed_records": 7117,
   "missing_value_records": 0,
   "estimated_records": 0,
   "unavailable_reason": null
  }
 ],
 "groups_total": 1,
 "groups_shown": 1,
 "disclaimers": [
  "Amounts are as published by the source; commitments, approvals and disbursements are different things and a...",
  "Historical finance is not evidence of project success, environmental benefit or financial return.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 12. Trends total for the same metric (PAK)

`GET /api/v1/analytics/trends?metric=adb_disbursements_usd&country=PAK` -> **200** (244.0 ms)

Response (trimmed):

```json
{
 "metric": {
  "metric_id": "adb_disbursements_usd",
  "label": "ADB Pakistan disbursements (IATI transaction type 3, USD)",
  "source_id": "adb_pakistan",
  "flow_kind": "disbursement",
  "level": "transaction",
  "currency": "USD",
  "price_basis": "nominal",
  "year_basis": "IATI transaction date (year)",
  "is_funding": true,
  "description": "Sum of ADB disbursement transactions (including published reversals) by year.",
  "limitations": [
   "Includes negative reversal transactions as published."
  ],
  "deduplication_policy": "Single source; one observation per published amount (unique source + key); instrument components never adde...",
  "row_selection": "exclude"
 },
 "status": "available",
 "unavailable_reason": null,
 "country": "PAK",
 "year_from": null,
 "year_to": null,
 "points": [
  {
   "year": 2013,
   "status": "available",
   "total": "5216938110.62",
   "unit": "USD",
   "summed_records": 63,
   "missing_value_records": 0,
   "estimated_records": 0,
   "excluded_records": {},
   "unavailable_reason": null
  },
  {
   "year": 2014,
   "status": "available",
   "total": "856914999.20",
   "unit": "USD",
   "summed_records": 117,
   "missing_value_records": 0,
   "estimated_records": 0,
   "excluded_records": {},
   "unavailable_reason": null
  },
  "... 2 more"
 ],
 "undated_records": 0,
 "excluded_outside_rules": {},
 "aggregation_limitations": [
  "Includes negative reversal transactions as published."
 ],
 "disclaimers": [
  "Amounts are as published by the source; commitments, approvals and disbursements are different things and a...",
  "Historical finance is not evidence of project success, environmental benefit or financial return.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 13. Approved vs disbursed (PAK)

`GET /api/v1/analytics/approved-vs-disbursed?country=PAK` -> **200** (331.8 ms)

Response (trimmed):

```json
{
 "country": "PAK",
 "sources": [
  {
   "source_id": "climate_funds_update",
   "approval_meaning": "Approved funding per CFU project (stated total, instrument components excluded)",
   "disbursement_meaning": "Disbursed to date as reported by CFU (stated total)",
   "currency": "USD",
   "universe": "Records of this source that report BOTH figures in USD (paired); multi-country records excluded; mapped to PAK",
   "projects_with_approval": 31,
   "projects_with_disbursement": 27,
   "paired_projects": 27,
   "approved_total_paired": "307254915.44000000",
   "disbursed_total_paired": "106901546.78000000",
   "disbursed_to_approved_ratio": "0.3479",
   "excluded_projects": {},
   "limitations": [
    "CFU reports cumulative disbursement at its own update; timing differs by fund.",
    "Project-level USD as published (CFU units: millions, converted with the unit scale only)."
   ]
  },
  {
   "source_id": "gcf_api_projects",
   "approval_meaning": "GCF financing approved (sum of the project's USD funding lines)",
   "disbursement_meaning": "GCF disbursement transactions (USD)",
   "currency": "USD",
   "universe": "Records of this source that report BOTH figures in USD (paired); multi-country records excluded; mapped to PAK",
   "projects_with_approval": 8,
   "projects_with_disbursement": 6,
   "paired_projects": 6,
   "approved_total_paired": "205727978",
   "disbursed_total_paired": "79882949",
   "disbursed_to_approved_ratio": "0.3883",
   "excluded_projects": {},
   "limitations": [
    "Projects with any non-USD line or lines inconsistent with the published total are excluded (counted), never...",
    "Disbursement lags approval by years; a low ratio is not under-performance."
   ]
  },
  "... 1 more"
 ],
 "disclaimers": [
  "Amounts are as published by the source; commitments, approvals and disbursements are different things and a...",
  "Historical finance is not evidence of project success, environmental benefit or financial return.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 14. Country profile (PAK)

`GET /api/v1/analytics/country-profile/PAK` -> **200** (756.0 ms)

Response (trimmed):

```json
{
 "country": "PAK",
 "project_counts": [
  {
   "source_id": "adb_pakistan",
   "single_country_projects": 193,
   "multi_country_projects_including_country": 0
  },
  {
   "source_id": "aiddata",
   "single_country_projects": 496,
   "multi_country_projects_including_country": 0
  },
  "... 2 more"
 ],
 "metrics": [
  {
   "declaration": {
    "metric_id": "aiddata_commitments_constant_2021_usd",
    "label": "Chinese official finance commitments (AidData constant 2021 USD)",
    "universe": "AidData commitments by commitment year in AidData's own constant-2021-USD conversion, restricted to records...",
    "financial_meaning": "historical commitments (not disbursements)",
    "source_id": "aiddata",
    "flow_kind": "commitment",
    "level": "project",
    "currency": "USD",
    "price_basis": "constant_2021_usd",
    "unit": "units of USD",
    "year_basis": "AidData commitment year",
    "is_funding": true,
    "known_exclusions": "[3 items]",
    "excluded_records": "{...}"
   },
   "status": "available",
   "all_years_total": "102852446551.65715952412",
   "summed_records": 318,
   "first_year": 2000,
   "last_year": 2021,
   "unavailable_reason": null
  },
  {
   "declaration": {
    "metric_id": "cfu_approvals_usd",
    "label": "Climate fund approvals (Climate Funds Update, nominal USD)",
    "universe": "Total approved funding per CFU project row by approval year (instrument components excluded so the total is...",
    "financial_meaning": "approved funding (not necessarily disbursed)",
    "source_id": "climate_funds_update",
    "flow_kind": "approval",
    "level": "project",
    "currency": "USD",
    "price_basis": "nominal",
    "unit": "units of USD",
    "year_basis": "CFU approval year",
    "is_funding": true,
    "known_exclusions": "[3 items]",
    "excluded_records": "{...}"
   },
   "status": "available",
   "all_years_total": "316574915.44000000",
   "summed_records": 31,
   "first_year": 2008,
   "last_year": 2025,
   "unavailable_reason": null
  },
  "... 2 more"
 ],
 "top_sectors": [
  {
   "label": "ENERGY",
   "projects": 86
  },
  {
   "label": "EMERGENCY RESPONSE",
   "projects": 82
  },
  "... 2 more"
 ],
 "climate": {
  "country": "PAK",
  "measure": "project_record_count",
  "distributions": [
   {
    "scheme": "cfu_theme_objective",
    "annotation_source_id": "climate_funds_update",
    "kind": "source_classification",
    "meaning": "Climate Funds Update theme / objective as published.",
    "buckets": "[4 items]",
    "projects_annotated": 31
   },
   {
    "scheme": "gcf_readiness_activity",
    "annotation_source_id": "gcf_readiness",
    "kind": "source_classification",
    "meaning": "GCF readiness activity type (capacity support).",
    "buckets": "[4 items]",
    "projects_annotated": 7
   },
   "... 2 more"
  ],
  "statement": "Counts of records by climate label or classification. Labels describe stated purpose; they are not measured...",
  "access": {
   "mode": "hackathon_event",
   "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
  }
 },
 "country_aggregates_endpoint": "/api/v1/analytics/country-aggregates?iso3=PAK",
 "disclaimers": [
  "Amounts are as published by the source; commitments, approvals and disbursements are different things and a...",
  "Historical finance is not evidence of project success, environmental benefit or financial return.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 15. Compare: same AidData parent package + GCF

`POST /api/v1/decision/compare` -> **200** (19.0 ms)

Request:

```json
{
 "project_ids": [
  "gcf_projects:FP085",
  "aiddata:35266",
  "aiddata:54087"
 ]
}
```

Response (trimmed):

```json
{
 "projects": [
  {
   "project_id": "gcf_projects:FP085",
   "title": "Green BRT Karachi",
   "source": {
    "source_id": "gcf_projects",
    "name": "Green Climate Fund Open Data Library - funded projects export",
    "publisher": "Green Climate Fund",
    "rights_status": "not_reviewed",
    "access_tier": "standard",
    "reference_url": "https://data.greenclimate.fund/public/data/projects"
   },
   "source_project_id": "FP085",
   "record_level": "gcf_funded_project",
   "description": null,
   "countries": [
    "{...}"
   ],
   "multi_country": false,
   "country_note": "Single recipient as published.",
   "sector": null,
   "institutions": [
    "{...}",
    "{...}"
   ],
   "year": null,
   "year_type": null,
   "source_status": null,
   "verified_approval": {
    "approval_status": "approved by the GCF Board (ApprovalDate published)",
    "approval_date": "2018-10-20",
    "approval_date_type": "GCF Board approval date (API 'ApprovalDate')",
    "project_status": "Under Implementation",
    "status_as_of": "2026-11-09T14:45:34",
    "verified_by_source_id": "gcf_api_projects",
    "verification_state": "deterministic_identifier_match",
    "official_url": "https://www.greenclimate.fund/project/FP085"
   },
   "climate_relevance": {
    "status": "listed_by_climate_fund",
    "basis": "Record published by a dedicated climate fund (gcf_projects); source classification: Mitigation",
    "is_model_prediction": false,
    "statement": "A climate-relevance label or classification, not measured environmental impact.",
    "annotations": "[1 items]",
    "model_screening": "Not run here. Use POST /api/v1/screening/projects/{project_id} (local only)."
   },
   "headline_facts": [
    "{...}",
    "{...}",
    "... 2 more"
   ],
   "breakdown_facts": [
    "{...}",
    "{...}",
    "... 2 more"
   ],
   "linked_records": [
    "{...}"
   ],
   "documents": [],
   "data_quality_warnings": [
    "{...}",
    "{...}"
   ],
   "completeness": {
    "has_description": false,
    "has_sector": false,
    "has_year": false,
    "has_mapped_country": true,
    "has_source_status": false,
    "has_institution": true,
    "has_reported_amount": true,
    "has_amount_with_currency": true,
    "has_dated_amount": true,
    "has_documents": false,
    "has_verified_approval": true,
    "missing": "[4 items]"
   },
   "source_reference": "GCF funded projects export, Ref # FP085",
   "group_key": null,
   "group_meaning": null,
   "current_funding_opportunity": "not_determinable",
   "limitations": [
    "Historical record: not evidence that funding is currently available.",
    "Climate labels are classifications, not measured environmental outcomes.",
    "... 1 more"
   ]
  },
  {
   "project_id": "aiddata:35266",
   "title": "China Eximbank provides $448 million buyer’s credit loan for 969MW Neelum-Jhelum Hydroelectric Project (Lin...",
   "source": {
    "source_id": "aiddata",
    "name": "AidData's Global Chinese Development Finance Dataset, Version 3.0",
    "publisher": "AidData (William & Mary)",
    "rights_status": "not_reviewed",
    "access_tier": "standard",
    "reference_url": "https://www.aiddata.org/data/aiddatas-global-chinese-development-finance-dataset-version-3-0"
   },
   "source_project_id": "35266",
   "record_level": "aiddata_record",
   "description": "On May 22, 2013, China Eximbank and the Government of Pakistan signed a $448 million buyer’s credit loan (B...",
   "countries": [
    "{...}"
   ],
   "multi_country": false,
   "country_note": "Single recipient as published.",
   "sector": {
    "name": "ENERGY",
    "code": "230",
    "vocabulary": "aiddata_crs_sector"
   },
   "institutions": [
    "{...}"
   ],
   "year": 2013,
   "year_type": "commitment_year",
   "source_status": "Completion",
   "verified_approval": null,
   "climate_relevance": {
    "status": "research_annotation_climate_related",
    "basis": "Qi et al. 2026 Rio-marker research annotation (label)",
    "is_model_prediction": false,
    "statement": "A climate-relevance label or classification, not measured environmental impact.",
    "annotations": "[1 items]",
    "model_screening": "Not run here. Use POST /api/v1/screening/projects/{project_id} (local only)."
   },
   "headline_facts": [
    "{...}",
    "{...}"
   ],
   "breakdown_facts": [],
   "linked_records": [],
   "documents": [],
   "data_quality_warnings": [
    "{...}"
   ],
   "completeness": {
    "has_description": true,
    "has_sector": true,
    "has_year": true,
    "has_mapped_country": true,
    "has_source_status": true,
    "has_institution": true,
    "has_reported_amount": true,
    "has_amount_with_currency": true,
    "has_dated_amount": true,
    "has_documents": false,
    "has_verified_approval": false,
    "missing": "[2 items]"
   },
   "source_reference": "AidData GCDF 3.0 AidData Record ID 35266; research workbook row 12390",
   "group_key": "aiddata_parent:1648",
   "group_meaning": "AidData Parent ID package: related financing records (tranches, umbrella and component agreements). Related...",
   "current_funding_opportunity": "not_determinable",
   "limitations": [
    "Historical record: not evidence that funding is currently available.",
    "Climate labels are classifications, not measured environmental outcomes.",
    "... 1 more"
   ]
  },
  "... 1 more"
 ],
 "comparable_groups": [
  {
   "comparability_key": "aiddata|commitment|project|USD|constant_2021_usd|stated_total",
   "source_id": "aiddata",
   "flow_kind": "commitment",
   "financial_meaning": "historical_commitment",
   "meaning_label": "Historical commitment (not a disbursement) - Commitment (project level)",
   "level": "project",
   "currency": "USD",
   "price_basis": "constant_2021_usd",
   "cells": [
    "{...}",
    "{...}",
    "... 1 more"
   ],
   "selection_total": null,
   "selection_total_status": "unavailable",
   "selection_summed_records": 0,
   "selection_missing_records": 0,
   "selection_total_reason": "At least two of these records belong to the same source record group (for example an AidData parent package...",
   "selection_total_meaning": "Sum of these historical figures for the selected records only, in units of the stated currency. Not availab..."
  },
  {
   "comparability_key": "aiddata|commitment|project|USD|nominal|stated_total",
   "source_id": "aiddata",
   "flow_kind": "commitment",
   "financial_meaning": "historical_commitment",
   "meaning_label": "Historical commitment (not a disbursement) - Commitment (project level)",
   "level": "project",
   "currency": "USD",
   "price_basis": "nominal",
   "cells": [
    "{...}",
    "{...}",
    "... 1 more"
   ],
   "selection_total": null,
   "selection_total_status": "unavailable",
   "selection_summed_records": 0,
   "selection_missing_records": 0,
   "selection_total_reason": "At least two of these records belong to the same source record group (for example an AidData parent package...",
   "selection_total_meaning": "Sum of these historical figures for the selected records only, in units of the stated currency. Not availab..."
  },
  "... 2 more"
 ],
 "duplicate_warnings": [
  {
   "project_ids": [
    "aiddata:35266",
    "aiddata:54087"
   ],
   "relation_type": "same_source_record_group",
   "verification_state": "source_published_group",
   "message": "Related records in the same source group (aiddata_parent:1648). The source publishes them as one package; C..."
  }
 ],
 "field_matrix": {
  "has_description": {
   "gcf_projects:FP085": false,
   "aiddata:35266": true,
   "aiddata:54087": true
  },
  "has_sector": {
   "gcf_projects:FP085": false,
   "aiddata:35266": true,
   "aiddata:54087": true
  },
  "has_year": {
   "gcf_projects:FP085": false,
   "aiddata:35266": true,
   "aiddata:54087": true
  },
  "has_mapped_country": {
   "gcf_projects:FP085": true,
   "aiddata:35266": true,
   "aiddata:54087": true
  },
  "has_source_status": {
   "gcf_projects:FP085": false,
   "aiddata:35266": true,
   "aiddata:54087": true
  },
  "has_institution": {
   "gcf_projects:FP085": true,
   "aiddata:35266": true,
   "aiddata:54087": true
  },
  "has_reported_amount": {
   "gcf_projects:FP085": true,
   "aiddata:35266": true,
   "aiddata:54087": true
  },
  "has_amount_with_currency": {
   "gcf_projects:FP085": true,
   "aiddata:35266": true,
   "aiddata:54087": true
  },
  "has_dated_amount": {
   "gcf_projects:FP085": true,
   "aiddata:35266": true,
   "aiddata:54087": true
  },
  "has_documents": {
   "gcf_projects:FP085": false,
   "aiddata:35266": false,
   "aiddata:54087": false
  },
  "has_verified_approval": {
   "gcf_projects:FP085": true,
   "aiddata:35266": false,
   "aiddata:54087": false
  }
 },
 "methodology_version": "compassio-comparison-1.1.0",
 "disclaimers": [
  "Decision support only: Compassio does not approve, recommend or allocate real funding.",
  "Historical project funding is not a currently available funding opportunity.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 16. Compare: cross-source linked pair

`POST /api/v1/decision/compare` -> **200** (20.5 ms)

Request:

```json
{
 "project_ids": [
  "climate_funds_update:projects-r10",
  "gcf_projects:FP005"
 ]
}
```

Response (trimmed):

```json
{
 "projects": [
  {
   "project_id": "climate_funds_update:projects-r10",
   "title": "(FP005) KawiSafi Ventures Fund",
   "source": {
    "source_id": "climate_funds_update",
    "name": "Climate Funds Update - website master workbook 2025",
    "publisher": "Climate Funds Update (ODI / Heinrich Boll Stiftung)",
    "rights_status": "not_reviewed",
    "access_tier": "standard",
    "reference_url": "https://climatefundsupdate.org/data-dashboard/"
   },
   "source_project_id": "projects-r10",
   "record_level": "cfu_project_row",
   "description": "Creating a new investment fund, KawiSa , to drive off-grid solar power in East Africa. Investing in 10-15 c...",
   "countries": [
    "{...}"
   ],
   "multi_country": true,
   "country_note": "Multi-country record: amounts are whole-project values and are not allocated to any one country.",
   "sector": {
    "name": "Energy generation, renewable sources",
    "code": "DAC232_",
    "vocabulary": "cfu_oecd_sector"
   },
   "institutions": [
    "{...}",
    "{...}",
    "... 1 more"
   ],
   "year": 2015,
   "year_type": "approval_year",
   "source_status": null,
   "verified_approval": null,
   "climate_relevance": {
    "status": "listed_by_climate_fund",
    "basis": "Record published by a dedicated climate fund (climate_funds_update); source classification: Multiple foci",
    "is_model_prediction": false,
    "statement": "A climate-relevance label or classification, not measured environmental impact.",
    "annotations": "[1 items]",
    "model_screening": "Not run here. Use POST /api/v1/screening/projects/{project_id} (local only)."
   },
   "headline_facts": [
    "{...}",
    "{...}"
   ],
   "breakdown_facts": [
    "{...}",
    "{...}"
   ],
   "linked_records": [
    "{...}"
   ],
   "documents": [],
   "data_quality_warnings": [
    "{...}",
    "{...}",
    "... 1 more"
   ],
   "completeness": {
    "has_description": true,
    "has_sector": true,
    "has_year": true,
    "has_mapped_country": false,
    "has_source_status": false,
    "has_institution": true,
    "has_reported_amount": true,
    "has_amount_with_currency": true,
    "has_dated_amount": true,
    "has_documents": false,
    "has_verified_approval": false,
    "missing": "[4 items]"
   },
   "source_reference": "CFU workbook, sheet 'Projects', row 10",
   "group_key": null,
   "group_meaning": null,
   "current_funding_opportunity": "not_determinable",
   "limitations": [
    "Historical record: not evidence that funding is currently available.",
    "Climate labels are classifications, not measured environmental outcomes.",
    "... 1 more"
   ]
  },
  {
   "project_id": "gcf_projects:FP005",
   "title": "KawiSafi Ventures Fund",
   "source": {
    "source_id": "gcf_projects",
    "name": "Green Climate Fund Open Data Library - funded projects export",
    "publisher": "Green Climate Fund",
    "rights_status": "not_reviewed",
    "access_tier": "standard",
    "reference_url": "https://data.greenclimate.fund/public/data/projects"
   },
   "source_project_id": "FP005",
   "record_level": "gcf_funded_project",
   "description": null,
   "countries": [
    "{...}",
    "{...}"
   ],
   "multi_country": true,
   "country_note": "Multi-country record: amounts are whole-project values and are not allocated to any one country.",
   "sector": null,
   "institutions": [
    "{...}",
    "{...}"
   ],
   "year": null,
   "year_type": null,
   "source_status": null,
   "verified_approval": {
    "approval_status": "approved by the GCF Board (ApprovalDate published)",
    "approval_date": "2015-11-05",
    "approval_date_type": "GCF Board approval date (API 'ApprovalDate')",
    "project_status": "Under Implementation",
    "status_as_of": "2026-11-09T14:45:34",
    "verified_by_source_id": "gcf_api_projects",
    "verification_state": "deterministic_identifier_match",
    "official_url": "https://www.greenclimate.fund/project/FP005"
   },
   "climate_relevance": {
    "status": "listed_by_climate_fund",
    "basis": "Record published by a dedicated climate fund (gcf_projects); source classification: Cross-cutting",
    "is_model_prediction": false,
    "statement": "A climate-relevance label or classification, not measured environmental impact.",
    "annotations": "[1 items]",
    "model_screening": "Not run here. Use POST /api/v1/screening/projects/{project_id} (local only)."
   },
   "headline_facts": [
    "{...}",
    "{...}",
    "... 2 more"
   ],
   "breakdown_facts": [
    "{...}",
    "{...}",
    "... 2 more"
   ],
   "linked_records": [
    "{...}"
   ],
   "documents": [],
   "data_quality_warnings": [
    "{...}",
    "{...}",
    "... 1 more"
   ],
   "completeness": {
    "has_description": false,
    "has_sector": false,
    "has_year": false,
    "has_mapped_country": true,
    "has_source_status": false,
    "has_institution": true,
    "has_reported_amount": true,
    "has_amount_with_currency": true,
    "has_dated_amount": true,
    "has_documents": false,
    "has_verified_approval": true,
    "missing": "[4 items]"
   },
   "source_reference": "GCF funded projects export, Ref # FP005",
   "group_key": null,
   "group_meaning": null,
   "current_funding_opportunity": "not_determinable",
   "limitations": [
    "Historical record: not evidence that funding is currently available.",
    "Climate labels are classifications, not measured environmental outcomes.",
    "... 2 more"
   ]
  }
 ],
 "comparable_groups": [
  {
   "comparability_key": "climate_funds_update|approval|project|USD|nominal|stated_total",
   "source_id": "climate_funds_update",
   "flow_kind": "approval",
   "financial_meaning": "approval",
   "meaning_label": "Approved funding (not necessarily disbursed) - Approval (project level)",
   "level": "project",
   "currency": "USD",
   "price_basis": "nominal",
   "cells": [
    "{...}",
    "{...}"
   ],
   "selection_total": null,
   "selection_total_status": "unavailable",
   "selection_summed_records": 0,
   "selection_missing_records": 0,
   "selection_total_reason": "Fewer than two selected projects report this figure; nothing to compare.",
   "selection_total_meaning": "Sum of these historical figures for the selected records only, in units of the stated currency. Not availab..."
  },
  {
   "comparability_key": "climate_funds_update|disbursement|project|USD|nominal|stated_total",
   "source_id": "climate_funds_update",
   "flow_kind": "disbursement",
   "financial_meaning": "disbursement",
   "meaning_label": "Disbursed funds as published - Disbursement (project level)",
   "level": "project",
   "currency": "USD",
   "price_basis": "nominal",
   "cells": [
    "{...}",
    "{...}"
   ],
   "selection_total": null,
   "selection_total_status": "unavailable",
   "selection_summed_records": 0,
   "selection_missing_records": 0,
   "selection_total_reason": "Fewer than two selected projects report this figure; nothing to compare.",
   "selection_total_meaning": "Sum of these historical figures for the selected records only, in units of the stated currency. Not availab..."
  },
  "... 2 more"
 ],
 "duplicate_warnings": [
  {
   "project_ids": [
    "climate_funds_update:projects-r10",
    "gcf_projects:FP005"
   ],
   "relation_type": "cross_source_reference_code",
   "verification_state": "deterministic_identifier_match",
   "message": "These records are linked as probably the same real-world project in different sources; their amounts are ne..."
  }
 ],
 "field_matrix": {
  "has_description": {
   "climate_funds_update:projects-r10": true,
   "gcf_projects:FP005": false
  },
  "has_sector": {
   "climate_funds_update:projects-r10": true,
   "gcf_projects:FP005": false
  },
  "has_year": {
   "climate_funds_update:projects-r10": true,
   "gcf_projects:FP005": false
  },
  "has_mapped_country": {
   "climate_funds_update:projects-r10": false,
   "gcf_projects:FP005": true
  },
  "has_source_status": {
   "climate_funds_update:projects-r10": false,
   "gcf_projects:FP005": false
  },
  "has_institution": {
   "climate_funds_update:projects-r10": true,
   "gcf_projects:FP005": true
  },
  "has_reported_amount": {
   "climate_funds_update:projects-r10": true,
   "gcf_projects:FP005": true
  },
  "has_amount_with_currency": {
   "climate_funds_update:projects-r10": true,
   "gcf_projects:FP005": true
  },
  "has_dated_amount": {
   "climate_funds_update:projects-r10": true,
   "gcf_projects:FP005": true
  },
  "has_documents": {
   "climate_funds_update:projects-r10": false,
   "gcf_projects:FP005": false
  },
  "has_verified_approval": {
   "climate_funds_update:projects-r10": false,
   "gcf_projects:FP005": true
  }
 },
 "methodology_version": "compassio-comparison-1.1.0",
 "disclaimers": [
  "Decision support only: Compassio does not approve, recommend or allocate real funding.",
  "Historical project funding is not a currently available funding opportunity.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 17. Prioritize (CFU, PAK, energy): call 1

`POST /api/v1/decision/prioritize` -> **200** (70.5 ms)

Request:

```json
{
 "filters": {
  "country": "PAK",
  "source": "climate_funds_update"
 },
 "sectors_of_interest": [
  "energy"
 ],
 "countries_of_interest": [
  "PAK"
 ],
 "page_size": 5
}
```

Response (trimmed):

```json
{
 "items": [
  {
   "rank": 1,
   "project_id": "climate_funds_update:projects-r1115",
   "title": "Combating Climate Change through the Promotion and Application of Sustainable Biomass Energy Technologies i...",
   "source_id": "climate_funds_update",
   "score": "0.8667",
   "components": [
    "{...}",
    "{...}",
    "... 2 more"
   ],
   "applied_weight_total": "10",
   "distinctions": {
    "matches_search": true,
    "matched_filters": "{...}",
    "has_documented_historical_funding": true,
    "documented_funding_basis": "approval 3.44 millions USD from climate_funds_update",
    "current_funding_opportunity": "not_determinable"
   },
   "interpretation": "Ranked for further due diligence under the selected criteria only. A high rank is not a statement of financ..."
  },
  {
   "rank": 2,
   "project_id": "climate_funds_update:projects-r300",
   "title": "(SAP024) Pakistan Distributed Solar Project",
   "source_id": "climate_funds_update",
   "score": "0.8667",
   "components": [
    "{...}",
    "{...}",
    "... 2 more"
   ],
   "applied_weight_total": "10",
   "distinctions": {
    "matches_search": true,
    "matched_filters": "{...}",
    "has_documented_historical_funding": true,
    "documented_funding_basis": "approval 10 millions USD from climate_funds_update",
    "current_funding_opportunity": "not_determinable"
   },
   "interpretation": "Ranked for further due diligence under the selected criteria only. A high rank is not a statement of financ..."
  },
  "... 2 more"
 ],
 "pagination": {
  "page": 1,
  "page_size": 5,
  "total_items": 31,
  "total_pages": 7
 },
 "candidates": 31,
 "methodology_version": "compassio-priority-1.0.0",
 "ranking_fingerprint": "149e0721bece4654be0fc47cb6868f0f634f58cd1a39cc5c34ca0c1bb7d7bc2e",
 "data_version": [
  23,
  23
 ],
 "disclaimers": [
  "Decision support only: Compassio does not approve, recommend or allocate real funding.",
  "Historical project funding is not a currently available funding opportunity.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 18. Prioritize: identical call 2 (same fingerprint)

`POST /api/v1/decision/prioritize` -> **200** (17.0 ms)

Request:

```json
{
 "filters": {
  "country": "PAK",
  "source": "climate_funds_update"
 },
 "sectors_of_interest": [
  "energy"
 ],
 "countries_of_interest": [
  "PAK"
 ],
 "page_size": 5
}
```

Response (trimmed):

```json
{
 "items": [
  {
   "rank": 1,
   "project_id": "climate_funds_update:projects-r1115",
   "title": "Combating Climate Change through the Promotion and Application of Sustainable Biomass Energy Technologies i...",
   "source_id": "climate_funds_update",
   "score": "0.8667",
   "components": [
    "{...}",
    "{...}",
    "... 2 more"
   ],
   "applied_weight_total": "10",
   "distinctions": {
    "matches_search": true,
    "matched_filters": "{...}",
    "has_documented_historical_funding": true,
    "documented_funding_basis": "approval 3.44 millions USD from climate_funds_update",
    "current_funding_opportunity": "not_determinable"
   },
   "interpretation": "Ranked for further due diligence under the selected criteria only. A high rank is not a statement of financ..."
  },
  {
   "rank": 2,
   "project_id": "climate_funds_update:projects-r300",
   "title": "(SAP024) Pakistan Distributed Solar Project",
   "source_id": "climate_funds_update",
   "score": "0.8667",
   "components": [
    "{...}",
    "{...}",
    "... 2 more"
   ],
   "applied_weight_total": "10",
   "distinctions": {
    "matches_search": true,
    "matched_filters": "{...}",
    "has_documented_historical_funding": true,
    "documented_funding_basis": "approval 10 millions USD from climate_funds_update",
    "current_funding_opportunity": "not_determinable"
   },
   "interpretation": "Ranked for further due diligence under the selected criteria only. A high rank is not a statement of financ..."
  },
  "... 2 more"
 ],
 "pagination": {
  "page": 1,
  "page_size": 5,
  "total_items": 31,
  "total_pages": 7
 },
 "candidates": 31,
 "methodology_version": "compassio-priority-1.0.0",
 "ranking_fingerprint": "149e0721bece4654be0fc47cb6868f0f634f58cd1a39cc5c34ca0c1bb7d7bc2e",
 "data_version": [
  23,
  23
 ],
 "disclaimers": [
  "Decision support only: Compassio does not approve, recommend or allocate real funding.",
  "Historical project funding is not a currently available funding opportunity.",
  "... 2 more"
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 19. Hypothetical scenario (equal split of 1,000,000 USD)

`POST /api/v1/decision/scenarios` -> **200** (22.6 ms)

Request:

```json
{
 "budget": {
  "amount": "1000000",
  "currency": "USD"
 },
 "project_ids": [
  "climate_funds_update:projects-r1115",
  "climate_funds_update:projects-r300",
  "climate_funds_update:projects-r315"
 ],
 "method": "equal"
}
```

Response (trimmed):

```json
{
 "scenario_label": null,
 "status": "allocated",
 "budget": {
  "amount": "1000000",
  "currency": "USD",
  "unit": "units"
 },
 "allocated_total": "1000000.00",
 "unallocated": "0.00",
 "conservation_check": "1000000.00 + 0.00 = 1000000.00 (equals the budget)",
 "allocations": [
  {
   "project_id": "climate_funds_update:projects-r1115",
   "title": "Combating Climate Change through the Promotion and Application of Sustainable Biomass Energy Technologies i...",
   "source_id": "climate_funds_update",
   "sector": "Energy generation, renewable sources",
   "country_group": "PAK",
   "weight": "1",
   "weight_basis": "equal weight",
   "allocation": "333333.34",
   "share_of_budget": "0.333333",
   "binding_constraints": [],
   "reference_facts": [
    "{...}",
    "{...}"
   ],
   "warnings": [
    "Whether this record can receive new funding is not determinable from the data."
   ]
  },
  {
   "project_id": "climate_funds_update:projects-r300",
   "title": "(SAP024) Pakistan Distributed Solar Project",
   "source_id": "climate_funds_update",
   "sector": "Energy generation, renewable sources",
   "country_group": "PAK",
   "weight": "1",
   "weight_basis": "equal weight",
   "allocation": "333333.33",
   "share_of_budget": "0.333333",
   "binding_constraints": [],
   "reference_facts": [
    "{...}",
    "{...}"
   ],
   "warnings": [
    "Whether this record can receive new funding is not determinable from the data."
   ]
  },
  "... 1 more"
 ],
 "arithmetic": [
  "Budget B = 1000000 USD (units); 3 selected records.",
  "Round 1: share 1000000.000000 by weight over 3 records (sum of weights 3); scale 1.000000; placed 1000000.0...",
  "... 2 more"
 ],
 "feasibility_warnings": [],
 "assumptions": [
  "Weights: equal (compassio-scenario-1.0.0).",
  "All amounts are in USD (units) as entered; no conversion or inflation adjustment.",
  "... 2 more"
 ],
 "disclosures": [
  "HYPOTHETICAL PLANNING SIMULATION: not a statement that funding is available or that any record can receive ...",
  "Records are historical; Compassio holds no data on currently open funding opportunities.",
  "... 2 more"
 ],
 "methodology_version": "compassio-scenario-1.0.0",
 "request_sha256": "741c3c4af89db227ff433cc45c7e70f2402d70c12327669d16d0ab70f2d3ed03",
 "result_sha256": "c451a301181c40bb7c6df2c94659dabfc414d39dc1b23d5bf41dcf0bab195300",
 "data_version": [
  23,
  23
 ],
 "access": {
  "mode": "hackathon_event",
  "notice": "EVENT DEMONSTRATION ONLY (BATTLEVERSE 2026 (Battle of Intelligence)): served under an organizer authorizati..."
 }
}
```

## 20. Error: compare with one id

`POST /api/v1/decision/compare` -> **422** (25.1 ms)

Request:

```json
{
 "project_ids": [
  "aiddata:35266"
 ]
}
```

Response (trimmed):

```json
{
 "code": "invalid_request",
 "message": "body.project_ids: List should have at least 2 items after validation, not 1",
 "detail": [
  {
   "loc": [
    "body",
    "project_ids"
   ],
   "msg": "List should have at least 2 items after validation, not 1",
   "type": "too_short"
  }
 ]
}
```

## 21. Error: unknown request field

`POST /api/v1/decision/compare` -> **422** (30.5 ms)

Request:

```json
{
 "project_ids": [
  "aiddata:35266",
  "aiddata:54087"
 ],
 "extra": 1
}
```

Response (trimmed):

```json
{
 "code": "invalid_request",
 "message": "body.extra: Extra inputs are not permitted",
 "detail": [
  {
   "loc": [
    "body",
    "extra"
   ],
   "msg": "Extra inputs are not permitted",
   "type": "extra_forbidden"
  }
 ]
}
```

## 22. Error: unsupported scenario objective

`POST /api/v1/decision/scenarios` -> **422** (14.2 ms)

Request:

```json
{
 "budget": {
  "amount": "1",
  "currency": "USD"
 },
 "project_ids": [
  "climate_funds_update:projects-r1115",
  "climate_funds_update:projects-r300",
  "climate_funds_update:projects-r315"
 ],
 "objective": "maximize_emission_reductions"
}
```

Response (trimmed):

```json
{
 "code": "objective_not_supported",
 "message": "Objective 'maximize_emission_reductions' cannot be supported: No measured emission reductions are stored. S..."
}
```

## 23. Error: unknown project

`GET /api/v1/projects/aiddata:example_missing` -> **404** (16.8 ms)

Response (trimmed):

```json
{
 "code": "project_not_found",
 "message": "No project with id aiddata:example_missing"
}
```

## 24. Error: restricted source record

`GET /api/v1/decision/evidence/gcf_historical:1` -> **404** (14.6 ms)

Response (trimmed):

```json
{
 "code": "project_not_found",
 "message": "No project with id gcf_historical:1"
}
```

## 25. Error: ranking without filters

`POST /api/v1/decision/prioritize` -> **422** (7.8 ms)

Request:

```json
{
 "filters": {}
}
```

Response (trimmed):

```json
{
 "code": "candidate_set_too_large",
 "message": "26499 records match; narrow the filters to at most 2000 (e.g. country, source, sector, years or a search te..."
}
```

## 26. Error: review write without token

`POST /api/v1/reviews` -> **403** (22.7 ms)

Request:

```json
{
 "screening_id": "000000000000000000000000000000000000",
 "decision": "agree",
 "reviewer": "example_reviewer"
}
```

Response (trimmed):

```json
{
 "code": "review_writes_disabled",
 "message": "Saving screenings and recording reviews is disabled."
}
```

## 27. Error: oversized body

`POST /api/v1/screening/text` -> **413** (12.3 ms)

Request:

```json
"<300013 raw bytes>"
```

Response (trimmed):

```json
{
 "code": "request_too_large",
 "message": "Request body exceeds 262144 bytes (COMPASSIO_MAX_REQUEST_BODY_BYTES)."
}
```
