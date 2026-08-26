from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ImportLog
from app.schemas import (
    AdminGenerateRequest,
    AdminMaintenanceResult,
    ConceptDifficultyAnchorRead,
    CareerRequirementRead,
    DashboardSummary,
    ExternalQuestionObservationRead,
    ExternalSourceRead,
    ImportLogRead,
    QuestionAuditIssue,
    SectionSummary,
    ResearchSummary,
)
from app.services.quality_service import (
    audit_questions,
    build_dashboard_summary,
    dedupe_questions,
    generate_questions,
    list_career_requirements,
    recalibrate_difficulties,
    rebalance_question_bank,
)
from app.services.research_service import (
    approve_anchor,
    build_research_summary,
    discover_sources,
    harvest_source,
    list_concept_anchors,
    list_external_observations,
    list_external_sources,
    match_observations,
    recalibrate_from_external_observations,
    reject_anchor,
)


router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/import-status", response_model=list[ImportLogRead])
def import_status(db: Session = Depends(get_db)) -> list[ImportLogRead]:
    logs = list(db.scalars(select(ImportLog).order_by(ImportLog.created_at.desc()).limit(25)).all())
    return [ImportLogRead.model_validate(log) for log in logs]


@router.get("/question-audit", response_model=list[QuestionAuditIssue])
def question_audit(db: Session = Depends(get_db)) -> list[QuestionAuditIssue]:
    return audit_questions(db)


@router.get("/section-summary", response_model=list[SectionSummary])
def section_summary(db: Session = Depends(get_db)) -> list[SectionSummary]:
    return build_dashboard_summary(db).by_section


@router.get("/summary", response_model=DashboardSummary)
def summary(db: Session = Depends(get_db)) -> DashboardSummary:
    return build_dashboard_summary(db)


@router.post("/dedupe", response_model=AdminMaintenanceResult)
def dedupe(db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return dedupe_questions(db)


@router.post("/recalibrate", response_model=AdminMaintenanceResult)
def recalibrate(db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return recalibrate_difficulties(db)


@router.post("/rebalance", response_model=AdminMaintenanceResult)
def rebalance(db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return rebalance_question_bank(db)


@router.post("/generate", response_model=AdminMaintenanceResult)
def generate(payload: AdminGenerateRequest, db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return generate_questions(db, payload)


@router.get("/career-requirements", response_model=list[CareerRequirementRead])
def career_requirements(db: Session = Depends(get_db)) -> list[CareerRequirementRead]:
    return list_career_requirements(db)


@router.get("/research-summary", response_model=ResearchSummary)
def research_summary(db: Session = Depends(get_db)) -> ResearchSummary:
    return build_research_summary(db)


@router.get("/external-sources", response_model=list[ExternalSourceRead])
def external_sources(db: Session = Depends(get_db)) -> list[ExternalSourceRead]:
    return list_external_sources(db)


@router.get("/external-observations", response_model=list[ExternalQuestionObservationRead])
def external_observations(limit: int = 200, db: Session = Depends(get_db)) -> list[ExternalQuestionObservationRead]:
    return list_external_observations(db, limit=limit)


@router.get("/concept-anchors", response_model=list[ConceptDifficultyAnchorRead])
def concept_anchors(limit: int = 200, db: Session = Depends(get_db)) -> list[ConceptDifficultyAnchorRead]:
    return list_concept_anchors(db, limit=limit)


@router.post("/research/discover", response_model=AdminMaintenanceResult)
def research_discover(db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return discover_sources(db)


@router.post("/research/harvest", response_model=AdminMaintenanceResult)
def research_harvest(source: str, limit: int = 100, db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return harvest_source(db, source_key=source, limit=limit)


@router.post("/research/match", response_model=AdminMaintenanceResult)
def research_match(db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return match_observations(db)


@router.post("/research/recalibrate", response_model=AdminMaintenanceResult)
def research_recalibrate(db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return recalibrate_from_external_observations(db)


@router.post("/research/anchors/{anchor_id}/approve", response_model=AdminMaintenanceResult)
def research_approve_anchor(anchor_id: str, db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return approve_anchor(db, anchor_id)


@router.post("/research/anchors/{anchor_id}/reject", response_model=AdminMaintenanceResult)
def research_reject_anchor(anchor_id: str, db: Session = Depends(get_db)) -> AdminMaintenanceResult:
    return reject_anchor(db, anchor_id)
