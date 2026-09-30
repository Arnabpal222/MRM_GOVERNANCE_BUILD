"""Deterministic synthetic sample data for Phase 2 (models, validations, findings, approvals).

Writes CSV files to B_Inputs/AB_sample_data. Dates are relative to --reference-date (default today)
so revalidation and overdue states look the same on every run. Synthetic data only.

The 19 named models, findings and approvals come from the HTML prototype (C_Requirements/_OLD).
Phase 3 extends this generator to the full 256-model seed and the import templates.

Usage (from project root):
    python A_Codes/AD_seed/generate_samples.py [--reference-date 2026-09-30] [--generic 60]
"""
import argparse
import calendar
import csv
import random
from datetime import date, timedelta
from pathlib import Path

OUT_DIR = Path(__file__).resolve().parents[2] / "B_Inputs" / "AB_sample_data"
SEED = 20260930

FREQ_MONTHS = {"Monthly": 1, "Quarterly": 3, "Semi-annual": 6, "Annual": 12, "Biennial": 24}

# (id, name, type, subtype, tier, phase, owner, developer, validator, business line, version, frequency,
#  days to revalidation due, purpose, successor)
HEROES = [
    ("M-0012", "Wholesale PD Model", "Credit Risk", "PD", "High", "Monitoring", "J. Chen", "R. Kumar", "S. Patel", "Commercial Banking", "v3.1", "Annual", 198, "Estimates 12-month probability of default for wholesale commercial exposures from financial statements, market signals and behaviour.", None),
    ("M-0015", "Retail LGD Model", "Credit Risk", "LGD", "High", "Monitoring", "A. Williams", "T. Nguyen", "M. Garcia", "Retail Banking", "v2.4", "Annual", -24, "Loss given default for retail mortgage and unsecured portfolios, using collateral values and recovery timelines.", None),
    ("M-0023", "EAD Facility Model", "Credit Risk", "EAD", "Medium", "Monitoring", "D. Park", "K. Sharma", "L. Thompson", "Commercial Banking", "v1.3", "Annual", 188, "Exposure at default for revolving facilities and committed lines through credit conversion factors.", None),
    ("M-0031", "CECL Lifetime ECL", "Provisioning", "CECL", "High", "Reg/Audit", "B. Foster", "J. Lee", "C. Martinez", "Enterprise Risk", "v4.0", "Annual", 104, "Lifetime expected credit loss across commercial, retail and securities portfolios with weighted macroeconomic scenarios.", None),
    ("M-0038", "IFRS 9 Stage Allocation", "Provisioning", "IFRS 9", "High", "Reg/Audit", "N. Ahmed", "Y. Tanaka", "P. O'Brien", "International", "v2.2", "Annual", 63, "Significant-increase-in-credit-risk staging and forward-looking ECL for the international book.", None),
    ("M-0042", "ALM Interest Rate Risk", "Balance Sheet", "ALM/IRR", "High", "Monitoring", "R. Stevens", "H. Muller", "E. Wong", "Treasury", "v3.0", "Annual", -52, "Net interest income sensitivity and economic value of equity under parallel and non-parallel rate shocks.", None),
    ("M-0048", "Liquidity Stress Model", "Balance Sheet", "Liquidity", "High", "Monitoring", "G. Hoffman", "A. Costa", "T. Raj", "Treasury", "v2.1", "Semi-annual", 17, "LCR and NSFR projections under idiosyncratic and market-wide stress.", None),
    ("M-0055", "Revenue Forecasting Model", "Forecasting", "Revenue", "Medium", "Monitoring", "L. Kim", "S. Nakamura", "D. Brown", "Finance", "v2.0", "Annual", 88, "Multi-factor revenue projection for financial planning cycles.", None),
    ("M-0061", "Expense Projection Model", "Forecasting", "Expense", "Low", "Monitoring", "M. Taylor", "W. Zhang", "J. Fernandez", "Finance", "v1.5", "Biennial", 441, "Bottom-up expense forecast from cost-centre projections, inflation and headcount plans.", None),
    ("M-0071", "CCAR PPNR Model", "CCAR/Stress Testing", "PPNR", "High", "Implementation", "F. Johnson", "B. Gupta", "K. Ivanova", "Enterprise Risk", "v5.0", "Annual", None, "Pre-provision net revenue under baseline, adverse and severely adverse supervisory scenarios.", None),
    ("M-0076", "CCAR Loss Forecasting", "CCAR/Stress Testing", "Loss", "High", "Validation", "V. Petrov", "C. Okafor", "A. Dubois", "Enterprise Risk", "v4.2", None, None, "Net charge-offs and provision expense under stress scenarios across major portfolios.", None),
    ("M-0078", "CCAR Capital Adequacy", "CCAR/Stress Testing", "Capital", "High", "Validation", "J. Chen", "R. Kumar", "J. Chen", "Enterprise Risk", "v3.5", None, None, "CET1 ratio projection combining RWA dynamics, loss absorption and planned capital actions.", None),
    ("M-0082", "Market Risk VaR", "Credit Risk", "VaR", "High", "Development", "T. Fischer", "M. Rossi", None, "Capital Markets", "v1.0-draft", None, None, "Historical simulation VaR with expected shortfall for the trading book.", None),
    ("M-0085", "Behavioral Scorecard v2", "Credit Risk", "Scorecard", "Medium", "Development", "L. Kim", "P. Johansson", None, "Retail Banking", "v2.0-draft", None, None, "Behavioural score for existing retail customers from transaction patterns and bureau updates.", None),
    ("M-0089", "Climate Risk Transition", "Forecasting", "Climate", "Medium", "Initiation", "N. Ahmed", "S. Nakamura", None, "Enterprise Risk", "v0.1", None, None, "Transition-risk exposure to carbon-intensive sectors under NGFS scenarios.", None),
    ("M-0091", "Deposit Pricing Model", "Balance Sheet", "Deposit", "Low", "Initiation", "G. Hoffman", "A. Costa", None, "Treasury", "v0.1", None, None, "Non-maturity deposit pricing with rate sensitivity and balance elasticity.", None),
    ("M-0003", "Legacy PD Scorecard v1", "Credit Risk", "PD", "Low", "Retirement", "J. Chen", "R. Kumar", "S. Patel", "Retail Banking", "v1.0", None, None, "Original retail PD scorecard, replaced by M-0012 after a parallel run.", "M-0012"),
    ("M-0005", "Basel II IRB Floor Model", "Credit Risk", "Rating", "Low", "Retirement", "D. Park", "K. Sharma", "L. Thompson", "Enterprise Risk", "v2.0", None, None, "IRB output floor calculation, retired after the Basel III.1 implementation.", None),
    ("M-0008", "Legacy ALCO NII Model", "Balance Sheet", "ALM/IRR", "Low", "Retirement", "R. Stevens", "H. Muller", "E. Wong", "Treasury", "v1.5", None, None, "First-generation NII sensitivity model, replaced by M-0042.", "M-0042"),
]
LEGACY_SOD = {"M-0078"}

# (model, title, description, severity, category, status, days until due; negative = overdue)
HERO_FINDINGS = [
    ("M-0012", "CRE obligor data gap", "Segment B data quality gap: 14% of obligor financial statements missing in construction lending.", "Critical", "Data", "Open", -40),
    ("M-0012", "Macro overlay undocumented", "Model documentation does not reflect the December parameter update to the macro overlay.", "Medium", "Documentation", "Open", 45),
    ("M-0015", "LGD floor deviation", "LGD floor methodology deviates from policy.", "Medium", "Methodology", "Open", 20),
    ("M-0015", "Collateral valuation lag", "Collateral valuation lag above 90 days for 8% of the retail mortgage portfolio.", "Critical", "Data", "Open", -12),
    ("M-0031", "Scenario weights stale", "Macro scenario weights reflect prior-year ALCO assumptions and need committee refresh.", "Medium", "Methodology", "Open", 30),
    ("M-0031", "Q-factor evidence missing", "Q-factor documentation incomplete for the CRE segment.", "Medium", "Documentation", "Open", 55),
    ("M-0038", "Stage 2 triggers", "Stage 2 trigger calibration needs a post-pandemic refresh; thresholds over-stage by about 15%.", "Critical", "Methodology", "Open", 18),
    ("M-0038", "Cross-border staging", "GBP and EUR books apply different SICR definitions.", "Medium", "Data", "Open", 40),
    ("M-0038", "Disclosure template gap", "Pillar 3 disclosure table not aligned to the current template.", "Medium", "Documentation", "Open", 70),
    ("M-0042", "NMD behaviour assumptions", "Repricing beta assumes 60% pass-through against 72% observed.", "Medium", "Methodology", "Open", -8),
    ("M-0048", "Intraday data gap", "Four-hour gap in real-time position data from APAC operations.", "Medium", "Data", "Open", 25),
    ("M-0071", "NII rate path", "NII component needs rate-path recalibration: +200bp shock 15% above benchmark.", "Critical", "Methodology", "Open", 12),
    ("M-0071", "Fee income assumptions", "Fee income projection uses undocumented AUM growth assumptions.", "Medium", "Documentation", "Open", 35),
    ("M-0071", "Trading tail risk", "Trading revenue tail risk underestimated; 99th percentile exceedances twice the expected rate.", "Critical", "Methodology", "Open", 12),
    ("M-0071", "UAT sign-off", "UAT sign-off delayed by a core banking interface dependency.", "Medium", "Implementation", "In Progress", 20),
    ("M-0076", "CRE loss rates stale", "CRE loss rates based on 2019 vintage data; no post-pandemic structural update.", "Critical", "Data", "Open", 15),
    ("M-0076", "Auto loan recalibration", "Auto loan delinquency transition matrix not updated; subprime performance has diverged.", "Critical", "Methodology", "Open", 15),
    ("M-0076", "Static correlations", "Cross-portfolio correlation uses static assumptions with no tail dependence.", "Medium", "Methodology", "Open", 50),
    ("M-0076", "Scenario mapping", "Unemployment, HPI and commercial vacancy not mapped to supervisory scenario variables.", "Medium", "Data", "Open", 50),
    ("M-0076", "Sensitivity section", "Documentation lacks the sensitivity analysis section required by policy 4.2.3.", "Low", "Documentation", "Open", 80),
    ("M-0078", "RWA linkage", "Credit risk RWA feed into the capital projection is unreconciled.", "Critical", "Methodology", "Open", 10),
    ("M-0078", "Capital actions", "Dividend and buyback assumptions are undocumented.", "Medium", "Documentation", "Open", 40),
    ("M-0078", "Payout ratio conflict", "Dividend payout ratio assumption conflicts with the board-approved capital plan.", "Medium", "Methodology", "Open", 40),
]

# model -> [(forum, decision type, decision, conditions/notes, days ago)]
HERO_APPROVALS = {
    "M-0012": [("MRC", "Initial approval", "Approved", "Full validation within 6 months of go-live", 900), ("MRC", "Annual review", "Approved", "Annual recalibration; CRE segment under enhanced monitoring", 470), ("MRC", "Periodic review", "Conditional", "Resolve the CRE data gap by next quarter; interim risk adjustment on CRE outputs", 160)],
    "M-0015": [("MRC", "Initial approval", "Approved", "Semi-annual monitoring cadence", 820), ("MRC", "Annual review", "Approved", "Quarterly monitoring enhanced", 560), ("MRC", "Periodic review", "Conditional", "PSI breach requires recalibration; revalidation triggered", 385)],
    "M-0031": [("MRC", "Initial approval", "Approved", "Quarterly scenario weight review by ALCO", 1200), ("MRC", "Annual review", "Conditional", "Update macro scenario weights for the current rate environment", 440), ("MRC", "Annual review", "Approved", "Supervisory review readiness confirmed; CRE Q-factor evidence still pending", 260)],
    "M-0038": [("MRC", "Initial approval", "Approved", "Quarterly staging migration monitoring", 1100), ("MRC", "Periodic review", "Conditional", "Recalibrate Stage 2 triggers before next half-year close", 300)],
    "M-0042": [("MRC", "Initial approval", "Approved", "Quarterly NII backtesting required", 900), ("MRC", "Periodic review", "Approved", "Refresh NMD behavioural assumptions; revalidation triggered", 420)],
    "M-0048": [("MRC", "Initial approval", "Approved", "Semi-annual revalidation cycle", 870), ("MRC", "Periodic review", "Approved", "Stress gap KPI breach noted for next revalidation", 170)],
    "M-0071": [("MRC", "ToR", "Approved", "Scope extended to fee income and trading revenue sub-models", 470), ("Validation Committee", "Validation complete", "Conditional", "Five findings issued; remediation plan required", 260), ("MRC", "Pre-implementation", "Conditional", "Go-live blocked until the NII rate path and trading tail risk findings are resolved; interim v4.8 as fallback", 220)],
    "M-0082": [("MRC", "ToR", "Approved", "Complete the model development document by next quarter", 270)],
    "M-0085": [("MRC", "ToR", "Approved", "None", 230)],
    "M-0003": [("MRC", "Retirement", "Approved", "Archive complete; successor M-0012 validated", 480)],
    "M-0005": [("MRC", "Retirement", "Approved", "Decommission complete", 380)],
    "M-0008": [("MRC", "Retirement", "Approved", "Full archive with lineage link to M-0042", 250)],
}

TIER_ANSWERS = {"High": [(3, 3, 2, 3), (3, 2, 3, 3), (3, 3, 3, 3)], "Medium": [(2, 2, 2, 2), (2, 3, 2, 1), (3, 2, 2, 1)],
                "Low": [(1, 2, 1, 1), (1, 1, 2, 1), (2, 1, 1, 1)]}

FIRST_NAMES = {"J. Chen": "Jia Chen", "R. Kumar": "Rahul Kumar", "A. Williams": "Anna Williams", "T. Nguyen": "Thanh Nguyen",
               "M. Garcia": "Maria Garcia", "D. Park": "Daniel Park", "K. Sharma": "Kavya Sharma", "L. Thompson": "Laura Thompson",
               "B. Foster": "Ben Foster", "J. Lee": "Joon Lee", "C. Martinez": "Carmen Martinez", "N. Ahmed": "Nadia Ahmed",
               "Y. Tanaka": "Yuki Tanaka", "P. O'Brien": "Patrick O'Brien", "R. Stevens": "Ruth Stevens", "H. Muller": "Hans Muller",
               "E. Wong": "Emily Wong", "G. Hoffman": "Greta Hoffman", "A. Costa": "Andre Costa", "T. Raj": "Tara Raj",
               "L. Kim": "Lena Kim", "S. Nakamura": "Sora Nakamura", "D. Brown": "David Brown", "M. Taylor": "Megan Taylor",
               "W. Zhang": "Wei Zhang", "J. Fernandez": "Jorge Fernandez", "F. Johnson": "Fiona Johnson", "B. Gupta": "Bina Gupta",
               "K. Ivanova": "Katya Ivanova", "V. Petrov": "Viktor Petrov", "C. Okafor": "Chidi Okafor", "A. Dubois": "Amelie Dubois",
               "T. Fischer": "Tobias Fischer", "M. Rossi": "Marco Rossi", "P. Johansson": "Per Johansson"}
EXISTING_USERS = {"S. Patel": "U-014"}  # already in B_Inputs/AA_bootstrap/T01_users.csv

GENERIC_SUBTYPES = {"Credit Risk": ["PD", "LGD", "EAD", "Scorecard", "Rating", "Collections"],
                    "Provisioning": ["CECL", "IFRS 9", "Q-factor", "Reserve allocation"],
                    "Balance Sheet": ["ALM/IRR", "Liquidity", "Deposit", "Prepayment", "Funds transfer pricing"],
                    "Forecasting": ["Revenue", "Expense", "Balance", "Volume"],
                    "CCAR/Stress Testing": ["PPNR", "Loss", "Capital", "RWA", "Scenario"]}
GENERIC_SEGMENTS = ["Commercial", "Consumer", "Mortgage", "Card", "Small Business", "Treasury", "International", "CRE"]
GENERIC_BIZ = {"Credit Risk": ["Commercial Banking", "Retail Banking", "Business Banking"],
               "Provisioning": ["Enterprise Risk", "Finance", "International"], "Balance Sheet": ["Treasury"],
               "Forecasting": ["Finance", "Retail Banking"], "CCAR/Stress Testing": ["Enterprise Risk"]}
GENERIC_FINDINGS = {"Data": "Source extract does not reconcile to the ledger", "Methodology": "Segmentation not revisited since development",
                    "Documentation": "Assumption log incomplete", "Performance": "Rank-ordering weakened in the latest period",
                    "Implementation": "Production code differs from the validated version"}


def sub_months(d: date, months: int) -> date:
    idx = d.month - 1 - months
    y, m = d.year + idx // 12, idx % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def iso(d: date | None) -> str:
    return d.isoformat() if d else ""


def build(ref: date, generic: int):
    rnd = random.Random(SEED)
    people: dict[str, dict] = {}

    def person(short: str, role: str) -> str:
        if short in EXISTING_USERS:
            return EXISTING_USERS[short]
        if short not in people:
            uid = f"U-{101 + len(people)}"
            full = FIRST_NAMES.get(short, short)
            people[short] = {"user_id": uid, "full_name": full,
                             "email": full.lower().replace(" ", ".").replace("'", "") + "@demo-bank.example",
                             "roles": set(), "business_line": ""}
        people[short]["roles"].add(role)
        return people[short]["user_id"]

    models, validations, findings, approvals = [], [], [], []

    def add_model(mid, name, mtype, sub, tier, phase, owner, dev, val, biz, ver, freq, due_days, purpose, successor):
        answers = rnd.choice(TIER_ANSWERS[tier])
        needs_dates = phase in ("Monitoring", "Reg/Audit")
        last_val = go_live = None
        if needs_dates:
            due = ref + timedelta(days=due_days)
            last_val = sub_months(due, FREQ_MONTHS[freq])
            go_live = last_val - timedelta(days=rnd.randint(200, 900))
        owner_id, dev_id = person(owner, "Model Owner"), person(dev, "Model Developer")
        val_id = person(val, "Validator") if val else None
        models.append({"model_id": mid, "model_name": name, "model_type": mtype, "model_subtype": sub, "purpose": purpose,
                       "business_line": biz, "owner_id": owner_id, "developer_id": dev_id, "validator_id": val_id or "",
                       "lifecycle_phase": phase, "version": ver, "go_live_date": iso(go_live),
                       "revalidation_frequency": freq if needs_dates else "", "last_validation_date": iso(last_val),
                       "q_materiality": answers[0], "q_complexity": answers[1], "q_reliance": answers[2],
                       "q_regulatory_use": answers[3], "successor_model_id": successor or "",
                       "legacy_sod_exception": "Y" if mid in LEGACY_SOD else "N"})
        return last_val, owner_id, val_id

    info = {}
    for h in HEROES:
        info[h[0]] = add_model(*h)

    types = list(GENERIC_SUBTYPES)
    validators = [p for p in ("M. Garcia", "L. Thompson", "C. Martinez", "E. Wong", "T. Raj", "D. Brown", "A. Dubois")]
    owners = ["D. Park", "L. Kim", "B. Foster", "R. Stevens", "M. Taylor", "N. Ahmed"]
    devs = ["K. Sharma", "S. Nakamura", "J. Lee", "H. Muller", "W. Zhang", "Y. Tanaka"]
    phases = ["Initiation"] * 2 + ["Development"] * 4 + ["Validation"] * 4 + ["Implementation"] * 3 + ["Monitoring"] * 36 + ["Reg/Audit"] * 4 + ["Retirement"] * 3
    for i in range(generic):
        mid = f"M-{101 + i:04d}"
        mtype = types[i % len(types)]
        sub = rnd.choice(GENERIC_SUBTYPES[mtype])
        phase = phases[i % len(phases)]
        tier = rnd.choices(["High", "Medium", "Low"], weights=[35, 41, 24])[0]
        freq = rnd.choice(["Annual", "Annual", "Semi-annual", "Biennial"])
        due_days = rnd.randint(-60, FREQ_MONTHS[freq] * 30 - 5)  # keeps last validation date in the past
        val = rnd.choice(validators) if phase not in ("Initiation", "Development") else None
        name = f"{rnd.choice(GENERIC_SEGMENTS)} {sub} Model"
        info[mid] = add_model(mid, name, mtype, sub, tier, phase, rnd.choice(owners), rnd.choice(devs), val,
                              rnd.choice(GENERIC_BIZ[mtype]), f"v{rnd.randint(1, 4)}.{rnd.randint(0, 9)}", freq,
                              due_days, f"{sub} model for the {name.split()[0].lower()} portfolio.", None)

    # Validations: one completed validation at the last validation date; in-progress for Validation phase.
    vno = 1
    latest_validation = {}
    for m in models:
        mid, phase = m["model_id"], m["lifecycle_phase"]
        last_val, _, val_id = info[mid]
        hero_appr = HERO_APPROVALS.get(mid, [])
        if last_val:
            outcome = "Conditional" if hero_appr and hero_appr[-1][2] == "Conditional" else "Approved"
            vid = f"V-{vno:04d}"; vno += 1
            validations.append({"validation_id": vid, "model_id": mid, "validation_type": "Periodic",
                                "validator_id": val_id, "start_date": iso(last_val - timedelta(days=45)),
                                "completion_date": iso(last_val), "outcome": outcome})
            latest_validation[mid] = vid
        elif mid == "M-0071":
            vid = f"V-{vno:04d}"; vno += 1
            done = ref - timedelta(days=260)
            validations.append({"validation_id": vid, "model_id": mid, "validation_type": "Initial",
                                "validator_id": val_id, "start_date": iso(done - timedelta(days=60)),
                                "completion_date": iso(done), "outcome": "Conditional"})
            latest_validation[mid] = vid
        elif phase == "Validation":
            # M-0078's assigned validator conflicts with the owner; the exercise is run by an independent validator.
            runner = person("A. Dubois", "Validator") if mid in LEGACY_SOD else val_id
            vid = f"V-{vno:04d}"; vno += 1
            validations.append({"validation_id": vid, "model_id": mid, "validation_type": "Initial",
                                "validator_id": runner, "start_date": iso(ref - timedelta(days=40)),
                                "completion_date": "", "outcome": "In Progress"})
            latest_validation[mid] = vid

    fno = 1
    for mid, title, desc, sev, cat, status, due_in in HERO_FINDINGS:
        due = ref + timedelta(days=due_in)
        raised = min(ref - timedelta(days=60), due - timedelta(days=30))
        findings.append({"finding_id": f"F-{fno:04d}", "model_id": mid, "validation_id": latest_validation.get(mid, ""),
                         "title": title, "description": desc, "severity": sev, "category": cat, "status": status,
                         "owner_id": info[mid][1], "raised_date": iso(raised), "due_date": iso(due), "closed_date": ""})
        fno += 1
    for m in models[len(HEROES):]:
        mid = m["model_id"]
        if m["lifecycle_phase"] not in ("Monitoring", "Reg/Audit", "Validation", "Implementation") or rnd.random() < 0.45:
            continue
        for _ in range(rnd.randint(1, 3)):
            cat = rnd.choice(list(GENERIC_FINDINGS))
            sev = rnd.choices(["Critical", "Medium", "Low"], weights=[15, 55, 30])[0]
            raised = ref - timedelta(days=rnd.randint(30, 300))
            due = raised + timedelta(days=rnd.randint(60, 240))
            closed = rnd.random() < 0.3
            findings.append({"finding_id": f"F-{fno:04d}", "model_id": mid, "validation_id": latest_validation.get(mid, ""),
                             "title": GENERIC_FINDINGS[cat], "description": f"{GENERIC_FINDINGS[cat]} ({m['model_name']}).",
                             "severity": sev, "category": cat, "status": "Closed" if closed else rnd.choice(["Open", "In Progress"]),
                             "owner_id": info[mid][1], "raised_date": iso(raised), "due_date": iso(due),
                             "closed_date": iso(min(ref, due - timedelta(days=rnd.randint(0, 30)))) if closed else ""})
            fno += 1

    ano = 200
    for mid, rows in HERO_APPROVALS.items():
        for idx, (forum, dtype, decision, notes, days_ago) in enumerate(rows):
            ano += 1
            d = ref - timedelta(days=days_ago)
            is_latest = idx == len(rows) - 1
            cond = decision == "Conditional"
            approvals.append({"approval_id": f"A-{ano:04d}", "model_id": mid, "decision_date": iso(d), "forum": forum,
                              "decision_type": dtype, "decision": decision, "conditions": notes if cond else "",
                              "condition_due_date": iso(d + timedelta(days=120)) if cond else "",
                              "condition_status": ("Open" if is_latest else "Met") if cond else ""})
    for m in models[len(HEROES):]:
        if m["lifecycle_phase"] in ("Implementation", "Monitoring", "Reg/Audit", "Retirement") and rnd.random() < 0.85:
            ano += 1
            d = ref - timedelta(days=rnd.randint(60, 700))
            decision = rnd.choices(["Approved", "Conditional"], weights=[80, 20])[0]
            cond = decision == "Conditional"
            dtype = "Retirement" if m["lifecycle_phase"] == "Retirement" else "Annual review"
            approvals.append({"approval_id": f"A-{ano:04d}", "model_id": m["model_id"], "decision_date": iso(d),
                              "forum": "MRC", "decision_type": dtype, "decision": decision,
                              "conditions": "Recalibrate before the next review" if cond else "",
                              "condition_due_date": iso(d + timedelta(days=120)) if cond else "",
                              "condition_status": rnd.choice(["Open", "Met"]) if cond else ""})

    users = [{"user_id": p["user_id"], "full_name": p["full_name"], "email": p["email"],
              "role": "; ".join(sorted(p["roles"])), "business_line": "Model Risk Management" if "Validator" in p["roles"] else "",
              "active": "Y"} for p in people.values()]
    return users, models, validations, findings, approvals


def write(out_dir: Path, name: str, rows: list[dict]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with (out_dir / name).open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"  {name}: {len(rows)} rows")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference-date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--generic", type=int, default=60, help="number of generic models in addition to the 19 named ones")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    args = ap.parse_args()
    print(f"Writing sample data to {args.out} (reference date {args.reference_date})")
    generate(args.out, args.reference_date, args.generic)


def generate(out_dir: Path, reference_date: date, generic: int = 60) -> None:
    users, models, validations, findings, approvals = build(reference_date, generic)
    for name, rows in (("T01_users.csv", users), ("T02_models.csv", models), ("T03_validations.csv", validations),
                       ("T04_findings.csv", findings), ("T05_approvals.csv", approvals)):
        write(out_dir, name, rows)


if __name__ == "__main__":
    main()
