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
};
