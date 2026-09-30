# Model Governance Management Information System (MRM/MIS)
## Business Requirements Document (BRD) — Development Specification

**Version:** 1.0  
**Date:** 30 September 2026  
**Purpose:** Development specification for Claude Code  
**Status:** Proposed / Development Baseline  
**Source documents:** Existing Model Governance MIS requirements/design, input templates, and HTML prototype.

---

# 1. Executive Summary

The objective is to develop a **Model Governance Management Information System (MRM/MIS)** that provides a central, auditable view of the model inventory, model lifecycle, validation, findings, approvals/MRC decisions, model documentation, monitoring results, critical data elements, data-quality results, governance scores and management information.

The system shall support both:

1. **Structured data ingestion** through Excel/CSV templates, and
2. **Unstructured evidence ingestion** through individual documents, multiple documents, and complete folder structures.

The existing requirements already define a strong initial capability: template-driven onboarding, model inventory, validation history, findings, approvals, CDE/DQ information, KPI results, performance curves, governance scoring, Model 360, Command Center, Operations Board, Data Audit, Audit Copilot, document extraction and audit trail.

This BRD extends that design in four important areas:

- **Model Monitoring:** ongoing monitoring plans, monitoring runs, KPI/threshold evaluation, performance deterioration, drift/stability, backtesting, data-quality monitoring, breaches, alerts, issues and evidence.
- **Document Management:** individual and batch document uploads, document classification, versioning, metadata, duplicate detection, extraction, review/confirmation and traceability.
- **Batch Upload:** users can upload multiple files in one operation, including mixed document types and structured data files.
- **Folder/Package Upload:** users can upload a folder structure or ZIP package while preserving the hierarchy and establishing relationships between folders, documents, models, monitoring periods and governance records.

The target architecture proposed in this BRD is:

**React + TypeScript frontend → Python/FastAPI backend → PostgreSQL → MinIO/S3-compatible object storage → Redis + Celery/RQ for asynchronous jobs → optional pgvector for semantic document search → Claude/other LLM through a server-side AI service.**

The system shall be designed as a reusable enterprise-style platform rather than a demo hard-coded around the existing seed data.

---

# 2. Business Objectives

## 2.1 Primary objectives

The system shall:

1. Maintain a complete and authoritative model inventory.
2. Provide a single source of truth for model governance information.
3. Track the full model lifecycle from initiation through retirement.
4. Track validation activities and validation outcomes.
5. Track findings, remediation and overdue issues.
6. Track MRC/approval decisions and conditions.
7. Maintain model documentation and supporting evidence.
8. Monitor model performance and model risk indicators.
9. Track KPI thresholds, breaches and trends.
10. Track data-quality rules and CDE health.
11. Calculate configurable model governance scores.
12. Provide management dashboards and operational work queues.
13. Provide an auditable history of all material changes.
14. Support individual, batch and folder-based data/document ingestion.
15. Reduce manual effort in onboarding and maintaining model governance records.
16. Provide controlled AI-assisted document extraction and governance querying.
17. Preserve evidence and lineage so users can answer:
   - What happened?
   - When did it happen?
   - Who changed it?
   - What evidence supports it?
   - Which model does it relate to?
   - Which monitoring/validation run produced it?

---

# 3. Scope

## 3.1 In scope

### Model inventory
- Model registration.
- Model metadata.
- Model owners/developers/validators.
- Lifecycle phase.
- Model version.
- Business line.
- Model type/subtype.
- Risk tier.
- Tiering questionnaire.
- Tier override.
- Revalidation frequency.
- Last validation date.
- Next validation due date.
- Model relationships and successor models.

### Governance
- Validation history.
- Findings.
- Remediation status.
- Approvals.
- MRC decisions.
- Conditions.
- Governance score.
- Governance insights.
- Segregation of duties.

### Monitoring
- Monitoring plans.
- Monitoring frequency.
- Monitoring KPIs.
- Thresholds.
- Warning bands.
- Monitoring runs.
- Monitoring results.
- Historical trends.
- Performance metrics.
- Backtesting.
- Drift/stability indicators.
- Data-quality monitoring.
- Breaches.
- Alerts.
- Monitoring issues.
- Evidence.
- Monitoring sign-off/review.

### Documents
- Individual upload.
- Multi-file upload.
- Folder upload.
- ZIP/package upload.
- Folder hierarchy preservation.
- Document metadata.
- Document versioning.
- Document classification.
- Document-to-model association.
- Document-to-validation association.
- Document-to-monitoring-run association.
- Document extraction.
- Human confirmation.
- Document completeness assessment.
- Document search.
- Download/view evidence.
- Document audit trail.

### Structured ingestion
- Excel.
- CSV.
- Batch Excel/CSV upload.
- Validation.
- Preview.
- Partial acceptance.
- Error reports.
- Import history.
- Re-import/update.
- Idempotency.
- Load dependencies.

### Management information
- Command Center.
- Operations Board.
- Model 360.
- Monitoring Dashboard.
- Data Audit.
- Import Center.
- Document Centre.
- Admin.
- Audit Trail.
- Audit Copilot.

---

# 4. Out of Scope for Initial Release

Unless explicitly enabled as a later phase:

- Direct integration with enterprise GRC platforms.
- Automatic regulatory submission.
- Automatic model changes.
- Automatic approval of findings.
- Automatic approval of extracted document content.
- Automatic lifecycle phase changes based solely on monitoring.
- Production model execution.
- Direct access to model source code repositories.
- Real-time trading/model execution systems.
- Automated regulatory interpretation.
- Automated replacement of human validation judgement.

The system may identify, calculate, flag and recommend workflow actions, but governance decisions remain human-controlled.

---

# 5. User Roles

The initial role model shall include:

| Role | Core responsibility |
|---|---|
| Admin | Configuration, users, policies, imports, system administration |
| Model Owner | Own model governance, documents, monitoring and remediation |
| Model Developer | Maintain development-related information and evidence |
| Validator | Perform/record independent validation and upload validation evidence |
| MRC Member | Review approvals, decisions and conditions |
| Auditor | Read-only governance and evidence access |
| Executive | Read-only management information |
| Monitoring Analyst | Maintain monitoring definitions/results and investigate breaches |
| Data Owner | Maintain CDE/data-quality information |
| Platform Administrator | Technical administration, storage and processing configuration |

A user may have one or more functional roles in the production version.

---

# 6. Functional Requirements

## 6.1 Model Inventory

### REQ-INV-01 — Model registration
The system shall allow an authorised user to create a model record.

Mandatory information shall include:
- Model ID
- Model name
- Model type
- Model subtype
- Purpose
- Business line
- Owner
- Developer
- Validator where applicable
- Lifecycle phase
- Version
- Go-live date where applicable
- Revalidation frequency
- Last validation date where applicable
- Tiering answers

### REQ-INV-02 — Model editing
Authorised users shall be able to edit model metadata.

Every edit shall generate an audit event containing:
- User
- Role
- Timestamp
- Entity
- Entity ID
- Before value
- After value

### REQ-INV-03 — Segregation of duties
The system shall prevent a validator from being the same person as the model owner or developer.

The check shall operate:
- During manual model creation.
- During manual editing.
- During structured import.
- During batch import.

### REQ-INV-04 — Model version
Model version shall be tracked independently from the model ID.

The system shall support multiple versions where required.

### REQ-INV-05 — Model relationships
The system shall support:
- Successor model.
- Predecessor model.
- Related model.
- Parent/child model.
- Model family/group.

---

# 7. Risk Tiering

The initial design contains four tiering questions:

1. Materiality.
2. Complexity.
3. Reliance.
4. Regulatory use.

Each is scored 1–3.

The system shall calculate:

**Tier Score = Materiality + Complexity + Reliance + Regulatory Use**

Initial policy thresholds:

- High: >= 10
- Medium: 7–9
- Low: <= 6

These values must be configuration-driven.

The system shall support an authorised tier override with:
- Override tier.
- Reason.
- User.
- Timestamp.
- Previous calculated tier.
- New tier.

The system shall never delete the calculated tier when an override is applied.

---

# 8. Model Lifecycle

The system shall support:

1. Initiation
2. Development
3. Validation
4. Implementation
5. Monitoring
6. Reg/Audit
7. Retirement

Revalidation shall be represented as a governance work state and not necessarily as a separate lifecycle phase.

The system shall display:
- Current phase.
- Previous phase.
- Phase transition date.
- User who performed the transition.
- Optional transition reason.
- Required evidence for the transition.

---

# 9. Validation Management

The system shall maintain validation exercises including:

- Validation ID.
- Model.
- Validation type.
- Validator.
- Start date.
- Completion date.
- Outcome.
- Validation report.
- Findings.
- Recommendations.

Validation types:
- Initial.
- Periodic.
- Targeted.
- Change.

Outcomes:
- Approved.
- Conditional.
- Rejected.
- In Progress.

The system shall calculate validation currency against the configured revalidation frequency.

---

# 10. Revalidation Management

The system shall calculate:

**Next Validation Date = Last Validation Date + Revalidation Frequency**

Supported frequencies:
- Monthly
- Quarterly
- Semi-annual
- Annual
- Biennial

The system shall classify a model as:
- Scheduled
- Due Soon
- Overdue

The lead-time and due-soon thresholds shall be configurable.

The system shall display:
- Next due date.
- Days remaining.
- Days overdue.
- Risk tier.
- Owner.
- Last validation.
- Latest outcome.

---

# 11. Findings and Remediation

Each finding shall contain:

- Finding ID
- Model
- Validation
- Title
- Description
- Severity
- Category
- Status
- Owner
- Raised date
- Due date
- Closed date
- Source
- Evidence
- Root cause
- Management response
- Remediation action

Initial severity:
- Critical
- Medium
- Low

Initial status:
- Open
- In Progress
- Closed

Additional recommended status:
- Accepted Risk
- Deferred
- Rejected

The system shall calculate:
- Days open.
- Days overdue.
- Number of overdue findings.
- Critical overdue findings.
- Finding ageing.

---

# 12. MRC and Approval Management

The system shall maintain:

- Approval ID.
- Model.
- Decision date.
- Forum.
- Decision type.
- Decision.
- Conditions.
- Condition due date.
- Condition status.
- Supporting document.

Decisions:
- Approved
- Conditional
- Rejected

Conditional decisions shall remain visible until all conditions are closed.

---

# 13. MODEL MONITORING — NEW CORE REQUIREMENT

## 13.1 Monitoring objective

The Model Monitoring capability shall provide an ongoing mechanism to determine whether a model remains within approved performance, stability, data-quality and governance boundaries after implementation.

Monitoring shall be evidence-based and time-series oriented.

The system shall distinguish:

- Monitoring definition.
- Monitoring run.
- Monitoring result.
- Threshold.
- Breach.
- Alert.
- Investigation.
- Finding/issue.
- Resolution.
- Evidence.

---

# 14. Monitoring Plan

Each production/monitoring model shall have a Monitoring Plan.

A Monitoring Plan shall contain:

- Monitoring plan ID.
- Model ID.
- Model version.
- Effective date.
- Monitoring owner.
- Reviewer.
- Monitoring frequency.
- Monitoring methodology.
- Required KPIs.
- Thresholds.
- Warning thresholds.
- Escalation thresholds.
- Required data sources.
- Required CDEs.
- Required monitoring reports.
- Review calendar.
- Approval status.
- Last review date.
- Next review date.

The monitoring plan shall be versioned.

Example:

| Attribute | Example |
|---|---|
| Model | M-0012 |
| Frequency | Quarterly |
| Owner | Model Owner |
| Reviewer | Validator |
| KPI | Gini |
| Target | >= 0.65 |
| Warning | 0.6175–0.65 |
| Breach | < 0.6175 |
| Data quality | >= 98% |
| Drift | PSI <= 0.10 |
| Review | Quarterly |

---

# 15. Monitoring Metrics

The system shall support configurable monitoring metrics rather than hard-coding a fixed list.

Metric categories shall include:

### 15.1 Discrimination/performance
Examples:
- Gini.
- AUC.
- KS.
- Accuracy.
- Precision.
- Recall.
- F1.
- Brier score.

### 15.2 Calibration
Examples:
- Calibration error.
- Observed vs predicted default rate.
- Predicted vs actual.
- Calibration slope/intercept.

### 15.3 Stability/drift
Examples:
- PSI.
- CSI.
- Population distribution change.
- Characteristic drift.
- Feature distribution drift.

### 15.4 Forecast/error metrics
Examples:
- MAE.
- MAPE.
- RMSE.
- Forecast bias.

### 15.5 Data quality
Examples:
- Completeness.
- Accuracy.
- Validity.
- Timeliness.
- Uniqueness.
- Referential integrity.

### 15.6 Business outcome monitoring
Examples:
- Actual loss vs predicted loss.
- Actual delinquency vs predicted PD.
- Exposure movement.
- Utilisation.
- Portfolio mix.

---

# 16. Monitoring Thresholds

Each monitoring metric shall support:

- Target/threshold.
- Warning threshold.
- Breach threshold.
- Direction:
  - Higher is better.
  - Lower is better.
  - Within range.
- Unit.
- Frequency.
- Applicable model types.
- Effective date.

Threshold changes shall be versioned and audited.

Historical results shall continue to use the threshold applicable at the time of the monitoring run.

---

# 17. Monitoring Run

A Monitoring Run represents one execution/review cycle.

Example:

**M-0012 / 2026-Q3 Monitoring Run**

A run shall contain:

- Run ID.
- Model.
- Model version.
- Period.
- Run date.
- Monitoring type.
- Data period.
- Status.
- Reviewer.
- Sign-off.
- Evidence package.
- Overall result.

Run status:
- Not Started
- In Progress
- Completed
- Under Review
- Approved
- Rejected

---

# 18. Monitoring Result

Every metric evaluated in a run shall create a Monitoring Result.

Fields:

- Monitoring result ID.
- Run ID.
- Metric ID.
- Actual value.
- Expected value.
- Threshold.
- Warning threshold.
- Status.
- Previous value.
- Change percentage.
- Evidence.
- Comment.
- Reviewer.
- Review status.

Status:
- Pass
- Warn
- Fail
- Not Available
- Not Applicable

---

# 19. Monitoring Trend Analysis

The system shall display historical monitoring results.

For each metric:
- Current value.
- Previous value.
- 4-period trend where available.
- 8-period trend where available.
- Target.
- Warning band.
- Breach band.

The system shall support charts such as:

- Metric trend.
- Actual vs threshold.
- Predicted vs actual.
- PSI trend.
- Gini/AUC trend.
- DQ trend.
- Breach history.

The user shall be able to drill from a trend point to the underlying monitoring run.

---

# 20. Monitoring Breach Management

A monitoring breach shall be created when a metric violates its configured threshold.

A breach shall contain:

- Breach ID.
- Model.
- Model version.
- Monitoring run.
- Metric.
- Actual value.
- Threshold.
- Severity.
- Detected date.
- Owner.
- Due date.
- Status.
- Root cause.
- Impact assessment.
- Management response.
- Resolution.
- Evidence.

The system shall support:

- New.
- Acknowledged.
- Under Investigation.
- Action Required.
- Closed.
- Accepted Risk.

A monitoring breach may optionally generate a formal model-risk finding.

---

# 21. Monitoring Escalation

Severity may be determined by configurable rules such as:

- High-risk model + failed critical KPI = Critical.
- Repeated warning for N periods = Escalation.
- Repeated failure = Critical/High.
- Material data-quality failure = High.
- Regulatory KPI failure = High/Critical.

These rules must be configurable rather than hard-coded.

The system shall record the rule that generated the escalation.

---

# 22. Repeated Breach Detection

The system shall identify repeated failures.

Examples:

- Same KPI fails for 2 consecutive periods.
- Same KPI fails for 3 of the last 4 periods.
- PSI remains above threshold for multiple periods.
- Data-quality rule fails repeatedly.
- Performance declines continuously.

The system shall present these as governance insights.

The system shall not automatically change the model lifecycle phase unless such automation is explicitly configured by policy.

---

# 23. Backtesting

The system shall support backtesting results as a monitoring category.

Each backtest shall contain:

- Backtest ID.
- Model.
- Model version.
- Methodology.
- Test period.
- Metric.
- Expected value.
- Actual value.
- Result.
- Threshold.
- Outcome.
- Supporting evidence.

Backtesting shall be shown separately from routine monitoring.

---

# 24. Monitoring Evidence

A monitoring run shall support multiple evidence files.

Examples:
- Monitoring report.
- KPI output.
- Data-quality report.
- Backtesting report.
- Drift report.
- Management commentary.
- Approval/sign-off.

Every evidence document shall be linked to:
- Model.
- Model version.
- Monitoring run.
- Metric where applicable.

---

# 25. Monitoring Dashboard

Add a dedicated **Monitoring Dashboard**.

The dashboard shall contain:

### Portfolio monitoring tiles
- Models monitored this period.
- Monitoring runs completed.
- Monitoring runs overdue.
- Models with KPI failures.
- Models with warnings.
- Models with critical breaches.
- Models with repeated breaches.
- Models with data-quality failures.
- Models requiring review.

### Charts
- Pass/Warn/Fail distribution.
- Breaches by severity.
- Breaches by model type.
- Breaches by business line.
- KPI trend.
- Performance trend.
- Drift trend.
- DQ trend.
- Monitoring completion trend.

### Work queue
- Overdue monitoring.
- Failed KPI.
- Critical breach.
- Repeated breach.
- Evidence missing.
- Review/sign-off pending.

---

# 26. Model 360 — Monitoring Section

Model 360 shall contain a dedicated Monitoring tab.

Sections:

1. Monitoring Plan.
2. Current monitoring status.
3. Latest monitoring run.
4. KPI scorecard.
5. Performance trend.
6. Stability/drift.
7. Data quality.
8. Backtesting.
9. Breaches.
10. Monitoring findings.
11. Monitoring evidence.
12. Historical runs.

The user shall be able to drill from:
**Model → Monitoring Run → Metric → Result → Evidence/Breach.**

---

# 27. DOCUMENT MANAGEMENT — NEW CORE REQUIREMENT

The document capability shall be treated as a document management subsystem rather than only a document upload field.

A document shall have:

- Document ID.
- File name.
- File type.
- MIME type.
- Size.
- Hash.
- Model ID.
- Model version.
- Document type.
- Document subtype.
- Version.
- Effective date.
- Uploaded date.
- Uploaded by.
- Source.
- Folder ID.
- Parent folder.
- Extraction status.
- Review status.
- Classification status.
- Storage location.
- Retention metadata.
- Confidentiality classification where required.

---

# 28. Document Types

Initial document types:

- Terms of Reference.
- Model Development Document.
- Validation Report.
- Monitoring Report.
- Backtesting Report.
- Model Approval/MRC Paper.
- Model Change Document.
- Data Quality Report.
- Regulatory/Audit Evidence.
- Model Inventory Evidence.
- Other.

The list shall be configurable.

---

# 29. Individual Document Upload

Users shall be able to upload one document.

Workflow:

**Select Model → Select Document Type → Select Version → Upload → Validate → Extract → Review → Confirm → Store**

The user shall see:
- File name.
- Size.
- File type.
- Model.
- Document type.
- Version.
- Upload progress.
- Processing status.
- Extraction status.
- Review status.

---

# 30. Batch Document Upload

Users shall be able to upload multiple files in a single operation.

Example:

```
M-0012/
    TOR.pdf
    MDD.pdf
    Validation_Report_2026.pdf
    Monitoring_Report_Q2_2026.pdf
    Backtesting_Q2_2026.xlsx
```

The user shall be able to upload all files together.

The system shall:
1. Detect every file.
2. Validate file type.
3. Calculate checksum.
4. Detect duplicates.
5. Determine folder path.
6. Identify candidate model.
7. Identify candidate document type.
8. Extract metadata where possible.
9. Queue processing.
10. Show progress.
11. Produce a batch summary.

---

# 31. Folder Upload

The user shall be able to select a local folder and upload it.

The system shall preserve:

- Folder name.
- Nested folders.
- Relative file path.
- File name.
- Folder hierarchy.

Example:

```
Model_Governance/
├── Credit_Risk/
│   ├── M-0012/
│   │   ├── Governance/
│   │   │   ├── TOR.pdf
│   │   │   └── MDD.pdf
│   │   ├── Validation/
│   │   │   └── Validation_Report.pdf
│   │   └── Monitoring/
│   │       ├── 2026_Q1/
│   │       └── 2026_Q2/
│   └── M-0042/
└── Forecasting/
    └── M-0076/
```

The system shall preserve this logical structure.

---

# 32. ZIP Package Upload

Because browser folder upload support varies, the system shall also support ZIP package upload.

The system shall:
- Accept ZIP.
- Scan contents.
- Reject unsupported file types.
- Prevent path traversal.
- Preserve relative paths.
- Extract files into controlled storage.
- Create folder records.
- Process each document asynchronously.
- Provide a package-level processing report.

---

# 33. Folder-to-Model Mapping

The system shall support multiple mapping methods.

### Method A — Folder naming convention

Example:

`/M-0012/Validation/`

The system identifies:
- Model = M-0012
- Area = Validation

### Method B — User mapping

The system presents:

| Folder | Candidate model | User action |
|---|---|---|
| M-0012 | M-0012 Wholesale PD | Confirm |
| M-0042 | M-0042 ALM | Confirm |

### Method C — Metadata extraction

The system extracts model IDs/model names from documents.

### Method D — Manifest file

The user may provide:

`manifest.xlsx`

containing:
- File path.
- Model ID.
- Document type.
- Version.
- Effective date.

The manifest shall override heuristic classification.

---

# 34. Document Classification

Classification may use:

1. Folder name.
2. File name.
3. Manifest.
4. Document content.
5. AI extraction.

Classification shall produce:
- Document type.
- Confidence.
- Reason.

AI classification shall never silently commit governance data without human confirmation where the classification affects material governance records.

---

# 35. Duplicate Documents

The system shall calculate a SHA-256 checksum.

Duplicate logic shall identify:
- Exact file duplicate.
- Same document with different filename.
- Same document version.
- Potential duplicate requiring user review.

The system shall not create duplicate records for exact re-upload unless the user explicitly chooses to create a new version.

---

# 36. Document Versioning

Documents shall support versions:

`1.0 → 1.1 → 2.0`

The system shall maintain:
- Current version.
- Previous versions.
- Uploaded date.
- Uploaded by.
- Change reason.

Historical versions must remain available.

---

# 37. Document Extraction

Existing extraction requirements shall be retained.

Supported initial extraction:

### ToR
- Model name.
- Purpose.
- Scope.
- Intended use.
- Planned dates.

### MDD
- Required section presence.
- Assumptions.
- Limitations.

### Validation Report
- Outcome.
- Findings.
- Severity.
- Category.
- Description.
- Recommended due date.

### Monitoring Report
Additional extraction:
- Monitoring period.
- Overall monitoring conclusion.
- KPI results.
- Failed metrics.
- Warning metrics.
- Breaches.
- Management commentary.
- Recommended actions.

AI output shall be:
**Extracted → Validated → Human Reviewed → Confirmed → Persisted.**

---

# 38. Document Review Queue

The Document Centre shall contain a Review Queue.

Columns:
- Document.
- Model.
- Document type.
- Version.
- Extraction status.
- Classification confidence.
- Review status.
- Uploaded by.
- Uploaded date.

Review actions:
- Confirm.
- Edit.
- Reject.
- Reclassify.
- Re-run extraction.
- Download original.

---

# 39. Folder-Level Governance View

The system shall provide a package/folder view.

Example:

**M-0012 Governance Evidence**

```
Governance
 ├── ToR                    ✓
 ├── MDD                    ✓
 ├── Approval Paper         ✓
Validation
 └── Validation Report      ✓
Monitoring
 ├── 2026 Q1                ✓
 ├── 2026 Q2                ⚠
 └── 2026 Q3                ✕
```

The system shall highlight missing expected evidence.

---

# 40. DOCUMENT COMPLETENESS

Document completeness shall be calculated based on:

- Lifecycle phase.
- Required document policy.
- Model type where applicable.
- Model risk tier where applicable.
- Monitoring requirements.

Example:

Development:
- ToR
- MDD

Validation:
- ToR
- MDD
- Validation Report

Production:
- ToR
- MDD
- Validation Report
- Approval evidence
- Monitoring plan

The required-document policy shall be configurable.

---

# 41. DATA INGESTION FRAMEWORK

The ingestion framework shall support:

### Structured
- XLSX.
- CSV.
- JSON where enabled.
- API payloads in future.

### Unstructured
- PDF.
- DOCX.
- XLSX evidence.
- PPTX where enabled.
- ZIP packages.

### Modes
- Individual upload.
- Batch upload.
- Folder upload.
- ZIP package.
- Manifest-driven upload.

---

# 42. IMPORT BATCH

Every ingestion operation shall create an Import Batch.

Fields:

- Batch ID.
- Batch type.
- Uploaded by.
- Start time.
- End time.
- Source.
- Number of files.
- Number of records.
- Successful records.
- Failed records.
- Warnings.
- Status.
- Error report.

Status:
- Uploaded
- Validating
- Validation Failed
- Ready
- Processing
- Partially Completed
- Completed
- Failed
- Cancelled

---

# 43. Import Preview

Before committing structured data, users shall see:

- File name.
- Template.
- Number of rows.
- Valid rows.
- Invalid rows.
- Warnings.
- New records.
- Existing records.
- Records to update.

The user shall explicitly choose **Load** before data is persisted.

---

# 44. Partial Acceptance

The system shall support valid-row loading.

Example:

100 rows uploaded:
- 94 valid.
- 6 invalid.

User sees:

**94 rows will be loaded; 6 rows will be rejected.**

The error report shall contain:
- File.
- Sheet.
- Row.
- Column.
- Error type.
- Error message.
- Original value.

---

# 45. Batch Processing

Large uploads shall be processed asynchronously.

The browser shall not wait for the entire operation to complete.

The UI shall display:
- Files processed.
- Files remaining.
- Records processed.
- Errors.
- Current status.

The user may navigate away and return to the batch history.

---

# 46. Data Lineage

Every important governance record shall have lineage to its source.

For example:

**Finding F-1023**
→ extracted from Validation Report
→ uploaded in Batch B-20260930-001
→ file `M-0012/Validation/Validation_Report.pdf`
→ uploaded by user U-014
→ extracted by AI
→ confirmed by U-003
→ created on 30-Sep-2026.

This lineage shall be accessible from the record.

---

# 47. Import History

Import Center shall show:

- Batch ID.
- Date.
- User.
- Type.
- Files.
- Records.
- Status.
- Errors.
- Warnings.

Clicking a batch opens:
- Files.
- Rows.
- Errors.
- Changes.
- Audit events.

---

# 48. Data Model — Extended

The existing 16-table design shall be extended.

Core existing tables:

- policy_setting
- app_user
- model
- tiering_answer
- validation
- finding
- approval
- document
- cde
- dq_rule
- dq_result
- dq_issue
- kpi
- kpi_result
- performance_point
- audit_event

Additional tables recommended:

### monitoring_plan
- monitoring_plan_id
- model_id
- model_version
- effective_from
- effective_to
- owner_id
- reviewer_id
- frequency
- methodology
- status
- approval_id

### monitoring_metric
- metric_id
- monitoring_plan_id
- metric_name
- metric_category
- direction
- threshold
- warning_threshold
- breach_threshold
- unit
- frequency
- active

### monitoring_run
- monitoring_run_id
- model_id
- monitoring_plan_id
- model_version
- period
- run_date
- status
- reviewer_id
- signoff_date

### monitoring_result
- monitoring_result_id
- monitoring_run_id
- metric_id
- actual_value
- expected_value
- previous_value
- change_pct
- status
- commentary

### monitoring_breach
- breach_id
- monitoring_result_id
- severity
- detected_date
- owner_id
- due_date
- status
- root_cause
- impact
- management_response
- resolution

### monitoring_evidence
- monitoring_run_id
- document_id

### document_folder
- folder_id
- parent_folder_id
- folder_name
- relative_path
- model_id

### document_version
- document_id
- version
- checksum
- storage_path
- uploaded_by
- uploaded_at
- change_reason

### import_batch
- batch_id
- batch_type
- uploaded_by
- started_at
- completed_at
- status
- total_files
- successful_files
- failed_files

### import_file
- import_file_id
- batch_id
- file_name
- relative_path
- checksum
- file_type
- status
- error_count
- warning_count

### document_extraction
- extraction_id
- document_id
- extraction_type
- model_used
- status
- extracted_json
- confidence
- created_at
- reviewed_by
- reviewed_at

### document_link
Generic many-to-many association between documents and:
- models
- validations
- findings
- approvals
- monitoring runs
- monitoring results
- DQ issues.

---

# 49. Database Requirements

PostgreSQL shall be the system of record.

Requirements:
- Referential integrity.
- Foreign keys.
- Unique constraints.
- Transactional writes.
- Database migrations.
- Soft delete where appropriate.
- Created/updated timestamps.
- Optimistic concurrency for material records.
- Indexes on model ID, status, lifecycle phase, tier, dates and monitoring periods.
- Full audit history.

Optional:
- pgvector for semantic document search.
- PostgreSQL full-text search for document metadata/content.

---

# 50. Document Storage

Use an S3-compatible object store.

Preferred open-source option:

**MinIO**

Object storage shall not store governance metadata as the only source of truth.

PostgreSQL stores metadata.

Object storage stores binary content.

Example:

```
bucket/
  models/
    M-0012/
      governance/
      validation/
      monitoring/
        2026/
          Q1/
          Q2/
```

The logical folder hierarchy shall also be represented in PostgreSQL.

---

# 51. Application Architecture

Recommended architecture:

```text
React + TypeScript
        |
        | REST / JSON
        v
Python FastAPI
        |
        +--------------------+
        |                    |
        v                    v
 PostgreSQL              Redis
        |                    |
        |                    v
        |                 Celery/RQ
        |                    |
        |             Background jobs
        |                    |
        v                    v
    MinIO <------------ Document processor
        |
        v
 PDF/DOCX/XLSX extraction
        |
        v
 AI extraction service
```

---

# 52. Frontend

Recommended:

- React.
- TypeScript.
- Vite or equivalent.
- React Router.
- TanStack Query.
- Recharts.
- Component library such as MUI or shadcn/ui.

The existing HTML prototype's visual language shall be preserved:

- Dark-first theme.
- Flat cards.
- Thin borders.
- No unnecessary drop shadows.
- Compact enterprise dashboard.
- Clear status pills.
- Dense data tables.
- Strong filtering and drill-down.

The existing prototype should be treated as the visual reference, not as the application architecture.

---

# 53. Backend

Recommended:

- Python 3.11+.
- FastAPI.
- SQLAlchemy.
- Alembic.
- Pydantic.
- Pandas/OpenPyXL for structured ingestion.
- PyMuPDF/pdfplumber for PDF processing.
- python-docx for DOCX.
- Celery or RQ for asynchronous jobs.
- Redis for job state/caching where required.

---

# 54. API Requirements

API groups:

```text
/api/auth
/api/users
/api/models
/api/validations
/api/findings
/api/approvals
/api/documents
/api/folders
/api/imports
/api/monitoring/plans
/api/monitoring/metrics
/api/monitoring/runs
/api/monitoring/results
/api/monitoring/breaches
/api/cde
/api/dq
/api/dashboard
/api/copilot
/api/audit
/api/admin
```

All write APIs shall:
1. Validate authorization.
2. Validate payload.
3. Execute business rules.
4. Write transactionally.
5. Generate audit event.
6. Return the persisted record.

---

# 55. Screens

## 55.1 Command Center
Portfolio view:
- Total models.
- Models by tier.
- Models by lifecycle.
- Models requiring revalidation.
- Open findings.
- Monitoring breaches.
- Monitoring completion.
- DQ health.
- Portfolio governance score.

## 55.2 Operations Board
Filters:
- Model type.
- Tier.
- Phase.
- Business line.
- Monitoring status.
- Revalidation status.
- Findings.
- Search.

## 55.3 Model 360
Sections:
- Profile.
- Lifecycle.
- Risk tier.
- Owners.
- Validation.
- Findings.
- Approvals.
- Documents.
- Monitoring.
- CDE/DQ.
- Governance score.
- Audit history.

## 55.4 Monitoring Dashboard
Dedicated monitoring portfolio view.

## 55.5 Data Audit
- CDE registry.
- DQ rules.
- DQ results.
- DQ issues.

## 55.6 Document Centre
Features:
- Folder tree.
- Document list.
- Upload.
- Batch upload.
- Folder upload.
- ZIP upload.
- Search.
- Filter.
- Preview.
- Download.
- Version history.
- Extraction queue.
- Review queue.

## 55.7 Import Centre
Features:
- Template list.
- Blank template download.
- Upload.
- Batch upload.
- Preview.
- Validation.
- Load.
- Error report.
- Import history.

## 55.8 Admin
- Policy settings.
- Required documents.
- Monitoring thresholds.
- Monitoring frequencies.
- Severity rules.
- Roles.
- Users.
- Document types.
- System configuration.

## 55.9 Audit Trail
Filter by:
- User.
- Model.
- Entity.
- Action.
- Date.
- Batch.
- Document.

---

# 56. Command Center Insights

Insights shall be generated from rules and current data.

Examples:
- High-tier model overdue for revalidation.
- Critical finding overdue.
- Validator independence breach.
- Missing required documentation.
- KPI failure.
- Repeated KPI failure.
- Critical DQ issue.
- Monitoring run overdue.
- Critical monitoring breach.
- Monitoring evidence missing.
- Repeated monitoring breach.
- Significant performance deterioration.

Insights shall contain:
- Severity.
- Message.
- Model ID.
- Source record.
- Date.
- Link to relevant screen.

---

# 57. Governance Score

The existing score shall be retained as the initial baseline.

Components:
- Documentation.
- Validation currency.
- Issue remediation.
- MRC compliance.
- Monitoring.

Initial weights:
- Documentation 25%.
- Validation currency 25%.
- Issue remediation 20%.
- MRC compliance 15%.
- Monitoring 15%.

Weights shall be configurable.

The score must be explainable.

For every score the system shall display:
- Overall score.
- Component score.
- Weight.
- Calculation inputs.
- Missing information.
- Last recalculation time.

---

# 58. Audit Trail

Every material write shall create an audit event.

Events include:
- Create.
- Update.
- Delete/retire.
- Import.
- Upload.
- Extraction.
- Confirmation.
- Rejection.
- Approval.
- Tier override.
- Threshold change.
- Monitoring result confirmation.
- Breach creation.
- Breach closure.
- Document version creation.

Audit records must be immutable to normal application users.

---

# 59. Security and Access Control

The production version shall support authentication.

Recommended:
- OAuth2/OIDC.
- Enterprise identity provider.
- JWT/session-based authorization.

Authorization must be enforced server-side.

UI hiding alone is insufficient.

Examples:
- Auditor cannot modify.
- Executive cannot upload.
- Model Owner can modify assigned models.
- Validator can update assigned validation records.
- Admin can configure policies.
- Monitoring Analyst can manage monitoring records.

---

# 60. AI Governance

AI functionality shall be treated as an assistive service.

AI shall:
- Extract.
- Classify.
- Summarize.
- Search.
- Answer questions from governed data.

AI shall not:
- Approve models.
- Close findings.
- Change risk tier.
- Change monitoring thresholds.
- Change lifecycle phase.
- Delete evidence.
- Make governance decisions.

All AI-generated content that becomes governance data requires human confirmation unless explicitly configured otherwise.

The system shall record:
- AI provider.
- Model.
- Prompt/version identifier.
- Timestamp.
- Input document.
- Output.
- Reviewer.
- Confirmation status.

---

# 61. Audit Copilot

The Copilot shall remain read-only.

Suggested questions:

- Which high-risk models are overdue for revalidation?
- Which models have critical findings?
- Which monitoring KPIs failed this quarter?
- Which models have repeated monitoring breaches?
- Which CDEs are failing?
- Which models are missing required documentation?
- Why did model M-0012's governance score change?
- Show the monitoring history for M-0012.
- What evidence supports the latest monitoring result?

Every answer shall identify the relevant model IDs and underlying records.

---

# 62. Search

The application shall provide global search across:

- Model ID.
- Model name.
- Document name.
- Finding.
- Validation.
- Approval.
- Monitoring run.
- KPI.
- CDE.
- DQ issue.

Optional phase:
- Full-text document search.
- Semantic document search using pgvector.

---

# 63. Notifications

Recommended later capability:

- Monitoring breach.
- Monitoring due.
- Revalidation due.
- Finding overdue.
- Document review pending.
- Approval condition due.

Notification channels can later include:
- In-app.
- Email.
- Teams/Slack.

The notification engine should be decoupled from the rules engine.

---

# 64. Non-Functional Requirements

## Performance
- Dashboard load target: <2 seconds for normal portfolio queries.
- Model 360: <2 seconds excluding document/AI processing.
- Large upload processing shall be asynchronous.
- UI must remain responsive during background ingestion.

## Scalability
Initial target:
- 5,000 models.
- 100,000 documents.
- 1 million monitoring results.
- 10 million audit events.

The architecture should allow horizontal scaling of workers.

## Availability
Production deployment should support:
- Application health checks.
- Database health checks.
- Worker health checks.
- Object storage health checks.

## Reliability
- Failed background jobs shall be retryable.
- Processing shall be idempotent.
- Partial batch failures shall not corrupt successful records.
- Database writes shall be transactional.

## Security
- Encryption in transit.
- Encryption at rest where supported.
- Role-based access.
- Server-side authorization.
- No secrets in frontend.
- File malware scanning recommended before production.
- ZIP path traversal protection.

---

# 65. File Validation and Security

Every uploaded file shall be checked for:

- Extension.
- MIME type.
- File size.
- File signature.
- Malware status where scanner is available.
- ZIP archive safety.
- Maximum file count.
- Maximum decompressed size.
- Path traversal.
- Duplicate checksum.

Default maximum:
- Individual document: 10 MB.
- Configurable at system level.
- ZIP maximum configurable separately.

---

# 66. Error Handling

Errors shall be human-readable.

Examples:

**Invalid model ID**
> Model M-9999 does not exist.

**Duplicate**
> Document already exists with SHA-256 checksum XXXXX.

**SoD**
> Validator U-014 cannot validate model M-0012 because U-014 is also the model owner.

**Monitoring**
> KPI K-0012-01 failed: actual value 0.58 is below breach threshold 0.6175.

**Document**
> Extraction failed validation. No governance record was created.

---

# 67. Auditability and Lineage Requirements

The system shall answer:

- Who uploaded this?
- Where did it come from?
- Which batch contained it?
- Which folder was it uploaded from?
- Which model is it linked to?
- Which version is it?
- Was AI used?
- Who confirmed the AI extraction?
- Which monitoring run produced this breach?
- Which policy threshold was used?
- What was the previous value?
- What changed?

---

# 68. Data Retention

Retention policies shall be configurable.

Documents and audit records shall support:
- Retention start date.
- Retention end date.
- Legal hold flag.
- Archived flag.

Deletion shall be controlled and audited.

---

# 69. Configuration

The following shall be configuration-driven:

- Risk tier thresholds.
- Governance score weights.
- Revalidation lead time.
- Revalidation frequencies.
- Required documents.
- Monitoring frequencies.
- KPI thresholds.
- DQ thresholds.
- Breach severity rules.
- Repeated-breach rules.
- File-size limits.
- Allowed document types.
- Roles.
- Lifecycle phases.

Business rules must not be duplicated throughout frontend components.

---

# 70. Seed and Demo Data

The existing design contains 256 synthetic models and defined seed targets.

The seed generator shall remain deterministic.

Seed data shall be created through the same ingestion/business-service path used by the application where practical.

The reset function shall:
1. Clear/reset application data.
2. Recreate configuration.
3. Load users.
4. Load models.
5. Load governance history.
6. Load CDE/DQ.
7. Load monitoring definitions/results.
8. Load documents/evidence metadata.
9. Recalculate derived fields.

---

# 71. Initial Template Framework

Existing templates shall remain supported:

- T01 Users.
- T02 Model Inventory.
- T03 Validation History.
- T04 Findings.
- T05 Approvals.
- T06 CDE/DQ Rules.
- T07 KPI Definitions.
- T08 KPI Results.
- T09 Performance Curves.
- T10 DQ Results.
- T11 Documents.
- T12 Policy Settings.

New recommended templates:

### T13 Monitoring Plan
### T14 Monitoring Metrics
### T15 Monitoring Results
### T16 Monitoring Breaches
### T17 Document Manifest
### T18 Folder/Package Manifest

The template registry shall remain the single source of truth for validation and blank template generation.

---

# 72. New Monitoring Templates

## T13 Monitoring Plan

Columns:
- monitoring_plan_id
- model_id
- model_version
- effective_from
- frequency
- owner_id
- reviewer_id
- methodology
- status

## T14 Monitoring Metrics

Columns:
- metric_id
- monitoring_plan_id
- metric_name
- metric_category
- direction
- threshold
- warning_threshold
- breach_threshold
- unit
- frequency
- active

## T15 Monitoring Results

Columns:
- monitoring_run_id
- model_id
- model_version
- metric_id
- period
- run_date
- actual_value
- expected_value
- status
- commentary

## T16 Monitoring Breaches

Columns:
- breach_id
- monitoring_run_id
- metric_id
- severity
- detected_date
- owner_id
- due_date
- status
- root_cause
- impact
- management_response

## T17 Document Manifest

Columns:
- relative_path
- model_id
- document_type
- version
- effective_date

## T18 Folder Manifest

Columns:
- relative_path
- model_id
- folder_type
- description

---

# 73. User Journey — Individual Upload

```text
User opens Model 360
        |
Documents
        |
Upload Document
        |
Select file
        |
Select document type
        |
Select version
        |
Upload
        |
Validation
        |
AI extraction (if applicable)
        |
Review
        |
Confirm
        |
Database + object storage
        |
Audit event
```

---

# 74. User Journey — Batch Upload

```text
User opens Document Centre
        |
Batch Upload
        |
Select multiple files
        |
System validates files
        |
System calculates checksums
        |
System identifies models/types
        |
User reviews mapping
        |
Confirm Batch
        |
Background processing
        |
Extraction
        |
Review Queue
        |
Confirmation
        |
Database
        |
Audit Trail
```

---

# 75. User Journey — Folder Upload

```text
Select Folder
      |
Scan folder tree
      |
Display file hierarchy
      |
Identify model folders
      |
Identify document types
      |
User confirms mappings
      |
Create Import Batch
      |
Upload files
      |
Process asynchronously
      |
Create folders
      |
Create documents
      |
AI extraction
      |
Review
      |
Confirm
```

---

# 76. User Journey — Monitoring

```text
Monitoring Plan
      |
Monitoring Run
      |
Load Results
      |
Evaluate Thresholds
      |
Pass / Warn / Fail
      |
Create Breach where required
      |
Assess Impact
      |
Create/Link Finding if required
      |
Reviewer Sign-off
      |
Monitoring Dashboard
      |
Governance Score
```

---

# 77. Acceptance Criteria — Monitoring

### MON-01
Given a KPI threshold, the system calculates Pass/Warn/Fail correctly.

### MON-02
A failed critical KPI creates a monitoring breach.

### MON-03
A monitoring breach is linked to its monitoring run and model.

### MON-04
A monitoring run cannot be marked complete without required metrics.

### MON-05
Historical monitoring results remain unchanged when thresholds are subsequently changed.

### MON-06
A user can view at least four historical monitoring periods.

### MON-07
A user can drill from a chart point to the monitoring result.

### MON-08
Repeated KPI failures generate a governance insight.

### MON-09
A monitoring breach may be converted into a formal finding only through an authorised user action.

### MON-10
Monitoring evidence can be attached to the run.

### MON-11
The monitoring dashboard correctly aggregates Pass/Warn/Fail.

### MON-12
The governance score changes when the monitoring component changes.

---

# 78. Acceptance Criteria — Document and Folder Upload

### DOC-01
A user can upload a single PDF.

### DOC-02
A user can upload a single DOCX.

### DOC-03
A user can upload multiple files simultaneously.

### DOC-04
A user can upload a folder.

### DOC-05
A user can upload a ZIP package.

### DOC-06
Nested folder structure is preserved.

### DOC-07
Every file receives a checksum.

### DOC-08
Exact duplicate files are detected.

### DOC-09
A batch has a unique batch ID.

### DOC-10
A failed file does not cause valid files in the same batch to be lost.

### DOC-11
A user can see batch progress.

### DOC-12
A user can download a batch error report.

### DOC-13
A document can be mapped to a model.

### DOC-14
The system can suggest document type.

### DOC-15
The user can override document classification.

### DOC-16
AI extraction cannot persist governance changes without confirmation.

### DOC-17
Document versions remain accessible.

### DOC-18
The folder path is retained.

### DOC-19
Document lineage is visible.

### DOC-20
Document completeness is recalculated after confirmation.

---

# 79. Acceptance Criteria — Structured Batch Import

### IMP-01
User can upload multiple CSV/XLSX files.

### IMP-02
Each file is mapped to a template.

### IMP-03
Invalid files are isolated.

### IMP-04
Valid files continue processing.

### IMP-05
Row-level errors are recorded.

### IMP-06
Foreign-key dependencies are checked.

### IMP-07
Duplicate records are handled according to configured upsert rules.

### IMP-08
All changes are audited.

### IMP-09
Batch history remains available.

---

# 80. Test Strategy

Three levels:

## Unit tests
Business rules:
- Tiering.
- Revalidation.
- KPI status.
- DQ status.
- Governance score.
- Monitoring thresholds.
- Breach severity.
- Duplicate detection.
- Document completeness.

## Integration tests
- API.
- Database.
- Object storage.
- Import processing.
- Background jobs.
- AI extraction.

## End-to-end tests
- Model creation.
- Import.
- Document upload.
- Folder upload.
- Monitoring run.
- Breach.
- Finding.
- Dashboard drill-down.

---

# 81. Recommended Development Phases

## Phase 1 — Foundation
- React.
- FastAPI.
- PostgreSQL.
- Authentication framework.
- Base layout.
- Role model.

## Phase 2 — Existing Governance Core
- Model inventory.
- Tiering.
- Validation.
- Findings.
- Approvals.
- Governance score.

## Phase 3 — Import Engine
- Excel.
- CSV.
- Validation.
- Preview.
- Batch import.
- Audit.

## Phase 4 — Document Centre
- Individual upload.
- Batch upload.
- Folder upload.
- ZIP.
- Object storage.
- Document metadata.
- Versioning.

## Phase 5 — AI Extraction
- PDF/DOCX extraction.
- Classification.
- Structured extraction.
- Human review.
- Audit.

## Phase 6 — Monitoring
- Monitoring plans.
- Metrics.
- Thresholds.
- Runs.
- Results.
- Breaches.
- Trends.
- Evidence.
- Dashboard.

## Phase 7 — Data Audit
- CDE.
- DQ.
- Issues.

## Phase 8 — Command Center / Model 360
- Dashboards.
- Drill-down.
- Score.

## Phase 9 — Copilot
- Read-only tools.
- RAG/search.
- Model 360 questions.
- Document questions.

## Phase 10 — Hardening
- Security.
- Performance.
- E2E tests.
- Backup/restore.
- Monitoring.
- Deployment.

---

# 82. Claude Code Development Instructions

Claude Code shall treat this BRD as the business specification.

Implementation rules:

1. Do not hard-code business numbers in UI components.
2. Store configurable rules in configuration tables.
3. Keep business rules in a dedicated Python service/rules layer.
4. Keep database models separate from API schemas.
5. Every write must pass through a service.
6. Every material write must generate an audit event.
7. All document binary data must use object storage.
8. PostgreSQL remains the source of truth for metadata.
9. Long-running uploads must be asynchronous.
10. All batch operations must be restartable/idempotent.
11. Never trust client-side role checks.
12. Enforce authorization server-side.
13. Never allow AI output to directly mutate governance records without the required human confirmation.
14. Preserve source lineage.
15. Do not silently overwrite document versions.
16. Do not silently delete evidence.
17. Preserve historical monitoring results.
18. Threshold changes must not rewrite historical outcomes.
19. Write tests for every business rule.
20. Build feature-by-feature and keep the application runnable after every phase.

---

# 83. Suggested Repository Structure

```text
mrm-mis/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── features/
│   │   │   ├── models/
│   │   │   ├── monitoring/
│   │   │   ├── documents/
│   │   │   ├── imports/
│   │   │   ├── findings/
│   │   │   └── dashboard/
│   │   └── api/
│
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── rules/
│   │   ├── repositories/
│   │   ├── workers/
│   │   ├── ingestion/
│   │   ├── documents/
│   │   ├── monitoring/
│   │   └── audit/
│   ├── migrations/
│   └── tests/
│
├── seed/
├── demo-files/
├── docs/
│   ├── BRD.md
│   ├── design.md
│   └── templates.md
│
├── docker/
├── docker-compose.yml
└── README.md
```

---

# 84. Development Definition of Done

A feature is complete only when:

- Business requirement implemented.
- API implemented.
- Authorization implemented.
- Database migration implemented.
- Audit events implemented.
- Unit tests implemented.
- Integration test implemented where applicable.
- UI implemented.
- Empty/error/loading states implemented.
- Relevant documentation updated.
- No hard-coded business data.
- Existing functionality remains operational.

---

# 85. Priority Classification

## Must Have — MVP

- Model inventory.
- Tiering.
- Lifecycle.
- Validation.
- Findings.
- Approvals.
- Governance score.
- Structured imports.
- Individual document upload.
- Batch document upload.
- Folder/ZIP upload.
- Document metadata.
- Document versioning.
- Monitoring plan.
- Monitoring metrics.
- Monitoring results.
- Monitoring thresholds.
- Monitoring breaches.
- Monitoring dashboard.
- Model 360 monitoring.
- CDE/DQ.
- Audit trail.
- RBAC.
- Command Center.
- Operations Board.
- Document Centre.
- Import Centre.

## Should Have

- AI document classification.
- AI extraction.
- Repeated breach detection.
- Semantic document search.
- Audit Copilot.
- Automated notifications.
- Manifest-driven package ingestion.
- Advanced trend analysis.

## Could Have

- Enterprise GRC integration.
- SSO.
- API ingestion.
- Email/Teams notifications.
- Advanced ML-based anomaly detection.
- Automated regulatory mapping.

---

# 86. Important Design Principles

## Principle 1 — Database is the source of truth

Files are inputs/evidence.

The UI never calculates portfolio figures from raw uploaded files.

## Principle 2 — Evidence first

Every material governance conclusion should be traceable to evidence.

## Principle 3 — Human in the loop

AI assists; humans confirm.

## Principle 4 — Configuration over code

Thresholds, frequencies and policies must be configurable.

## Principle 5 — Historical immutability

Historical monitoring and governance decisions must not change because current configuration changes.

## Principle 6 — Batch-first architecture

The system must support both one-file and enterprise-scale package ingestion.

## Principle 7 — Async processing

Document extraction and large imports must run as background jobs.

## Principle 8 — Full lineage

Every record must be traceable back to its source.

## Principle 9 — Explainability

Governance scores, KPI statuses and breaches must show how they were calculated.

## Principle 10 — No governance decision by AI

AI must not make or silently implement governance decisions.

---

# 87. Final Target State

The completed system should allow a Model Risk function to perform the following end-to-end process:

```text
Model Inventory
      |
      v
Risk Tiering
      |
      v
Model Lifecycle
      |
      +----------------------+
      |                      |
      v                      v
Validation              Documentation
      |                      |
      v                      v
Findings                 Evidence
      |                      |
      +----------+-----------+
                 |
                 v
          Model Approval
                 |
                 v
            Production
                 |
                 v
        Monitoring Plan
                 |
                 v
        Monitoring Runs
                 |
        +--------+---------+
        |        |         |
        v        v         v
      KPI      Drift      DQ
        |        |         |
        +--------+---------+
                 |
                 v
          Breach / Alert
                 |
                 v
        Investigation
                 |
                 v
          Finding / Action
                 |
                 v
          Review / Closure
                 |
                 v
        Governance Score
                 |
                 v
          Command Center
```

At every point, the system should answer:

**What is the current state?  
What changed?  
Why did it change?  
Who changed it?  
What evidence supports it?  
What action is required?  
What is overdue?  
What is the risk implication?**

This is the core business objective of the Model Governance MIS.
