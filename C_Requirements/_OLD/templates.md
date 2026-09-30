# Input templates

Exported from the shared document (Input templates tab) for use as `docs/templates.md` in the Claude Code repository. Design and requirements are in `docs/design.md`.

Twelve templates load the initial build. Each table below is the column specification Claude Code turns into a zod schema in `src/lib/templates/registry.ts`, followed by sample rows.

## Load order and conventions

Templates load in this order, because each one refers to records created by the one before:

1. T12 Policy settings
2. T01 Users and roles
3. T02 Model inventory and tiering
4. T03 Validation history, T04 Findings, T05 Approvals (any order); T11 documents from here on
5. T06 Critical data elements and DQ rules, T07 KPI definitions
6. T08 KPI results, T09 Performance curves, T10 DQ rule results

Conventions for every Excel and CSV template:

- One header row with the exact column names below, in snake_case; column order does not matter.
- One sheet per Excel file, named `data`; a second sheet `instructions` is ignored on load.
- Dates as YYYY-MM-DD. Yes/no fields as Y or N. Percentages as whole numbers (98 means 98%).
- Allowed values are case-sensitive and must match the lists shown.
- IDs are text with a fixed prefix: U- users, M- models, V- validations, F- findings, A- approvals, CDE- data elements, DQR- rules, K- KPIs, R- DQ runs.
- “FK” means the value must already exist in the named table.

## T12 Policy settings

Excel, loaded first; every rule in design section 7 reads its thresholds from here, and Admin can edit each value afterwards.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| setting_key | text | Yes | One of the keys below; unique | reval_lead_days |
| value | text | Yes | Parsed by value_type | 60 |
| value_type | text | Yes | integer, percent, text, list | integer |
| description | text | No | Free text | Days before due date a model shows in Revalidation |

Seed values:

| setting_key | value | Used by |
| --- | --- | --- |
| tier_high_min | 10 | R1 |
| tier_medium_min | 7 | R1 |
| reval_lead_days | 60 | R3 |
| due_soon_days | 30 | R4 |
| validation_sla_days_high | 45 | R9 |
| validation_sla_days_medium | 60 | R9 |
| validation_sla_days_low | 90 | R9 |
| weight_documentation | 25 | R8 |
| weight_validation_currency | 25 | R8 |
| weight_issue_remediation | 20 | R8 |
| weight_mrc_compliance | 15 | R8 |
| weight_monitoring | 15 | R8 |
| required_docs_development | ToR | R8 |
| required_docs_validation | ToR; MDD | R8 |
| required_docs_production | ToR; MDD; Validation report | R8 (Implementation and later) |
| mdd_required_sections | Purpose and use; Data; Methodology; Assumptions; Limitations; Testing and performance; Implementation; Monitoring plan | R8, document extraction |
| dq_default_pass_pct | 98 | R7, when a rule gives none |
| dq_default_warn_pct | 95 | R7, when a rule gives none |

## T01 Users and roles

Excel; one row per person. In the demo these users appear in the role switcher.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| user_id | text | Yes | U-### ; unique | U-014 |
| full_name | text | Yes | Free text | Sarah Patel |
| email | text | Yes | Valid email; unique | s.patel@demo-bank.example |
| role | text | Yes | Admin, Model Owner, Model Developer, Validator, MRC Member, Auditor, Executive | Validator |
| business_line | text | No | Free text | Enterprise Risk |
| active | Y/N | Yes | Y or N | Y |

## T02 Model inventory and tiering

Excel; one row per model. The four tiering answers produce the risk tier (R1); the tier itself is never imported, except as an override.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| model_id | text | Yes | M-#### ; unique | M-0012 |
| model_name | text | Yes | Free text, 3–100 characters | Wholesale PD Model |
| model_type | text | Yes | Credit Risk, Provisioning, Balance Sheet, Forecasting, CCAR/Stress Testing | Credit Risk |
| model_subtype | text | Yes | Free text | PD |
| purpose | text | Yes | Free text, up to 500 characters | 12-month PD for wholesale commercial exposures |
| business_line | text | Yes | Free text | Commercial Banking |
| owner_id | text | Yes | FK app_user | U-003 |
| developer_id | text | Yes | FK app_user; not equal to validator_id | U-021 |
| validator_id | text | From Validation phase on | FK app_user; not equal to owner_id or developer_id (R5) | U-014 |
| lifecycle_phase | text | Yes | Initiation, Development, Validation, Implementation, Monitoring, Reg/Audit, Retirement | Monitoring |
| version | text | Yes | Free text | v3.1 |
| go_live_date | date | From Monitoring on | YYYY-MM-DD | 2024-02-15 |
| revalidation_frequency | text | From Monitoring on | Monthly, Quarterly, Semi-annual, Annual, Biennial | Annual |
| last_validation_date | date | From Monitoring on | YYYY-MM-DD; not in the future | 2025-11-15 |
| q_materiality | integer | Yes | 1, 2 or 3 | 3 |
| q_complexity | integer | Yes | 1, 2 or 3 | 2 |
| q_reliance | integer | Yes | 1, 2 or 3 | 3 |
| q_regulatory_use | integer | Yes | 1, 2 or 3 | 3 |
| override_tier | text | No | High, Medium, Low | (blank) |
| override_reason | text | If override_tier set | Free text | (blank) |
| successor_model_id | text | No | FK model; Retirement phase only | (blank) |

Tiering questions, each answered 1 (low), 2 (medium) or 3 (high):

| Column | Question |
| --- | --- |
| q_materiality | How large is the financial exposure or balance the model drives? |
| q_complexity | How complex is the method, data or number of components? |
| q_reliance | How much do decisions depend on the output without other checks? |
| q_regulatory_use | Is the output used in regulatory capital, provisioning or stress-test submissions? |

Sample rows:

```csv
model_id,model_name,model_type,model_subtype,business_line,owner_id,developer_id,validator_id,lifecycle_phase,version,go_live_date,revalidation_frequency,last_validation_date,q_materiality,q_complexity,q_reliance,q_regulatory_use
M-0012,Wholesale PD Model,Credit Risk,PD,Commercial Banking,U-003,U-021,U-014,Monitoring,v3.1,2024-02-15,Annual,2025-11-15,3,2,3,3
M-0042,ALM Interest Rate Risk,Balance Sheet,ALM/IRR,Treasury,U-007,U-025,U-016,Monitoring,v3.0,2023-04-15,Annual,2025-02-20,3,3,2,3
M-0076,CCAR Loss Forecasting,CCAR/Stress Testing,Loss,Enterprise Risk,U-009,U-027,U-018,Validation,v4.2,,,,3,3,3,3
M-0091,Deposit Pricing Model,Balance Sheet,Pricing,Treasury,U-011,U-029,,Initiation,v0.1,,,,1,2,1,1
```

The purpose column is left out of the samples for width; it is required in the file.

## T03 Validation history

Excel; one row per validation exercise, past or in progress.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| validation_id | text | Yes | V-#### ; unique | V-0412 |
| model_id | text | Yes | FK model | M-0012 |
| validation_type | text | Yes | Initial, Periodic, Targeted, Change | Periodic |
| validator_id | text | Yes | FK app_user; R5 against the model | U-014 |
| start_date | date | Yes | YYYY-MM-DD | 2025-10-01 |
| completion_date | date | If outcome is not In progress | Not before start_date | 2025-11-15 |
| outcome | text | Yes | Approved, Conditional, Rejected, In progress | Conditional |
| report_document_id | text | No | FK document, when the report is uploaded | (blank) |

## T04 Findings

Excel; one row per validation or audit finding. Findings confirmed from a validation report upload are added with source = extraction.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| finding_id | text | Yes | F-#### ; unique | F-0001 |
| model_id | text | Yes | FK model | M-0012 |
| validation_id | text | No | FK validation | V-0412 |
| title | text | Yes | Up to 120 characters | CRE obligor data gap |
| description | text | Yes | Free text | 14% of obligor financial statements missing in construction lending |
| severity | text | Yes | Critical, Medium, Low | Critical |
| category | text | Yes | Data, Methodology, Documentation, Implementation, Performance | Data |
| status | text | Yes | Open, In Progress, Closed | Open |
| owner_id | text | Yes | FK app_user | U-003 |
| raised_date | date | Yes | YYYY-MM-DD | 2025-11-15 |
| due_date | date | Yes | Not before raised_date | 2026-06-30 |
| closed_date | date | If status is Closed | Not before raised_date | (blank) |

## T05 Approvals and MRC decisions

Excel; one row per decision by the MRC or another approving body.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| approval_id | text | Yes | A-#### ; unique | A-0231 |
| model_id | text | Yes | FK model | M-0071 |
| decision_date | date | Yes | YYYY-MM-DD | 2026-02-20 |
| forum | text | Yes | MRC, Model Risk Officer, Validation Committee | MRC |
| decision_type | text | Yes | ToR, Initial approval, Validation complete, Pre-implementation, Annual review, Periodic review, Retirement | Pre-implementation |
| decision | text | Yes | Approved, Conditional, Rejected | Conditional |
| conditions | text | If decision is Conditional | Free text | Go-live blocked until F-017 and F-019 are resolved |
| condition_due_date | date | If decision is Conditional | YYYY-MM-DD | 2026-05-15 |
| condition_status | text | If decision is Conditional | Open, Met | Open |

## T06 Critical data elements and DQ rules

Excel; one row per data quality rule on one CDE. Every row names its own source system, table and column; a CDE drawn from two source columns is two CDE rows, never one row listing both.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| cde_id | text | Yes | CDE-#### ; the same cde_id may repeat across rows for different rules | CDE-0101 |
| model_id | text | Yes | FK model | M-0012 |
| cde_name | text | Yes | Free text | Obligor total assets |
| source_system | text | Yes | One named system | Commercial Loan Origination (CLOS) |
| source_table | text | Yes | One table | OBLIGOR_FINANCIALS |
| source_column | text | Yes | One column | TOTAL_ASSETS_AMT |
| data_owner_id | text | Yes | FK app_user | U-031 |
| dq_rule_id | text | Yes | DQR-#### ; unique | DQR-0301 |
| rule_description | text | Yes | Free text | Not null for active obligors |
| pass_threshold_pct | percent | No | 0–100; default dq_default_pass_pct | 98 |
| warn_threshold_pct | percent | No | 0–100; not above pass_threshold_pct | 95 |

Sample rows:

```csv
cde_id,model_id,cde_name,source_system,source_table,source_column,data_owner_id,dq_rule_id,rule_description,pass_threshold_pct,warn_threshold_pct
CDE-0101,M-0012,Obligor total assets,Commercial Loan Origination (CLOS),OBLIGOR_FINANCIALS,TOTAL_ASSETS_AMT,U-031,DQR-0301,Not null for active obligors,98,95
CDE-0102,M-0012,Collateral appraised value,Collateral Management (CMS),COLLATERAL_VALUATION,APPRAISED_VALUE_AMT,U-032,DQR-0302,Appraisal date within 90 days,97,93
CDE-0201,M-0042,Deposit repricing beta,Treasury ALM Platform (ALMP),NMD_ASSUMPTIONS,REPRICING_BETA_PCT,U-033,DQR-0401,Between 0 and 100 and reviewed this quarter,100,95
```

## T07 KPI definitions and thresholds

Excel; one row per KPI per model.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| kpi_id | text | Yes | K-&lt;model number&gt;-## ; unique | K-0012-01 |
| model_id | text | Yes | FK model | M-0012 |
| kpi_name | text | Yes | Free text | Gini coefficient |
| direction | text | Yes | higher_is_better, lower_is_better | higher_is_better |
| threshold | number | Yes | Decimal | 0.65 |
| warn_tolerance_pct | percent | Yes | 0–50 | 5 |
| frequency | text | Yes | Monthly, Quarterly | Quarterly |

Sample rows:

```csv
kpi_id,model_id,kpi_name,direction,threshold,warn_tolerance_pct,frequency
K-0012-01,M-0012,Gini coefficient,higher_is_better,0.65,5,Quarterly
K-0012-02,M-0012,Population stability index (PSI),lower_is_better,0.10,20,Quarterly
K-0015-02,M-0015,Coverage ratio,higher_is_better,0.95,2,Quarterly
```

## T08 KPI and backtesting results

CSV; one row per KPI per period. Status is calculated on load (R6), never supplied.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| model_id | text | Yes | FK model; must own kpi_id | M-0015 |
| kpi_id | text | Yes | FK kpi | K-0015-02 |
| period | text | Yes | YYYY-MM (Monthly) or YYYY-Qn (Quarterly), matching the KPI frequency | 2025-Q4 |
| value | number | Yes | Decimal | 0.94 |
| is_backtest | Y/N | Yes | Y for a backtesting exercise, N for routine monitoring | Y |

```csv
model_id,kpi_id,period,value,is_backtest
M-0015,K-0015-01,2025-Q4,0.12,Y
M-0015,K-0015-02,2025-Q4,0.94,Y
M-0015,K-0015-03,2025-Q4,0.11,Y
```

## T09 Performance curves

CSV; one row per point on a curve. ROC curves suit PD and scorecard models; predicted-versus-actual suits LGD, EAD, ALM, liquidity, CECL and forecasting models.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| model_id | text | Yes | FK model | M-0012 |
| curve_type | text | Yes | ROC, PRED_VS_ACTUAL | ROC |
| period | text | Yes | YYYY-Qn of the evaluation | 2025-Q4 |
| series | text | Yes | roc for ROC; predicted or actual for PRED_VS_ACTUAL | roc |
| point_index | integer | Yes | 0, 1, 2 … in drawing order; unique per model, curve, period and series | 3 |
| x | text | Yes | ROC: false positive rate 0–1; PRED_VS_ACTUAL: period label such as 2025-Q1 | 0.10 |
| y | number | Yes | ROC: true positive rate 0–1; PRED_VS_ACTUAL: value in the model's unit | 0.55 |
| auc | number | ROC, on point 0 only | 0.5–1 | 0.84 |

```csv
model_id,curve_type,period,series,point_index,x,y,auc
M-0012,ROC,2025-Q4,roc,0,0,0,0.84
M-0012,ROC,2025-Q4,roc,1,0.05,0.35,
M-0012,ROC,2025-Q4,roc,2,0.10,0.55,
M-0015,PRED_VS_ACTUAL,2025-Q4,predicted,0,2025-Q1,0.38,
M-0015,PRED_VS_ACTUAL,2025-Q4,actual,0,2025-Q1,0.39,
```

## T10 DQ rule results

CSV; one row per rule per run. Status is calculated on load (R7); a Fail opens a DQ issue.

| Column | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| run_id | text | Yes | R-######## ; the same run_id for every rule in one run | R-20260915 |
| run_date | date | Yes | YYYY-MM-DD | 2026-09-15 |
| dq_rule_id | text | Yes | FK dq_rule | DQR-0301 |
| records_tested | integer | Yes | Greater than 0 | 12480 |
| records_failed | integer | Yes | 0 to records_tested | 1747 |

```csv
run_id,run_date,dq_rule_id,records_tested,records_failed
R-20260915,2026-09-15,DQR-0301,12480,1747
R-20260915,2026-09-15,DQR-0302,5600,336
R-20260915,2026-09-15,DQR-0401,1,1
```

## T11 Document uploads

PDF or DOCX, up to 10 MB, uploaded in the Import Center's Documents tab against one model. The uploader fills three fields; Claude extracts the rest for review (design section 8).

| Upload field | Type | Required | Allowed values or rule | Example |
| --- | --- | --- | --- | --- |
| model_id | text | Yes | FK model | M-0301 |
| doc_type | text | Yes | ToR, MDD, Validation report | Validation report |
| version | text | Yes | Free text | 1.0 |

The synthetic demo documents follow these structures, so extraction has headings to anchor on:

| Document type | Expected headings | What is extracted |
| --- | --- | --- |
| Terms of Reference | Model name; Purpose and intended use; Scope; Out of scope; Planned timeline | Model name, purpose, scope, planned dates |
| Model development document (MDD) | The eight sections in mdd_required_sections (Purpose and use; Data; Methodology; Assumptions; Limitations; Testing and performance; Implementation; Monitoring plan) | Which sections are present; assumptions list; limitations list |
| Validation report | Executive summary; Scope of validation; Overall outcome; Findings (a table with ID, title, severity, category, description, recommended due date); Recommendations | Overall outcome; one candidate finding per row of the findings table |

## Demo sample files

Four files in `demo-files/` are uploaded live (design section 10); Claude Code generates them in P7 alongside the seed.

| File | Template | Contents | Deliberate issue |
| --- | --- | --- | --- |
| T02_new_models_demo.xlsx | T02 | 5 new models, M-0301 to M-0305, across Credit Risk, Provisioning and Forecasting | M-0304 has validator_id equal to owner_id, so it is rejected under R5 |
| validation_report_M-0301.pdf | T11 | Validation report for M-0301 with outcome Conditional and 4 findings: 1 Critical, 2 Medium, 1 Low | None; the presenter drops the Low finding at review |
| mdd_M-0302_incomplete.docx | T11 | MDD for M-0302 | Limitations and Monitoring plan sections are missing |
| T10_dq_results_demo.csv | T10 | One run of 6 DQ rules on seed models | 2 rules fall below their warn threshold and open DQ issues |

T02 demo file rows (the file also has a purpose column, left out here for width):

```csv
model_id,model_name,model_type,model_subtype,business_line,owner_id,developer_id,validator_id,lifecycle_phase,version,q_materiality,q_complexity,q_reliance,q_regulatory_use
M-0301,SME Probability of Default,Credit Risk,PD,Business Banking,U-004,U-022,U-015,Validation,v1.0,3,2,3,3
M-0302,CRE Lifetime Loss,Provisioning,CECL,Commercial Real Estate,U-006,U-024,U-017,Validation,v2.0,3,3,2,3
M-0303,Card Fraud Scorecard,Credit Risk,Scorecard,Consumer Cards,U-008,U-026,,Development,v0.9,2,2,2,1
M-0304,Branch Deposit Forecast,Forecasting,Deposits,Retail Banking,U-005,U-023,U-005,Validation,v1.1,2,1,2,1
M-0305,Mortgage Prepayment,Forecasting,Prepayment,Treasury,U-010,U-028,,Initiation,v0.1,2,3,2,2
```

Expected result: 4 rows loaded, 1 rejected (row 5, validator_id: “Validator cannot be the model owner or developer”). Calculated tiers: M-0301 High, M-0302 High, M-0303 Medium, M-0305 Medium.
