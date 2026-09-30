import type { PlannedPageProps } from "./PlannedPage";

// Screen descriptions from the BRD (§25, §55). Replaced by real screens phase by phase.
export const PLANNED: Record<string, PlannedPageProps> = {
  command: {
    eyebrow: "Portfolio", title: "Command Center", phase: "Phase 8",
    lede: "Portfolio view of model risk: inventory, tiering, revalidation, findings, monitoring and governance score.",
    features: [
      "Total models, by tier and by lifecycle phase",
      "Revalidation queue: scheduled, due soon, overdue",
      "Open findings and overdue critical findings",
      "Monitoring breaches and completion",
      "DQ health and portfolio governance score",
      "Rule-generated insights linking to the source record",
    ],
  },
  operations: {
    eyebrow: "Portfolio", title: "Operations Board", phase: "Phase 2 / 8",
    lede: "Lifecycle pipeline and inventory table with combined filters and CSV export.",
    features: [
      "Filters: model type, tier, phase, business line, monitoring status, revalidation status, findings, search",
      "Pipeline of model cards by displayed lifecycle column",
      "Sortable inventory table with export of filtered rows",
    ],
  },
  model360: {
    eyebrow: "Portfolio", title: "Model 360", phase: "Phase 2 / 8",
    lede: "Everything about one model: profile, lifecycle, tier, owners, validation, findings, approvals, documents, monitoring, CDE/DQ, score and audit history.",
    features: [
      "Profile, lifecycle stepper, tier with override history",
      "Validation history, findings, MRC decisions and conditions",
      "Documents and evidence completeness",
      "Monitoring tab: plan, latest run, KPI scorecard, trends, breaches, evidence",
      "Explainable governance score breakdown",
    ],
  },
  monitoring: {
    eyebrow: "Portfolio", title: "Monitoring Dashboard", phase: "Phase 6",
    lede: "Ongoing monitoring across the portfolio: runs, KPI results against thresholds, breaches and repeated failures.",
    features: [
      "Models monitored, runs completed and overdue",
      "Models with KPI failures, warnings, critical and repeated breaches",
      "Pass/Warn/Fail distribution; breaches by severity, model type and business line",
      "KPI, performance, drift and DQ trends with drill-down to the run",
      "Work queue: overdue monitoring, failed KPI, missing evidence, sign-off pending",
    ],
  },
  dataAudit: {
    eyebrow: "Portfolio", title: "Data Audit", phase: "Phase 7",
    lede: "Critical data elements, data-quality rules, results and issues.",
    features: ["CDE registry", "DQ rules and thresholds", "DQ results by run", "DQ issue log"],
  },
  documents: {
    eyebrow: "Evidence & data", title: "Document Centre", phase: "Phase 4 / 5",
    lede: "Governance evidence: single, batch, folder and ZIP upload with versioning, classification, extraction and review.",
    features: [
      "Folder tree and document list with search and filters",
      "Upload: single file, multiple files, folder, ZIP package, manifest",
      "SHA-256 duplicate detection and version history",
      "Extraction and review queue with human confirmation",
      "Folder-level evidence completeness view",
    ],
  },
  imports: {
    eyebrow: "Evidence & data", title: "Import Centre", phase: "Phase 3",
    lede: "Structured data loads from Excel and CSV templates with validation, preview and partial acceptance.",
    features: [
      "Template list T01–T18 in load order, with blank downloads",
      "Single and batch upload",
      "Row-level validation, preview and explicit Load",
      "Error report download and import history",
    ],
  },
};
