import type { PlannedPageProps } from "./PlannedPage";

// Screen descriptions from the BRD (§25, §55). Replaced by real screens phase by phase.
export const PLANNED: Record<string, PlannedPageProps> = {
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
