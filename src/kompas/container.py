"""Dependency-injection container wiring the application from :class:`Settings`."""

from __future__ import annotations

from dataclasses import dataclass

from kompas.assistant.embeddings import EmbeddingModel, embedding_registry
from kompas.assistant.guardrails import guardrail_registry
from kompas.assistant.knowledge import KnowledgeBaseBuilder, KnowledgeChunk, load_index
from kompas.assistant.llm import LLMClient, llm_registry
from kompas.assistant.retriever import Retriever, retriever_registry
from kompas.assistant.service import AssistantService, load_prompts
from kompas.competency.criteria import CriteriaPolicy, FormSelector, load_forms
from kompas.competency.loader import YamlCompetencyModelLoader
from kompas.core.config import Settings, get_settings
from kompas.core.logging import configure_logging
from kompas.documents.renderer import DocumentRenderer, renderer_registry
from kompas.domain.competency import CompetencyModel
from kompas.domain.enums import DocumentFormat, EvaluationType
from kompas.domain.evaluation import Evaluation
from kompas.domain.people import Employee, User
from kompas.integrations.ezd import ArchiveGateway, archive_registry
from kompas.integrations.hr import HRGateway, hr_registry
from kompas.notifications.notifier import Notifier, notifier_registry
from kompas.notifications.reminders import ReminderService
from kompas.persistence.repository import Repository, repository_registry
from kompas.scoring.aggregation import IndicatorAggregationStrategy, aggregation_registry
from kompas.scoring.policies import OutcomePolicy, policy_registry
from kompas.scoring.scales import RatingScales, load_scales
from kompas.security.auth import AuthService, PasswordHasher, TokenService
from kompas.services.evaluation import EvaluationService
from kompas.services.job_analysis import JobAnalysisService
from kompas.services.monitoring import MonitoringService
from kompas.workflow.definitions import load_paths
from kompas.workflow.engine import WorkflowEngine


@dataclass
class AppContainer:
    """Holds all wired singletons for the running process."""

    settings: Settings
    competency_model: CompetencyModel
    criteria_policy: CriteriaPolicy
    scales: RatingScales
    workflow: WorkflowEngine
    employees: Repository[Employee]
    users: Repository[User]
    evaluations_repo: Repository[Evaluation]
    auth: AuthService
    evaluation_service: EvaluationService
    assistant: AssistantService
    monitoring: MonitoringService
    job_analysis: JobAnalysisService
    notifier: Notifier
    hr_gateway: HRGateway
    archive: ArchiveGateway


def _load_knowledge_chunks(settings: Settings, model: CompetencyModel) -> list[KnowledgeChunk]:
    index_path = settings.assistant.index_file
    if index_path is not None and index_path.is_file():
        chunks = load_index(index_path)
        if chunks:
            return chunks
    builder = KnowledgeBaseBuilder(
        chunk_size=settings.assistant.chunk_size,
        overlap=settings.assistant.chunk_overlap,
    )
    return builder.build(
        kb_dir=settings.assistant.knowledge_base_dir,
        faq_file=settings.assistant.faq_file,
        model=model,
    )


def build_container(settings: Settings | None = None) -> AppContainer:
    cfg = settings or get_settings()
    configure_logging(cfg.app.debug)

    # 1. Domain definitions from YAML
    model = YamlCompetencyModelLoader(cfg.paths.competency_model_file).load()
    forms = load_forms(cfg.paths.forms_file)
    criteria_policy = CriteriaPolicy(forms, model)
    scales, policy_configs = load_scales(cfg.paths.scoring_file)
    paths = load_paths(cfg.paths.workflows_file)
    workflow = WorkflowEngine(paths)

    # 2. Persistence + seed data
    repo_factory = repository_registry.create(cfg.repository.provider, cfg.repository.params)
    employees_repo = repo_factory.create(Employee, "employees")
    users_repo = repo_factory.create(User, "users")
    evaluations_repo = repo_factory.create(Evaluation, "evaluations")

    hr_gateway = hr_registry.create(cfg.hr_system.provider, cfg.hr_system.params)
    for emp in hr_gateway.fetch_employees():
        if employees_repo.find(emp.id) is None:
            employees_repo.add(emp)

    # 3. Security
    hasher = PasswordHasher(iterations=cfg.security.password_hash_iterations)
    tokens = TokenService(
        secret=cfg.security.jwt_secret.get_secret_value(),
        algorithm=cfg.security.jwt_algorithm,
        ttl_minutes=cfg.security.token_ttl_minutes,
    )
    auth = AuthService(users_repo, hasher, tokens)
    if cfg.security.seed_users_file is not None:
        auth.seed_from_yaml(cfg.security.seed_users_file)

    # 4. Scoring & Documents & Integrations & Notifications
    aggregator: IndicatorAggregationStrategy = aggregation_registry.create(
        cfg.scoring.indicator_aggregation.provider,
        cfg.scoring.indicator_aggregation.params,
    )
    policies: dict[EvaluationType, OutcomePolicy] = {
        EvaluationType(name): policy_registry.create(p["provider"], p.get("params"), scales=scales)
        for name, p in policy_configs.items()
    }
    renderers: dict[DocumentFormat, DocumentRenderer] = {
        DocumentFormat.PDF: renderer_registry.create("pdf", cfg.documents.params),
        DocumentFormat.HTML: renderer_registry.create("html"),
    }
    archive = archive_registry.create(cfg.archive.provider, cfg.archive.params)
    notifier = notifier_registry.create(cfg.notifications.provider, cfg.notifications.params)

    # 5. AI Assistant
    embeddings: EmbeddingModel = embedding_registry.create(cfg.embeddings.provider, cfg.embeddings.params)
    retriever: Retriever = retriever_registry.create(
        cfg.retriever.provider,
        cfg.retriever.params,
        embeddings=embeddings,
    )
    llm: LLMClient = llm_registry.create(cfg.llm.provider, cfg.llm.params)
    prompts = load_prompts(cfg.paths.prompts_file)
    guardrails = [guardrail_registry.create(name) for name in cfg.assistant.guardrails]
    chunks = _load_knowledge_chunks(cfg, model)
    assistant = AssistantService(
        retriever=retriever,
        llm=llm,
        prompts=prompts,
        guardrails=guardrails,
        chunks=chunks,
        top_k=cfg.assistant.top_k,
        min_relevance=cfg.assistant.min_relevance,
        max_context_chars=cfg.assistant.max_context_chars,
    )

    # 6. Application Services
    evaluation_service = EvaluationService(
        evaluations=evaluations_repo,
        employees=employees_repo,
        users=users_repo,
        model=model,
        criteria_policy=criteria_policy,
        form_selector=FormSelector(),
        scales=scales,
        aggregator=aggregator,
        policies=policies,
        workflow=workflow,
        renderers=renderers,
        archive=archive,
        office_name=cfg.app.office_name,
    )
    reminders = ReminderService(
        evaluations=evaluations_repo,
        users=users_repo,
        notifier=notifier,
        lead_days=cfg.notifications.reminder_lead_days,
    )
    monitoring = MonitoringService(evaluations=evaluations_repo, reminders=reminders)
    job_analysis = JobAnalysisService(model=model, criteria_policy=criteria_policy)

    return AppContainer(
        settings=cfg,
        competency_model=model,
        criteria_policy=criteria_policy,
        scales=scales,
        workflow=workflow,
        employees=employees_repo,
        users=users_repo,
        evaluations_repo=evaluations_repo,
        auth=auth,
        evaluation_service=evaluation_service,
        assistant=assistant,
        monitoring=monitoring,
        job_analysis=job_analysis,
        notifier=notifier,
        hr_gateway=hr_gateway,
        archive=archive,
    )
