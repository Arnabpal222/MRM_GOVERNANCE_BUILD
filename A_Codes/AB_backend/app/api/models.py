from dataclasses import asdict

from fastapi import APIRouter, status
from sqlalchemy import select

from app.api.deps import CurrentPrincipal, DbSession
from app.models import AppUser, Model, ModelPhaseHistory, ModelVersion, TierOverride
from app.rules import model_rules, revalidation, tiering
from app.schemas.governance import (
    FindingOut,
    Model360Out,
    ModelCreate,
    ModelMetaOut,
    ModelOut,
    ModelStateOut,
    ModelSummaryOut,
    ModelUpdate,
    RelationshipCreate,
    RelationshipOut,
    ScoreOut,
    TierOverrideRequest,
    TierPreviewOut,
    TieringAnswers,
    TransitionRequest,
)
from app.services import (
    approval_service,
    finding_service,
    governance_view,
    model_service,
    user_service,
    validation_service,
)
from app.services.policy_access import Policy

router = APIRouter(prefix="/api/models", tags=["models"])


def _state_out(state: governance_view.ModelState) -> ModelStateOut:
    data = {k: v for k, v in asdict(state).items() if k not in ("score", "calculated_at")}
    return ModelStateOut(**data, score=state.score.overall)


def _score_out(state: governance_view.ModelState) -> ScoreOut:
    return ScoreOut(overall=state.score.overall, reason=state.score.reason, calculated_at=state.calculated_at,
                    components=[asdict(c) for c in state.score.components])


def finding_out(f, policy: Policy) -> FindingOut:
    a = finding_service.age(f, policy)
    return FindingOut.model_validate(f).model_copy(
        update={"days_open": a.days_open, "days_overdue": a.days_overdue, "is_overdue": a.is_overdue})


@router.get("", response_model=list[ModelSummaryOut])
def list_models(
    db: DbSession, _: CurrentPrincipal, model_type: str | None = None, tier: str | None = None,
    phase: str | None = None, business_line: str | None = None, column: str | None = None,
    revalidation_status: str | None = None, search: str | None = None, owner_id: str | None = None,
    flag: str | None = None,
):
    rows = governance_view.portfolio(db, model_type=model_type, tier=tier, phase=phase, business_line=business_line,
                                     column=column, revalidation_status=revalidation_status, search=search,
                                     owner_id=owner_id, flag=flag)
    fields = [f for f in ModelSummaryOut.model_fields if f != "state"]
    return [ModelSummaryOut(**{f: getattr(m, f) for f in fields}, state=_state_out(s)) for m, s in rows]


@router.get("/meta", response_model=ModelMetaOut)
def model_meta(db: DbSession, _: CurrentPrincipal):
    p = Policy.load(db)
    phases = p.phases
    columns = [*phases[: phases.index("Monitoring") + 1], revalidation.REVALIDATION_COLUMN,
               *phases[phases.index("Monitoring") + 1:]] if "Monitoring" in phases else phases
    business_lines = sorted(set(db.scalars(select(Model.business_line))))
    users = [{"user_id": u.user_id, "full_name": u.full_name, "roles": u.role_names, "active": u.active}
             for u in user_service.list_users(db)]
    return ModelMetaOut(
        model_types=p.list("model_types"), lifecycle_phases=phases, displayed_columns=columns,
        revalidation_frequencies=list(p.frequency_months),
        revalidation_statuses=[revalidation.OVERDUE, revalidation.DUE_SOON, revalidation.SCHEDULED],
        tiers=list(tiering.TIERS), business_lines=business_lines,
        validation_types=p.list("validation_types"), validation_outcomes=p.list("validation_outcomes"),
        finding_severities=p.list("finding_severities"), finding_categories=p.list("finding_categories"),
        finding_statuses=p.list("finding_statuses"), finding_open_statuses=p.list("finding_open_statuses"),
        approval_forums=p.list("approval_forums"), approval_decision_types=p.list("approval_decision_types"),
        approval_decisions=p.list("approval_decisions"), relationship_types=list(model_rules.RELATIONSHIP_TYPES),
        tiering_questions=tiering.TIERING_QUESTION_TEXT, users=users,
    )


@router.post("/tier-preview", response_model=TierPreviewOut)
def tier_preview(body: TieringAnswers, db: DbSession, _: CurrentPrincipal):
    """Live tier preview for the model form. The calculation stays on the server (R1)."""
    return model_service.tier_preview(Policy.load(db), body.model_dump())


@router.post("", response_model=ModelOut, status_code=status.HTTP_201_CREATED)
def create_model(body: ModelCreate, db: DbSession, principal: CurrentPrincipal):
    data = body.model_dump(exclude={"reason"})
    return model_service.create_model(db, principal, data, reason=body.reason)


@router.get("/{model_id}", response_model=Model360Out)
def get_model_360(model_id: str, db: DbSession, _: CurrentPrincipal):
    policy = Policy.load(db)
    model = model_service.get_model(db, model_id)
    state = governance_view.model_state(db, model)
    relationships = model_service.relationships_for(db, model_id)
    for r in relationships:
        other = db.get(Model, r["model_id"])
        r["model_name"] = other.model_name if other else None
    validations = validation_service.list_validations(db, model_id)
    findings = finding_service.list_findings(db, model_id=model_id)
    approvals = approval_service.list_approvals(db, model_id)
    user_ids = {model.owner_id, model.developer_id, model.validator_id, *(v.validator_id for v in validations),
                *(f.owner_id for f in findings)}
    names = {u.user_id: u.full_name for u in db.scalars(select(AppUser).where(AppUser.user_id.in_(user_ids - {None})))}
    return Model360Out(
        model=ModelOut.model_validate(model), state=_state_out(state), score=_score_out(state),
        phase_history=list(db.scalars(select(ModelPhaseHistory).where(ModelPhaseHistory.model_id == model_id)
                                      .order_by(ModelPhaseHistory.changed_at.desc(),
                                                ModelPhaseHistory.transition_id.desc()))),
        tier_overrides=list(db.scalars(select(TierOverride).where(TierOverride.model_id == model_id)
                                       .order_by(TierOverride.override_id.desc()))),
        versions=list(db.scalars(select(ModelVersion).where(ModelVersion.model_id == model_id)
                                 .order_by(ModelVersion.recorded_at.desc()))),
        relationships=[RelationshipOut(**r) for r in relationships],
        validations=validations, findings=[finding_out(f, policy) for f in findings], approvals=approvals,
        user_names=names,
    )


@router.put("/{model_id}", response_model=ModelOut)
def update_model(model_id: str, body: ModelUpdate, db: DbSession, principal: CurrentPrincipal):
    data = body.model_dump(exclude={"row_version", "reason"})
    return model_service.update_model(db, principal, model_id, data, body.row_version, reason=body.reason)


@router.post("/{model_id}/transition", response_model=ModelOut)
def transition(model_id: str, body: TransitionRequest, db: DbSession, principal: CurrentPrincipal):
    return model_service.transition_phase(db, principal, model_id, body.to_phase, body.reason, body.row_version)


@router.post("/{model_id}/tier-override", response_model=ModelOut)
def tier_override(model_id: str, body: TierOverrideRequest, db: DbSession, principal: CurrentPrincipal):
    return model_service.override_tier(db, principal, model_id, body.tier, body.reason, body.row_version)


@router.post("/{model_id}/relationships", response_model=list[RelationshipOut], status_code=status.HTTP_201_CREATED)
def add_relationship(model_id: str, body: RelationshipCreate, db: DbSession, principal: CurrentPrincipal):
    model_service.add_relationship(db, principal, model_id, body.related_model_id, body.relationship_type)
    return [RelationshipOut(**r) for r in model_service.relationships_for(db, model_id)]
