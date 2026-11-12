/** Display labels for backend codes. Meanings themselves always come from the API. */

export const SOURCE_SHORT: Record<string, string> = {
  synthetic_demo: "Synthetic demo projects",
  aiddata: "AidData",
  adb_pakistan: "ADB Pakistan",
  climate_funds_update: "Climate Funds Update",
  gcf_projects: "GCF projects",
  gcf_api_projects: "GCF API",
  gcf_readiness: "GCF readiness",
  gcf_countries: "GCF countries",
  climate_project_explorer: "Climate Project Explorer",
  research_paper: "Qi et al. 2026 annotations",
  gcf_historical: "GCF historical (restricted)",
};

export function sourceName(id: string): string {
  return SOURCE_SHORT[id] ?? id;
}

/** What one row of each source is (from the backend's record_level). */
export const RECORD_LEVEL: Record<string, string> = {
  aiddata_record: "financing records",
  cfu_project_row: "climate fund project rows",
  gcf_funded_project: "funded projects",
  gcf_readiness_grant: "readiness grants",
  adb_financing_instrument: "financing instruments",
};

export type MeaningTone = "funding" | "notFunding" | "pledge";

/** Financial meaning (backend enum) -> short label and whether it is money flowing to a project. */
export const MEANING: Record<string, { short: string; tone: MeaningTone }> = {
  historical_commitment: { short: "Commitment", tone: "funding" },
  approval: { short: "Approval", tone: "funding" },
  disbursement: { short: "Disbursement", tone: "funding" },
  co_financing: { short: "Co-financing", tone: "funding" },
  readiness_grant: { short: "Readiness grant", tone: "funding" },
  deposit_into_fund: { short: "Deposit into fund", tone: "funding" },
  pledge_not_commitment: { short: "Pledge", tone: "pledge" },
  repayment_not_funding: { short: "Repayment (not funding)", tone: "notFunding" },
  total_project_cost: { short: "Total project cost", tone: "notFunding" },
};

/** ML prediction band in plain language. */
export const BAND: Record<string, { title: string; body: string }> = {
  clearly_flagged: {
    title: "Likely climate-related",
    body: "The text reads like projects that donors marked as climate-related. Worth a closer review.",
  },
  borderline: {
    title: "Borderline",
    body: "The score is close to the decision line. A person should read this one carefully.",
  },
  not_flagged: {
    title: "Not flagged",
    body: "The text does not read like donor-marked climate projects. It may still have climate aspects the text does not mention.",
  },
};

/** Flow kind -> financial meaning (mirrors the backend's evidence MEANINGS table). */
export const FLOW_MEANING: Record<string, string> = {
  commitment: "historical_commitment",
  pledge: "pledge_not_commitment",
  approval: "approval",
  gcf_financing: "approval",
  disbursement: "disbursement",
  repayment_principal: "repayment_not_funding",
  repayment_interest: "repayment_not_funding",
  co_financing: "co_financing",
  total_project_cost: "total_project_cost",
  readiness_grant: "readiness_grant",
  deposit: "deposit_into_fund",
};
