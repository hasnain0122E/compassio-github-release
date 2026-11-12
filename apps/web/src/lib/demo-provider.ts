import type { ProjectDetail, ProjectEvidence, ScreeningResponse } from "./api-types";
import { DEMO_NOTICE } from "./demo-mode";

const access = { mode: "public" as const, notice: DEMO_NOTICE };
const disclaimers = ["Synthetic sample data; no actual financing or approval is represented."];
const source = { source_id: "synthetic_demo", name: "Synthetic demo projects", publisher: "COMPASSIO demo", rights_status: "synthetic", access_tier: "public", reference_url: null };
export const demoProjects: ProjectDetail[] = [
  ["pak-flood", "Pakistan flood protection", "Restore wetlands, strengthen flood embankments and install community early warning in Sindh.", "Water resilience", "PAK", "Pakistan", 2025],
  ["pak-solar", "Pakistan solar energy", "Install solar panels and battery storage for rural schools and clinics.", "Solar energy", "PAK", "Pakistan", 2024],
  ["pak-water", "Pakistan water resilience", "Rainwater harvesting and drought resilient irrigation for smallholder farms.", "Water resilience", "PAK", "Pakistan", 2026],
  ["bgd-water", "Bangladesh coastal water resilience", "Improve safe water storage and protect coastal communities against saltwater intrusion.", "Water resilience", "BGD", "Bangladesh", 2025],
  ["ken-solar", "Kenya community solar energy", "Solar microgrids provide renewable electricity to community facilities.", "Solar energy", "KEN", "Kenya", 2026],
  ["pak-road", "Pakistan rural access road", "Resurface a rural road to improve access to markets.", "Transport", "PAK", "Pakistan", 2023],
].map(([id, title, description, sector, iso3, country, year]) => ({
  id: String(id), title: `Synthetic · ${title}`, description: String(description), source,
  source_project_id: String(id), record_level: "project", recipient_label: String(country),
  countries: [{ country_name: String(country), iso3: String(iso3), mapping_method: "synthetic" }],
  multi_country: false, region: null, sector_name: String(sector), sector_code: null, sector_vocabulary: "demo",
  year: Number(year), year_type: "illustrative", date_value: null, date_precision: null, date_estimated: null,
  status: "Synthetic concept", source_reference: "Author-written synthetic example", attributes: {},
  climate_annotations: [], financial_observations: [], data_quality_warnings: [], group: null,
  relationships: [], disclaimers, access, documents: [], enrichments: [],
}));

function evidence(p: ProjectDetail): ProjectEvidence {
  return { project_id: p.id, title: p.title, source, source_project_id: p.id, record_level: "project",
    description: p.description, countries: p.countries, multi_country: false, country_note: "Synthetic country attribution",
    sector: { name: p.sector_name!, code: null, vocabulary: "demo" }, institutions: [], year: p.year,
    year_type: p.year_type, source_status: p.status, verified_approval: null,
    climate_relevance: { status: "no_climate_annotation", basis: "Synthetic example", annotations: [] },
    headline_facts: [], breakdown_facts: [], linked_records: [], documents: [], data_quality_warnings: [],
    completeness: { has_description: true, has_sector: true, has_year: true, has_mapped_country: true,
      has_source_status: true, has_institution: false, has_reported_amount: false, has_amount_with_currency: false,
      has_dated_amount: false, has_documents: false, has_verified_approval: false, missing: ["financial evidence", "documents"] },
    source_reference: p.source_reference, group_key: null, group_meaning: null, limitations: disclaimers };
}
const model = { model_key: "illustrative_demo", engine_label: "Illustrative screening — keyword rules, no ML inference",
  model_version: "demo-rules-1", status: "illustrative_demo", artifact_sha256: "No model artifact", model_fingerprint: "demo-rules-1",
  threshold: 0.5, representation: "Deterministic keyword rules", training_data: "None", intended_use: "Interface demonstration only",
  evaluation: { population: "Not evaluated as a predictive model", independent_generalization_evidence: false },
  artifact_present: false, selectable_now: false };
function screen(text: string): unknown {
  const matches = text.toLowerCase().match(/\b(flood|solar|water|drought|renewable|irrigation|wetlands)\b/g) ?? [];
  const score = matches.length ? 0.75 : 0.25;
  return { screening_id: null, saved: false, model, operational_mode: "illustrative_demo", fallback_used: false,
    prediction: { is_climate_related: score > 0.5, label_score: score, threshold: 0.5,
      band: score > 0.5 ? "clearly_flagged" : "not_flagged", score_semantics: "Illustrative rule-based score; not ML v2 inference" },
    explanation: { method: "Illustrative keyword rules", intercept: 0, logit: 0, faithfulness_abs_error: 0,
      nonzero_features: matches.length, feature_contribution_total: 0, word_contribution_total: null,
      top_positive_features: [], top_negative_features: [], word_attribution_available: false, top_words: [] },
    input_sha256: "Not hashed or saved in demo", guidance: ["Human review required"], limitations: [DEMO_NOTICE, "Fixed rule scores are not actual ML inference."],
    not_predicted: ["Impact", "Funding eligibility"], generated_at: "2026-01-01T00:00:00Z" };
}
function selected(ids?: string[]) { return demoProjects.filter(p => !ids || ids.includes(p.id)); }
function filtered(q: URLSearchParams) {
  return demoProjects.filter(p => (!q.get("q") || `${p.title} ${p.description}`.toLowerCase().includes(q.get("q")!.toLowerCase()))
    && (!q.get("country") || p.countries.some(c => c.iso3 === q.get("country")))
    && (!q.get("sector") || p.sector_name === q.get("sector")) && (!q.get("source") || q.get("source") === source.source_id)
    && (!q.get("year_from") || p.year! >= Number(q.get("year_from"))) && (!q.get("year_to") || p.year! <= Number(q.get("year_to")))
    && q.get("climate_related") !== "true");
}
export function demoRequest(path: string, body?: unknown): unknown {
  const url = new URL(path, "https://demo.invalid");
  const route = url.pathname.replace("/api/v1/", "");
  const q = url.searchParams;
  const input = (body ?? {}) as { title?: string; description?: string; project_ids?: string[] };
  const common = { access, disclaimers };
  if (route === "projects") {
    const rows = filtered(q); const sort = q.get("sort") ?? "id"; const key = sort.replace("-", "") as "id" | "title" | "year";
    rows.sort((a,b) => String(a[key]).localeCompare(String(b[key])) * (sort.startsWith("-") ? -1 : 1));
    const size = Math.max(1, Number(q.get("page_size")) || 12); const page = Math.max(1, Number(q.get("page")) || 1);
    return { ...common, items: rows.slice((page-1)*size,page*size).map(p => ({...p, source_id: source.source_id, description_excerpt: p.description})),
      pagination: { page, page_size: size, total_items: rows.length, total_pages: Math.ceil(rows.length/size) }, applied_filters: Object.fromEntries(q), sort };
  }
  if (route.startsWith("projects/") || route.startsWith("decision/evidence/")) {
    const p = demoProjects.find(p => p.id === decodeURIComponent(route.split("/").at(-1)!));
    if (!p) throw new Error("Synthetic project not found");
    return route.startsWith("projects/") ? p : { ...common, project: evidence(p), methodology_version: "demo-1" };
  }
  if (route === "filters") return { access, sources: [source.source_id], countries: ["PAK", "BGD", "KEN"].map(iso3 => ({iso3, name: demoProjects.find(p=>p.countries[0].iso3===iso3)!.countries[0].country_name, project_rows: demoProjects.filter(p=>p.countries[0].iso3===iso3).length})), sectors: [...new Set(demoProjects.map(p=>p.sector_name))].map(sector_name=>({source_id: source.source_id, sector_name, project_rows: demoProjects.filter(p=>p.sector_name===sector_name).length})), year_ranges: [{source_id: source.source_id, min_year: 2023, max_year: 2026}], sort_options: ["id", "-id", "title", "-title", "year", "-year"], climate_annotation_filter: "No research annotations on synthetic records" };
  if (route === "sources") return { access, sources: [{...source, served_in_current_mode: true, license_notes: disclaimers[0]}] };
  if (route === "models") return { models: [model], operational: { inference_authorized: true, default_model: null, review_writes_enabled: false, notice: DEMO_NOTICE }, prediction_scope: DEMO_NOTICE };
  if (route.startsWith("screening/")) {
    const p = route.startsWith("screening/projects/") ? demoProjects.find(p=>p.id===route.split("/").at(-1)) : null;
    if (route.startsWith("screening/projects/") && !p) throw new Error("Synthetic project not found");
    const result = screen(p ? `${p.title} ${p.description}` : `${input.title ?? ""} ${input.description ?? ""}`) as ScreeningResponse;
    return {...result, source_evidence: p ? {project_id:p.id, source_id:source.source_id, source_reference:p.source_reference, title:p.title, description:p.description, rights_status:"synthetic", model_input_permission:"demo"} : null};
  }
  if (route === "decision/compare") return { ...common, projects: selected(input.project_ids).map(evidence), comparable_groups: [], duplicate_warnings: [], field_matrix: Object.fromEntries(Object.keys(evidence(demoProjects[0]).completeness).filter(k=>k!=="missing").map(k=>[k,Object.fromEntries(selected(input.project_ids).map(p=>[p.id, evidence(p).completeness[k as keyof ReturnType<typeof evidence>["completeness"]]]))])), methodology_version: "demo-1" };
  if (route === "decision/prioritize") {
    const request = body as {filters?: {project_ids?: string[]}; weights?: Record<string, number | string>};
    const rows = selected(request.filters?.project_ids);
    return {...common, items: rows.map((p,i)=>({rank:i+1,project_id:p.id,title:p.title,source_id:source.source_id,
      score:"0.000",components:[],applied_weight_total:"0",distinctions:{matches_search:true,matched_filters:{},has_documented_historical_funding:false,documented_funding_basis:"Synthetic example, no financial evidence"},
      interpretation:"All examples tie: no verified climate labels or financing. Source order breaks ties; illustrative review only."})),
      candidates:rows.length,pagination:{page:1,page_size:10,total_items:rows.length,total_pages:1},methodology_version:"demo-1",ranking_fingerprint:"synthetic-ties",data_version:[1]};
  }
  if (route === "decision/scenarios") {
    const request = body as {budget:{amount:string | number;currency:string;unit?:string};scenario_label?:string};
    return {access,scenario_label:request.scenario_label,status:"infeasible",budget:{...request.budget,amount:String(request.budget.amount)},
      allocated_total:"0",unallocated:String(request.budget.amount),conservation_check:"0 + unallocated = budget",
      allocations:[],arithmetic:[],feasibility_warnings:["Synthetic examples have no verified financing; the demo leaves the entire hypothetical budget unallocated."],
      assumptions:disclaimers,disclosures:disclaimers,methodology_version:"demo-1",request_sha256:"not hashed in demo",result_sha256:"not hashed in demo",data_version:[1]};
  }
  if (route === "analytics/overview") return { ...common, sources: [{...source, record_level:"project", project_rows:6, distinct_groups:6, rows_with_description:6, rows_with_year:6, min_year:2023,max_year:2026,multi_country_rows:0,pakistan_rows:4, observations_by_flow:{}, climate_annotations:{},top_warnings:{}}], cross_source_links:{},counting_rules:disclaimers };
  if (route === "analytics/metrics") return { access, metrics: [] };
  if (route === "analytics/coverage") return {access, data_version:[1], sources:[{...source, served_in_current_mode:true,project_rows:6, financial_observation_rows:0, reported_amount_rows:0,min_year:2023,max_year:2026,snapshot_ids:[],last_completed_import:null,version_info:"Synthetic demo 1"}]};
  if (route === "analytics/approved-vs-disbursed") return {...common,country:q.get("country"),sources:[]};
  if (route === "analytics/climate-distribution") return {access,country:q.get("country"),measure:"project_record_count",distributions:[],statement:"Synthetic records have no research annotations."};
  if (route === "analytics/institutions") return {...common,groups:[],universe:"Synthetic demo",note:disclaimers[0]};
  if (route.startsWith("analytics/country-profile/")) return {...common,country:route.split("/").at(-1),project_counts:[],metrics:[],top_sectors:[],climate:{distributions:[],statement:disclaimers[0]},country_aggregates_endpoint:""};
  if (route.startsWith("analytics/funding-by-") || route === "analytics/trends") return {...common,status:"unavailable",unavailable_reason:"Synthetic demo records have no actual financial observations.",groups:[],points:[],declaration:{label:"Synthetic demo ? no financial observations",source_id:source.source_id,flow_kind:"none",price_basis:"not_applicable",year_basis:"illustrative",currency:null,is_funding:false,universe:"Synthetic projects",financial_meaning:"No actual financing",known_exclusions:[],excluded_records:{}}};
  if (route === "decision/methodology") return {...common,scenario_methods:{equal:"Illustrative equal split",sector_priority:"Illustrative sector weighting",priority_score:"Illustrative priority weighting"},supported_objectives:["allocate_by_weights"],rules:[],public_display:{},financial_meanings:{},unsupported_objectives:{impact:"No verified impact in synthetic data"},methodology_version:"demo-1"};
  throw new Error("This research-only operation is unavailable in the self-contained demo.");
}
