from __future__ import annotations

from agents.assessment.service import AssessmentAgent
from agents.data.service import DataAgent
from agents.data.collection import DataCollectionAgent
from agents.evolution.service import EvolutionAgent
from agents.emerging_jobs.service import EmergingJobAgent
from agents.job_graph.service import JobGraphAgent
from agents.job_graph.knowledge_graph import KnowledgeGraphService
from agents.match.service import MatchAgent
from agents.validation.service import ValidationAgent
from contracts import (
    AssessmentAnswer,
    CleanedDataBatch,
    DataCollectionRequest,
    EmergingJobDiscoveryRequest,
    GameResultInput,
    ImportRequest,
    JobGraphBuildRequest,
    ValidationRun,
    ValidationRunRequest,
)
from core.store import store


class Orchestrator:
    def __init__(self) -> None:
        self.data_agent = DataAgent()
        self.data_collection_agent = DataCollectionAgent(data_agent=self.data_agent, app_store=store)
        self.job_graph_agent = JobGraphAgent()
        self.knowledge_graph_service = KnowledgeGraphService()
        self.evolution_agent = EvolutionAgent()
        self.assessment_agent = AssessmentAgent()
        self.match_agent = MatchAgent()
        self.emerging_job_agent = EmergingJobAgent()
        self.validation_agent = ValidationAgent()

    def import_data(self, request: ImportRequest):
        batch = self.data_agent.run(request)
        store.batches[batch.batch_id] = batch
        return batch

    def collect_data(self, request: DataCollectionRequest):
        return self.data_collection_agent.collect(request)

    def build_graph(self, request: JobGraphBuildRequest):
        batch = store.batches.get(request.batch_id)
        if batch is None:
            raise KeyError(f"batch not found: {request.batch_id}")
        graph = self.job_graph_agent.run(batch, request.target_job_title)
        store.graphs[graph.job_id] = graph
        return graph

    def run_evolution(self, job_id: str):
        graph = store.graphs.get(job_id)
        if graph is None:
            raise KeyError(f"job graph not found: {job_id}")
        result = self.evolution_agent.run(graph)
        store.evolutions[job_id] = result
        return result

    def start_assessment(
        self,
        candidate_id: str,
        target_job_id: str,
        resume_text: str | None = None,
        resume_parse: dict | None = None,
        *,
        require_ai_questions: bool = False,
    ):
        session = self.assessment_agent.start(
            candidate_id,
            target_job_id,
            resume_text,
            resume_parse=resume_parse,
            require_ai_questions=require_ai_questions,
        )
        return store.save_session(session)

    def answer_assessment(self, payload: AssessmentAnswer):
        session = store.sessions.get(payload.session_id)
        if session is None:
            raise KeyError(f"session not found: {payload.session_id}")
        session = self.assessment_agent.answer(session, payload)
        return store.save_session(session)

    def assessment_game_result(self, payload: GameResultInput):
        session = store.sessions.get(payload.session_id)
        if session is None:
            raise KeyError(f"session not found: {payload.session_id}")
        session = self.assessment_agent.game_result(session, payload)
        return store.save_session(session)

    def finalize_assessment(self, session_id: str):
        session = store.sessions.get(session_id)
        if session is None:
            raise KeyError(f"session not found: {session_id}")
        result = self.assessment_agent.finalize(session)
        store.save_session(session)
        store.profiles[result.candidate_profile.candidate_id] = result.candidate_profile
        return result

    def match_report(self, candidate_id: str, target_job_id: str):
        graph = store.graphs.get(target_job_id)
        profile = store.profiles.get(candidate_id)
        if graph is None:
            title_map = {"job_ai_agent": "AI Agent 工程师", "ai_agent": "AI Agent 工程师"}
            target_title = title_map.get(target_job_id, target_job_id.replace("_", " "))
            source_items = list(store.jobs.values())
            if not source_items:
                raise KeyError("no verified job data available to build the match graph")
            batch = CleanedDataBatch(batch_name="match_graph_runtime", items=source_items)
            graph = self.job_graph_agent.run(batch, target_title)
            store.graphs[graph.job_id] = graph
            store.graphs[target_job_id] = graph
        if profile is None:
            raise KeyError(f"candidate profile not found: {candidate_id}")
        report = self.match_agent.run(graph, profile)
        store.reports[report.report_id] = report
        return report

    def discover_emerging_jobs(self, request: EmergingJobDiscoveryRequest):
        if request.batch_ids:
            missing = [batch_id for batch_id in request.batch_ids if batch_id not in store.batches]
            if missing:
                raise KeyError(f"batches not found: {', '.join(missing)}")
            batches = [store.batches[batch_id] for batch_id in request.batch_ids]
        else:
            batches = list(store.batches.values())
        candidates = self.emerging_job_agent.discover(
            batches,
            list(store.graphs.values()),
            request,
            store.list_jobs(),
            list(store.community_signals.values()),
        )
        return store.replace_emerging_jobs(candidates)

    def run_validation(self, request: ValidationRunRequest):
        run = store.save_validation_run(ValidationRun(status="running", stage="initializing", stage_progress=0.02))
        result = self.validation_agent.run(request, run)
        return store.save_validation_run(result)


orchestrator = Orchestrator()
