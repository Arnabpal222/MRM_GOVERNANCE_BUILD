"""Deterministic 256-model seed (design §9 seed targets), written as the real import templates.

The seed is loaded through the import engine (Admin → Reset, or `python -m app.cli reset`), so the
database is always rebuilt through the same path a user import takes. Templates come from the backend
template registry (the single source of truth), so the seed can never drift from the import rules.

Targets: 256 models; tiers High 89 / Medium 106 / Low 61; types Credit Risk 78, Provisioning 42,
Balance Sheet 48, Forecasting 52, CCAR/Stress Testing 36; phases Initiation 6, Development 14,
Validation 18, Implementation 11, Monitoring 179 (31 in the Revalidation column, 8 overdue),
Reg/Audit 14, Retirement 14. The 19 named prototype models keep their IDs, findings and approvals.

Usage (from project root, backend venv):
    A_Codes/AB_backend/.venv/Scripts/python A_Codes/AD_seed/generate_seed.py [--reference-date YYYY-MM-DD]
Also writes the demo upload files to B_Inputs/AD_demo_files.
"""
import argparse
import csv
import random
import sys
from datetime import date, timedelta
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "AB_backend"))
sys.path.insert(0, str(HERE))

from app.ingestion import checks, fileio  # noqa: E402
from app.ingestion.registry import get_template  # noqa: E402
from app.rules.policy_values import parse_policy_value  # noqa: E402
from app.services.policy_access import Policy  # noqa: E402
from generate_samples import (  # noqa: E402
    FIRST_NAMES,
    FREQ_MONTHS,
    GENERIC_FINDINGS,
    HERO_APPROVALS,
    HERO_FINDINGS,
    HEROES,
    LEGACY_SOD,
    TIER_ANSWERS,
    sub_months,
)

SEED_DIR = PROJECT / "B_Inputs" / "AC_seed"
DEMO_DIR = PROJECT / "B_Inputs" / "AD_demo_files"
BOOTSTRAP = PROJECT / "B_Inputs" / "AA_bootstrap"
RANDOM_SEED = 20260930

TYPE_TARGET = {"Credit Risk": 78, "Provisioning": 42, "Balance Sheet": 48, "Forecasting": 52, "CCAR/Stress Testing": 36}
TIER_TARGET = {"High": 89, "Medium": 106, "Low": 61}
PHASE_TARGET = {"Initiation": 6, "Development": 14, "Validation": 18, "Implementation": 11, "Monitoring": 179,
                "Reg/Audit": 14, "Retirement": 14}
REVAL_COLUMN_TARGET, OVERDUE_TARGET, LEAD_DAYS = 31, 8, 60

SUBTYPES = {"Credit Risk": ["PD", "LGD", "EAD", "Scorecard", "Rating", "Collections"],
            "Provisioning": ["CECL", "IFRS 9", "Q-factor", "Reserve allocation"],
            "Balance Sheet": ["ALM/IRR", "Liquidity", "Deposit", "Prepayment", "Funds transfer pricing"],
            "Forecasting": ["Revenue", "Expense", "Balance", "Volume", "Climate"],
            "CCAR/Stress Testing": ["PPNR", "Loss", "Capital", "RWA", "Scenario"]}
SEGMENTS = {"Credit Risk": ["Commercial & Industrial", "CRE Office", "Residential Mortgage", "Auto Loan", "Credit Card",
                            "Small Business", "HELOC", "Wealth Lending", "Dealer Floorplan", "Student Lending"],
            "Provisioning": ["Commercial", "Consumer", "Securities", "CRE", "Card", "International"],
            "Balance Sheet": ["Non-maturity Deposit", "Treasury", "Mortgage", "Wholesale Funding", "Securities Portfolio"],
            "Forecasting": ["Net Interest Income", "Fee Income", "Operating Expense", "Loan Volume", "Deposit Volume", "Branch"],
            "CCAR/Stress Testing": ["Enterprise", "CRE", "Consumer", "Trading Book", "Operational"]}
BIZ = {"Credit Risk": ["Commercial Banking", "Retail Banking", "Business Banking", "Wealth Management"],
       "Provisioning": ["Enterprise Risk", "Finance", "International"], "Balance Sheet": ["Treasury"],
       "Forecasting": ["Finance", "Retail Banking", "Enterprise Risk"], "CCAR/Stress Testing": ["Enterprise Risk"]}
STAFF = {  # generic staff pool, in addition to bootstrap users and prototype people
    "Model Owner": ["Olivia Grant", "Samuel Osei", "Irene Novak", "Hiro Sato", "Claire Dubois", "Mateo Ruiz"],
    "Model Developer": ["Leah Cohen", "Arjun Mehta", "Sofia Rossi", "Kwame Mensah", "Elena Petrova", "Lucas Martin"],
    "Validator": ["Priyanka Das", "Oskar Lindqvist", "Fatima Al-Sayed", "George Adeyemi", "Mei Lin", "Rafael Souza"],
}
BOOTSTRAP_POOL = {"Model Owner": ["U-003", "U-007"], "Model Developer": ["U-021"], "Validator": ["U-014", "U-016"]}


def _expand(target: dict[str, int], fixed: list[str]) -> list[str]:
    """Values still needed after the hero models, as a flat list."""
    remaining = dict(target)
    for v in fixed:
        remaining[v] -= 1
    assert all(n >= 0 for n in remaining.values()), remaining
    return [k for k, n in remaining.items() for _ in range(n)]


def build(ref: date):
    rnd = random.Random(RANDOM_SEED)
    iso = lambda d: d.isoformat() if d else None  # noqa: E731

    # --- users ------------------------------------------------------------------------------
    with (BOOTSTRAP / "T01_users.csv").open(encoding="utf-8-sig") as fh:
        users = {r["user_id"]: {**r} for r in csv.DictReader(fh)}
    people: dict[str, str] = {"S. Patel": "U-014"}

    def hero_person(short: str, role: str) -> str:
        if short not in people:
            uid = f"U-{101 + len([p for p in people.values() if p.startswith('U-1')])}"
            full = FIRST_NAMES.get(short, short)
            people[short] = uid
            users[uid] = {"user_id": uid, "full_name": full, "role": "",
                          "email": full.lower().replace(" ", ".").replace("'", "") + "@demo-bank.example",
                          "business_line": "", "active": "Y"}
        uid = people[short]
        roles = {r.strip() for r in users[uid]["role"].split(";") if r.strip()} | {role}
        users[uid]["role"] = "; ".join(sorted(roles))
        return uid

    pools: dict[str, list[str]] = {}
    n = 201
    for role, names in STAFF.items():
        pools[role] = list(BOOTSTRAP_POOL[role])
        for full in names:
            uid = f"U-{n}"; n += 1
            users[uid] = {"user_id": uid, "full_name": full, "role": role, "business_line": "",
                          "email": full.lower().replace(" ", ".") + "@demo-bank.example", "active": "Y"}
            pools[role].append(uid)

    # --- models -----------------------------------------------------------------------------
    models, info = [], {}

    def add_model(mid, name, mtype, sub, tier, phase, owner, dev, val, biz, ver, freq, due_days, purpose, successor,
                  legacy=False):
        answers = rnd.choice(TIER_ANSWERS[tier])
        dated = phase in ("Monitoring", "Reg/Audit")
        last_val = go_live = None
        if dated:
            last_val = sub_months(ref + timedelta(days=due_days), FREQ_MONTHS[freq])
            go_live = last_val - timedelta(days=rnd.randint(200, 900))
        models.append({"model_id": mid, "model_name": name, "model_type": mtype, "model_subtype": sub,
                       "purpose": purpose, "business_line": biz, "model_family": None, "owner_id": owner,
                       "developer_id": dev, "validator_id": val, "lifecycle_phase": phase, "version": ver,
                       "go_live_date": iso(go_live), "revalidation_frequency": freq if dated else None,
                       "last_validation_date": iso(last_val), "q_materiality": answers[0], "q_complexity": answers[1],
                       "q_reliance": answers[2], "q_regulatory_use": answers[3], "successor_model_id": successor,
                       "legacy_sod_exception": "Y" if legacy else "N"})
        info[mid] = {"last_val": last_val, "owner": owner, "validator": val, "phase": phase, "type": mtype,
                     "name": name}

    hero_ids = set()
    for h in HEROES:
        (mid, name, mtype, sub, tier, phase, owner, dev, val, biz, ver, freq, due, purpose, succ) = h
        hero_ids.add(mid)
        add_model(mid, name, mtype, sub, tier, phase, hero_person(owner, "Model Owner"), hero_person(dev, "Model Developer"),
                  hero_person(val, "Validator") if val else None, biz, ver, freq, due, purpose, succ, mid in LEGACY_SOD)

    types = _expand(TYPE_TARGET, [h[2] for h in HEROES])
    tiers = _expand(TIER_TARGET, [h[4] for h in HEROES])
    phases = _expand(PHASE_TARGET, [h[5] for h in HEROES])
    for lst in (types, tiers, phases):
        rnd.shuffle(lst)

    # Monitoring due-date plan so the Revalidation column and overdue counts hit their targets.
    hero_mon_due = [h[12] for h in HEROES if h[5] == "Monitoring"]
    overdue_needed = OVERDUE_TARGET - sum(1 for d in hero_mon_due if d < 0)
    window_needed = REVAL_COLUMN_TARGET - OVERDUE_TARGET - sum(1 for d in hero_mon_due if 0 <= d <= LEAD_DAYS)
    mon_plan = ["overdue"] * overdue_needed + ["window"] * window_needed
    mon_plan += ["later"] * (phases.count("Monitoring") - len(mon_plan))
    rnd.shuffle(mon_plan)

    free_ids = (f"M-{i:04d}" for i in range(1, 400) if f"M-{i:04d}" not in hero_ids)
    used_names = {m["model_name"] for m in models}
    for mtype, tier, phase in zip(types, tiers, phases):
        mid = next(free_ids)
        sub = rnd.choice(SUBTYPES[mtype])
        name = f"{rnd.choice(SEGMENTS[mtype])} {sub} Model"
        k = 2
        while name in used_names:
            name = f"{name.rsplit(' v', 1)[0]} v{k}"; k += 1
        used_names.add(name)
        freq = rnd.choice(["Annual", "Annual", "Annual", "Semi-annual", "Biennial"])
        if phase == "Monitoring":
            kind = mon_plan.pop()
            due = {"overdue": rnd.randint(-90, -1), "window": rnd.randint(0, LEAD_DAYS)}.get(
                kind, rnd.randint(LEAD_DAYS + 1, FREQ_MONTHS[freq] * 30 - 5))
        else:
            due = rnd.randint(LEAD_DAYS + 1, FREQ_MONTHS[freq] * 30 - 5)
        owner, dev = rnd.choice(pools["Model Owner"]), rnd.choice(pools["Model Developer"])
        val = rnd.choice(pools["Validator"]) if phase not in ("Initiation", "Development") else None
        add_model(mid, name, mtype, sub, tier, phase, owner, dev, val, rnd.choice(BIZ[mtype]),
                  f"v{rnd.randint(1, 4)}.{rnd.randint(0, 9)}", freq, due,
                  f"{sub} model for the {name.split(' ' + sub)[0].lower()} portfolio.", None)

    # --- validations ---------------------------------------------------------------------------
    validations, latest_val = [], {}
    vno = 1

    def add_validation(mid, vtype, validator, start, done, outcome):
        nonlocal vno
        vid = f"V-{vno:04d}"; vno += 1
        validations.append({"validation_id": vid, "model_id": mid, "validation_type": vtype, "validator_id": validator,
                            "start_date": iso(start), "completion_date": iso(done), "outcome": outcome,
                            "summary": None, "recommendations": None})
        latest_val[mid] = vid

    for m in sorted(models, key=lambda x: x["model_id"]):
        mid, i = m["model_id"], info[m["model_id"]]
        hero_appr = HERO_APPROVALS.get(mid, [])
        if i["last_val"]:
            earlier = i["last_val"] - timedelta(days=365 + rnd.randint(0, 200))
            add_validation(mid, "Initial", i["validator"], earlier - timedelta(days=60), earlier, "Approved")
            outcome = "Conditional" if hero_appr and hero_appr[-1][2] == "Conditional" else (
                "Conditional" if mid not in hero_ids and rnd.random() < 0.15 else "Approved")
            add_validation(mid, "Periodic", i["validator"], i["last_val"] - timedelta(days=45), i["last_val"], outcome)
        elif i["phase"] == "Implementation":
            done = ref - timedelta(days=260 if mid == "M-0071" else rnd.randint(60, 200))
            add_validation(mid, "Initial", i["validator"], done - timedelta(days=60), done,
                           "Conditional" if mid == "M-0071" else "Approved")
        elif i["phase"] == "Validation":
            runner = hero_person("A. Dubois", "Validator") if mid in LEGACY_SOD else i["validator"]
            add_validation(mid, "Initial", runner, ref - timedelta(days=rnd.randint(20, 70)), None, "In Progress")

    # --- findings ---------------------------------------------------------------------------------
    findings, fno = [], 1

    def add_finding(mid, title, desc, sev, cat, status, raised, due, closed):
        nonlocal fno
        findings.append({"finding_id": f"F-{fno:04d}", "model_id": mid, "validation_id": latest_val.get(mid),
                         "title": title, "description": desc, "severity": sev, "category": cat, "status": status,
                         "owner_id": info[mid]["owner"], "raised_date": iso(raised), "due_date": iso(due),
                         "closed_date": iso(closed), "root_cause": None, "management_response": None,
                         "remediation_action": None})
        fno += 1

    for mid, title, desc, sev, cat, status, due_in in HERO_FINDINGS:
        due = ref + timedelta(days=due_in)
        add_finding(mid, title, desc, sev, cat, status, min(ref - timedelta(days=60), due - timedelta(days=30)), due, None)
    for m in models:
        mid = m["model_id"]
        if mid in hero_ids or info[mid]["phase"] not in ("Validation", "Implementation", "Monitoring", "Reg/Audit"):
            continue
        if rnd.random() < 0.5:
            continue
        for _ in range(rnd.randint(1, 3)):
            cat = rnd.choice(list(GENERIC_FINDINGS))
            sev = rnd.choices(["Critical", "Medium", "Low"], weights=[12, 58, 30])[0]
            raised = ref - timedelta(days=rnd.randint(20, 400))
            due = raised + timedelta(days=rnd.randint(60, 240))
            closed = rnd.random() < 0.35
            closed_on = min(ref, due - timedelta(days=rnd.randint(0, 30))) if closed else None
            if closed_on and closed_on < raised:
                closed_on = raised
            add_finding(mid, GENERIC_FINDINGS[cat], f"{GENERIC_FINDINGS[cat]} ({info[mid]['name']}).", sev, cat,
                        "Closed" if closed else rnd.choice(["Open", "Open", "In Progress"]), raised, due, closed_on)

    # --- approvals ----------------------------------------------------------------------------------
    approvals, ano = [], 200

    def add_approval(mid, forum, dtype, decision, notes, d, cond_status):
        nonlocal ano
        ano += 1
        cond = decision == "Conditional"
        approvals.append({"approval_id": f"A-{ano:04d}", "model_id": mid, "decision_date": iso(d), "forum": forum,
                          "decision_type": dtype, "decision": decision, "conditions": notes if cond else None,
                          "condition_due_date": iso(d + timedelta(days=120)) if cond else None,
                          "condition_status": cond_status if cond else None})

    for mid, rows in HERO_APPROVALS.items():
        for idx, (forum, dtype, decision, notes, days_ago) in enumerate(rows):
            add_approval(mid, forum, dtype, decision, notes, ref - timedelta(days=days_ago),
                         "Open" if idx == len(rows) - 1 else "Met")
    for m in models:
        mid, phase = m["model_id"], info[m["model_id"]]["phase"]
        if mid in hero_ids:
            continue
        if phase == "Development" and rnd.random() < 0.7:
            add_approval(mid, "MRC", "ToR", "Approved", None, ref - timedelta(days=rnd.randint(60, 300)), None)
        elif phase in ("Implementation", "Monitoring", "Reg/Audit"):
            add_approval(mid, "MRC", "Initial approval", "Approved", None, ref - timedelta(days=rnd.randint(500, 1100)), None)
            if phase != "Implementation" and rnd.random() < 0.8:
                decision = rnd.choices(["Approved", "Conditional"], weights=[82, 18])[0]
                add_approval(mid, "MRC", "Annual review", decision, "Recalibrate before the next review",
                             ref - timedelta(days=rnd.randint(30, 400)), rnd.choice(["Open", "Met"]))
        elif phase == "Retirement":
            add_approval(mid, "MRC", "Retirement", "Approved", None, ref - timedelta(days=rnd.randint(60, 500)), None)

    user_rows = sorted(users.values(), key=lambda u: u["user_id"])
    return user_rows, sorted(models, key=lambda m: m["model_id"]), validations, findings, approvals


def _policy_rows() -> list[dict]:
    with (BOOTSTRAP / "T12_policy_settings.csv").open(encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def _policy(rows: list[dict]) -> Policy:
    return Policy({r["setting_key"]: parse_policy_value(r["value"], r["value_type"]) for r in rows})


def _write(out: Path, file_name: str, template_id: str, rows: list[dict], policy: Policy) -> None:
    t = get_template(template_id)
    out.mkdir(parents=True, exist_ok=True)
    if file_name.endswith(".csv"):
        data = fileio.write_csv(t, rows)
    else:
        data = fileio.write_workbook(t, rows, checks.allowed_values(t, policy))
    (out / file_name).write_bytes(data)
    print(f"  {out.name}/{file_name}: {len(rows)} rows")


def demo_files(ref: date, policy: Policy, out: Path) -> None:
    """Files uploaded live in the demo script (design §10), each with one deliberate problem."""
    base = {"model_family": None, "go_live_date": None, "revalidation_frequency": None, "last_validation_date": None,
            "successor_model_id": None, "legacy_sod_exception": None}
    new_models = [
        {**base, "model_id": "M-0301", "model_name": "SME Probability of Default", "model_type": "Credit Risk",
         "model_subtype": "PD", "purpose": "12-month PD for small and medium enterprise lending.",
         "business_line": "Business Banking", "owner_id": "U-003", "developer_id": "U-021", "validator_id": "U-014",
         "lifecycle_phase": "Validation", "version": "v1.0", "q_materiality": 3, "q_complexity": 2, "q_reliance": 3,
         "q_regulatory_use": 3},
        {**base, "model_id": "M-0302", "model_name": "CRE Lifetime Loss", "model_type": "Provisioning",
         "model_subtype": "CECL", "purpose": "Lifetime expected loss for commercial real estate.",
         "business_line": "Commercial Real Estate", "owner_id": "U-007", "developer_id": "U-021", "validator_id": "U-016",
         "lifecycle_phase": "Validation", "version": "v2.0", "q_materiality": 3, "q_complexity": 3, "q_reliance": 2,
         "q_regulatory_use": 3},
        {**base, "model_id": "M-0303", "model_name": "Card Fraud Scorecard", "model_type": "Credit Risk",
         "model_subtype": "Scorecard", "purpose": "Transaction fraud score for consumer cards.",
         "business_line": "Consumer Cards", "owner_id": "U-003", "developer_id": "U-021", "validator_id": None,
         "lifecycle_phase": "Development", "version": "v0.9", "q_materiality": 2, "q_complexity": 2, "q_reliance": 2,
         "q_regulatory_use": 1},
        {**base, "model_id": "M-0304", "model_name": "Branch Deposit Forecast", "model_type": "Forecasting",
         "model_subtype": "Deposits", "purpose": "Branch-level deposit balance forecast.",
         "business_line": "Retail Banking", "owner_id": "U-007", "developer_id": "U-021", "validator_id": "U-007",
         "lifecycle_phase": "Validation", "version": "v1.1", "q_materiality": 2, "q_complexity": 1, "q_reliance": 2,
         "q_regulatory_use": 1},  # deliberate: validator is the owner (segregation of duties)
        {**base, "model_id": "M-0305", "model_name": "Mortgage Prepayment", "model_type": "Forecasting",
         "model_subtype": "Prepayment", "purpose": "Prepayment speeds for the mortgage book.",
         "business_line": "Treasury", "owner_id": "U-003", "developer_id": "U-021", "validator_id": None,
         "lifecycle_phase": "Initiation", "version": "v0.1", "q_materiality": 2, "q_complexity": 3, "q_reliance": 2,
         "q_regulatory_use": 2},
    ]
    _write(out, "T02_new_models_demo.xlsx", "T02", new_models, policy)
    d = lambda n: (ref + timedelta(days=n)).isoformat()  # noqa: E731
    f = {"validation_id": None, "status": "Open", "owner_id": "U-003", "closed_date": None, "root_cause": None,
         "management_response": None, "remediation_action": None}
    findings = [
        {**f, "finding_id": "F-9001", "model_id": "M-0012", "title": "Override log incomplete",
         "description": "Manual overrides are not logged.", "severity": "Low", "category": "Documentation",
         "raised_date": d(-10), "due_date": d(80)},
        {**f, "finding_id": "F-9002", "model_id": "M-0012", "title": "Challenger model missing",
         "description": "No challenger benchmark.", "severity": "Severe", "category": "Methodology",
         "raised_date": d(-10), "due_date": d(80)},  # deliberate: severity not allowed
        {**f, "finding_id": "F-9003", "model_id": "M-9999", "title": "Unknown model",
         "description": "References a model that does not exist.", "severity": "Medium", "category": "Data",
         "raised_date": d(-10), "due_date": d(80)},  # deliberate: model does not exist
        {**f, "finding_id": "F-9004", "model_id": "M-0042", "title": "Closed without date",
         "description": "Status Closed but no closed date.", "severity": "Medium", "category": "Data",
         "status": "Closed", "raised_date": d(-40), "due_date": d(20)},  # deliberate: closed_date missing
        {**f, "finding_id": "F-9005", "model_id": "M-0042", "title": "Prepayment curve stale",
         "description": "Prepayment curve not refreshed this year.", "severity": "Medium", "category": "Performance",
         "raised_date": "15/09/2026", "due_date": d(60)},  # deliberate: date not ISO
    ]
    _write(out, "T04_findings_demo_errors.csv", "T04", findings, policy)


def generate(out_dir: Path, reference_date: date, demo_dir: Path | None = DEMO_DIR) -> None:
    policy_rows = _policy_rows()
    policy = _policy(policy_rows)
    users, models, validations, findings, approvals = build(reference_date)
    _write(out_dir, "T12_policy_settings.xlsx", "T12", policy_rows, policy)
    _write(out_dir, "T01_users.xlsx", "T01", users, policy)
    _write(out_dir, "T02_model_inventory.xlsx", "T02", models, policy)
    _write(out_dir, "T03_validation_history.xlsx", "T03", validations, policy)
    _write(out_dir, "T04_findings.xlsx", "T04", findings, policy)
    _write(out_dir, "T05_approvals.xlsx", "T05", approvals, policy)
    if demo_dir is not None:
        demo_files(reference_date, policy, demo_dir)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reference-date", type=date.fromisoformat, default=date.today())
    ap.add_argument("--out", type=Path, default=SEED_DIR)
    args = ap.parse_args()
    print(f"Writing seed for reference date {args.reference_date}")
    generate(args.out, args.reference_date)


if __name__ == "__main__":
    main()
