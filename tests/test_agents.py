from agents.assessment.service import AssessmentAgent, AssessmentQuestionError
from agents.assessment.resume_parser import ResumeParseError, ResumeParsingAgent
from agents.data.service import DataAgent
from agents.evolution.service import EvolutionAgent
from agents.job_graph.service import JobGraphAgent
from agents.llm import LLMResult, OpenAICompatibleClient
from agents.match.service import MatchAgent
from contracts import AssessmentAnswer, GameResultInput, ImportRequest
from core.sample_data import DEMO_RESUME, generate_demo_jds


def test_resume_parsing_agent_extracts_skills_projects_and_evidence(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)
    resume = """
    候选人：李雷。五年后端和 AI 应用开发经验，本科。
    技术栈：Python、FastAPI、RAG、LangGraph、Redis、Docker、Kubernetes。
    项目：企业知识库 Agent 平台。我负责 RAG 检索链路、工具调用编排和服务部署，
    将回答命中率提升 18%，接口延迟降低到 230ms。
    期望城市：杭州，期望薪资 25K-35K。
    """

    result = ResumeParsingAgent().parse(resume, candidate_id="candidate_parse")

    skill_names = {skill["name"] for skill in result["skills"]}
    assert {"Python", "FastAPI", "RAG", "LangGraph", "Redis", "Docker", "Kubernetes"} <= skill_names
    assert result["experience_years"] == 5
    assert result["education"] == "本科"
    assert result["projects"]
    assert result["quality_summary"]["has_quantified_metrics"] is True
    assert all(item["content"] for item in result["evidence"])


def test_resume_parser_keeps_project_boundaries_precise(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)
    resume = """
    候选人：张宁
    技能：Python、FastAPI、RAG、LangGraph、Redis、Docker、Kubernetes。
    项目：企业知识库 Agent 平台。我负责 RAG 检索链路、工具调用编排和服务部署，
    将回答命中率提升 18%，接口延迟降低到 230ms。
    """

    result = ResumeParsingAgent().parse(resume, candidate_id="candidate_precise")
    project_names = {project["name"] for project in result["projects"]}

    assert "企业知识库 Agent 平台" in project_names
    assert "工具调用编排和服务" not in project_names


def test_resume_parser_does_not_guess_projects_from_responsibility_sentences(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)
    resume = """
    候选人：周岚。本科，三年 AI 应用开发经验。
    工作经历：负责 RAG 检索链路、工具调用编排和服务部署，参与接口性能优化。
    技能：Python、FastAPI、RAG、LangGraph、Docker。
    """

    result = ResumeParsingAgent().parse(resume, candidate_id="candidate_no_project_guess")

    assert result["projects"] == []
    assert result["quality_summary"]["project_count"] == 0


def test_resume_parser_strict_mode_rejects_remote_fallback():
    class FailingLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(data=kwargs["fallback"], provider_status={"fallback": True, "reason": "timeout"})

    try:
        ResumeParsingAgent(llm=FailingLLM()).parse("技能：Python、FastAPI。项目：知识库平台。", require_remote=True)
    except ResumeParseError as exc:
        assert "重新解析" in str(exc)
    else:
        raise AssertionError("strict resume parsing should reject remote fallback")


def test_resume_parser_can_skip_remote_model_for_fast_file_uploads():
    class UnexpectedLLM:
        configured = True

        def generate_json(self, **kwargs):
            raise AssertionError("file upload parsing should not call the remote model when use_remote is false")

    result = ResumeParsingAgent(llm=UnexpectedLLM()).parse(
        "技能栏：Python、FastAPI。项目：企业知识库 Agent 平台。",
        use_remote=False,
    )

    assert {skill["name"] for skill in result["skills"]} >= {"Python", "FastAPI"}
    assert result["provider_status"]["mode"] == "deterministic_fallback"


def test_resume_parser_extracts_dashboard_fields_skill_evidence_and_usage(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)
    resume = """
    Objective: AI Agent Engineer
    City: Remote
    Skills: Python, FastAPI, Redis
    Projects:
    Project: Retail Agent platform. I used Python and FastAPI to build APIs and reduced latency by 30%.
    Certificate: AWS
    Experience: 3 years
    Education: Bachelor
    """

    result = ResumeParsingAgent().parse(resume, use_remote=False)

    python_skill = next(skill for skill in result["skills"] if skill["name"] == "Python")
    assert result["job_intent"] == "AI Agent Engineer"
    assert result["certification_count"] == 1
    assert result["city_preferences"] == ["Remote"]
    assert python_skill["usage_status"] == "project_used"
    assert python_skill["occurrences"][0]["snippet"]
    assert result["semantic_profile"]["status"] == "structured_only"


def test_resume_parser_cleans_job_intent_from_mixed_resume_line(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)
    resume = """
    求职意向：AI Agent 工程师 | 杭州 | 25-35K | 全职
    技能：Python、RAG、FastAPI
    项目：企业知识库 Agent 平台。负责检索链路和接口开发。
    """

    result = ResumeParsingAgent().parse(resume, use_remote=False)

    assert result["job_intent"] == "AI Agent 工程师"
    assert result["city_preferences"] == ["杭州"]
    assert result["expected_salary_k"] == [25, 35]


def test_resume_parser_keeps_c_language_distinct_from_cpp():
    result = ResumeParsingAgent().parse(
        "专业技能：C语言、Python。使用C语言完成课程设计。",
        use_remote=False,
    )

    skill_names = {skill["name"] for skill in result["skills"]}
    assert "C" in skill_names
    assert "C++" not in skill_names


def test_assessment_fast_start_creates_session_without_waiting_for_question_llm():
    class UnexpectedQuestionLLM:
        configured = True

        def generate_json(self, **kwargs):
            raise AssertionError("fast start must not block on question generation")

    parsed = ResumeParsingAgent(llm=UnexpectedQuestionLLM()).parse(
        "技能栏：Python、FastAPI。负责数据处理接口开发。",
        use_remote=False,
    )
    session = AssessmentAgent(llm=UnexpectedQuestionLLM()).start(
        "candidate_fast_start",
        "job_ai_agent",
        "技能栏：Python、FastAPI。负责数据处理接口开发。",
        resume_parse=parsed,
        require_ai_questions=True,
        fast_start=True,
    )

    assert session.next_action is not None
    assert session.next_action.content
    assert session.provider_status["question"]["mode"] == "evidence_grounded_fast_start"


def test_resume_parser_uses_llm_entities_to_enrich_structured_result():
    class FocusedLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(
                data={
                    "skills": [
                        {
                            "name": "Python",
                            "level": "intermediate",
                            "evidence": "使用 Python 完成数据处理脚本",
                            "confidence": 0.86,
                        }
                    ],
                    "projects": [],
                    "experience_years": 2,
                    "education": "本科",
                    "certifications": [],
                    "preferred_locations": [],
                    "expected_salary_k": [],
                    "work_history": [],
                },
                provider_status={"fallback": False, "provider": "fake"},
            )

    resume = "本科，两年开发经验。技能栏：Python、FastAPI、Redis。使用 Python 完成数据处理脚本。"

    result = ResumeParsingAgent(llm=FocusedLLM()).parse(resume, require_remote=True)

    assert {skill["name"] for skill in result["skills"]} >= {"Python", "FastAPI", "Redis"}
    assert next(skill for skill in result["skills"] if skill["name"] == "Python")["usage_status"] in {"work_used", "listed_only"}
    assert result["semantic_profile"]["status"] in {"structured_only", "llm_enriched"}
    assert result["provider_status"]["mode"] == "llm_resume_understanding"


def test_llm_json_parser_extracts_object_from_wrapped_content():
    client = OpenAICompatibleClient()
    parsed = client._parse_json('noise before\n```json\n{"skills": [], "projects": []}\n```\nnoise after')

    assert parsed == {"skills": [], "projects": []}


def test_resume_parser_retries_once_after_invalid_json(monkeypatch):
    monkeypatch.setenv("TALENTGRAPH_RESUME_LLM_MAX_TOKENS", "2200")
    monkeypatch.setenv("TALENTGRAPH_RESUME_LLM_REPAIR_MAX_TOKENS", "3200")

    class JsonRetryLLM:
        configured = True

        def __init__(self):
            self.calls = []

        def generate_json(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                return LLMResult(
                    data=kwargs["fallback"],
                    provider_status={
                        "fallback": True,
                        "provider": "fake",
                        "reason": "JSONDecodeError: Unterminated string starting at: line 151 column 15",
                        "duration_ms": 11,
                    },
                )
            return LLMResult(
                data={
                    "skills": [{"name": "Python", "level": "intermediate", "evidence": "Skills: Python", "confidence": 0.88}],
                    "projects": [{"name": "Retail Agent", "role": "developer", "tech_stack": ["Python"], "metrics": [], "evidence": "Project: Retail Agent", "verification_status": "supported"}],
                    "experience_years": 3,
                    "education": "Bachelor",
                    "certifications": [],
                    "preferred_locations": [],
                    "expected_salary_k": [],
                    "work_history": [],
                },
                provider_status={"fallback": False, "provider": "fake", "duration_ms": 17},
            )

    llm = JsonRetryLLM()
    parser = ResumeParsingAgent(llm=llm)
    result = parser.parse(
        "Skills: Python\nProject: Retail Agent\nExperience: 3 years\nEducation: Bachelor",
        require_remote=True,
    )

    assert len(llm.calls) == 2
    assert llm.calls[0]["max_tokens"] == 2200
    assert llm.calls[1]["max_tokens"] == 3200
    assert result["provider_status"]["json_repair_retry"] is True
    assert result["provider_status"]["mode"] == "llm_resume_understanding"


def test_resume_parser_caches_same_resume_by_text_and_source():
    class CountingLLM:
        configured = True

        def __init__(self):
            self.calls = 0

        def generate_json(self, **kwargs):
            self.calls += 1
            return LLMResult(
                data={
                    "skills": [{"name": "Python", "level": "intermediate", "evidence": "Skills: Python", "confidence": 0.88}],
                    "projects": [{"name": "Retail Agent", "role": "developer", "tech_stack": ["Python"], "metrics": [], "evidence": "Project: Retail Agent", "verification_status": "supported"}],
                    "experience_years": 3,
                    "education": "Bachelor",
                    "certifications": [],
                    "preferred_locations": [],
                    "expected_salary_k": [],
                    "work_history": [],
                },
                provider_status={"fallback": False, "provider": "fake", "duration_ms": 123},
            )

    llm = CountingLLM()
    parser = ResumeParsingAgent(llm=llm)
    resume = "Skills: Python\nProject: Retail Agent\nExperience: 3 years\nEducation: Bachelor"

    first = parser.parse(resume, candidate_id="candidate_a", source_name="resume.docx", require_remote=True)
    second = parser.parse(resume, candidate_id="candidate_b", source_name="resume.docx", require_remote=True)

    assert llm.calls == 1
    assert first["provider_status"]["cache_hit"] is False
    assert second["provider_status"]["cache_hit"] is True
    assert second["candidate_id"] == "candidate_b"


def test_resume_compaction_preserves_high_value_sections():
    parser = ResumeParsingAgent()
    filler = "\n".join(f"irrelevant hobby line {index}" for index in range(500))
    resume = f"""
    Candidate: Alice
    Skills: Python, FastAPI, Redis
    Project: Retail Agent platform, reduced latency by 30%.
    Experience: 3 years backend work.
    Education: Bachelor of Computer Science.
    Certificate: Cloud engineer.
    {filler}
    """

    compact, stats = parser._compact_resume_for_llm(resume, limit=4200)

    assert stats["compact_input_chars"] <= 4200
    assert "Python" in compact
    assert "Retail Agent" in compact
    assert "3 years" in compact
    assert "Bachelor" in compact


def test_resume_parser_sends_compact_summary_payload_to_llm(monkeypatch):
    monkeypatch.setenv("TALENTGRAPH_RESUME_LLM_INPUT_CHARS", "3000")
    monkeypatch.setenv("TALENTGRAPH_RESUME_LLM_MAX_TOKENS", "1600")

    class PromptCaptureLLM:
        configured = True

        def __init__(self):
            self.kwargs = None

        def generate_json(self, **kwargs):
            self.kwargs = kwargs
            return LLMResult(
                data={
                    "skills": [{"name": "Python", "level": "intermediate", "evidence": "Skills: Python", "confidence": 0.88}],
                    "projects": [{"name": "Retail Agent", "role": "developer", "tech_stack": ["Python"], "metrics": ["30%"], "evidence": "Project: Retail Agent", "verification_status": "supported"}],
                    "experience_years": 3,
                    "education": "Bachelor",
                    "certifications": [],
                    "preferred_locations": [],
                    "expected_salary_k": [],
                    "work_history": [],
                },
                provider_status={"fallback": False, "provider": "fake", "duration_ms": 8},
            )

    llm = PromptCaptureLLM()
    filler = "\n".join(f"LOW_VALUE_{index}" for index in range(500))
    resume = f"Skills: Python\nProject: Retail Agent, reduced latency by 30%.\nExperience: 3 years\nEducation: Bachelor\n{filler}"

    result = ResumeParsingAgent(llm=llm).parse(resume, require_remote=True)
    prompt = llm.kwargs["user_prompt"]

    assert '"deterministic_hints"' in prompt
    assert '"resume_snippets"' in prompt
    assert "LOW_VALUE_499" not in prompt
    assert len(prompt) < 4200
    assert llm.kwargs["max_tokens"] == 1600
    assert result["provider_status"]["prompt_mode"] == "compact_resume_summary"


def test_assessment_first_question_uses_structured_summary_not_long_resume():
    class PromptCaptureLLM:
        configured = True

        def __init__(self):
            self.kwargs = None

        def generate_json(self, **kwargs):
            self.kwargs = kwargs
            return LLMResult(
                data={"content": "For your Python Retail Agent project, what latency signal did you verify first?", "focus": ["Python"]},
                provider_status={"fallback": False, "provider": "fake", "duration_ms": 9},
            )

    llm = PromptCaptureLLM()
    long_resume = "Skills: Python\n" + ("SHOULD_NOT_APPEAR " * 500)
    parsed = {
        "skills": [{"name": "Python", "evidence": "Skills: Python"}],
        "projects": [{"name": "Retail Agent", "evidence": "Project: Retail Agent"}],
        "evidence": [],
    }

    session = AssessmentAgent(llm=llm).start(
        "candidate_prompt_mode",
        "job_ai_agent",
        long_resume,
        resume_parse=parsed,
        require_ai_questions=True,
    )
    prompt = llm.kwargs["user_prompt"]

    assert "resume_summary" in prompt
    assert "resume_excerpt" not in prompt
    assert "SHOULD_NOT_APPEAR" not in prompt
    assert llm.kwargs["max_tokens"] == 220
    assert llm.kwargs["disable_thinking"] is True
    assert session.provider_status["dialogue_question_ms"] == 9


def test_resume_parser_extracts_skill_tags_from_skill_section(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)
    resume = """
    候选人：赵一
    专业技能：Python、FastAPI、Nacos、Sentinel、ClickHouse、PyTorch、OCR、设备影子、边缘计算
    工作经历：负责 AI 平台接口服务和可观测性建设。
    """

    result = ResumeParsingAgent().parse(resume)
    skill_names = {skill["name"] for skill in result["skills"]}

    assert {"Python", "FastAPI", "Nacos", "Sentinel", "ClickHouse", "PyTorch", "OCR", "Device Shadow", "Edge Computing"} <= skill_names
    assert "设备影子" not in skill_names
    assert "边缘计算" not in skill_names


def test_resume_parser_extracts_normal_chinese_resume_fields(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)
    resume = """
    候选人：李雷。五年后端和 AI 应用开发经验，本科。
    技能栏：Python、FastAPI、RAG、LangGraph、Redis、Docker、Kubernetes、向量数据库。
    项目：企业知识库 Agent 平台。本人负责 RAG 检索链路、工具调用编排和服务部署，
    将回答命中率提升 18%，接口延迟降低到 230ms。
    期望城市：杭州，期望薪资 25-35K。
    """

    result = ResumeParsingAgent().parse(resume, candidate_id="candidate_chinese")

    skill_names = {skill["name"] for skill in result["skills"]}
    assert {"Python", "FastAPI", "RAG", "LangGraph", "Redis", "Docker", "Kubernetes", "Vector Database"} <= skill_names
    assert result["experience_years"] == 5
    assert result["education"] == "本科"
    assert result["expected_salary_k"] == [25, 35]
    assert result["preferred_locations"] == ["杭州"]
    assert {project["name"] for project in result["projects"]} == {"企业知识库 Agent 平台"}


def test_assessment_start_persists_structured_resume_parse(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)
    resume = "三年 Java 后端经验，本科。参与订单系统，负责 Spring Boot、MySQL、Redis 和 RabbitMQ 链路优化。"

    session = AssessmentAgent().start("candidate_structured", "java_backend", resume)

    parsed = session.candidate_profile["resume_parse"]
    assert parsed["quality_summary"]["skill_count"] >= 4
    assert session.evidence
    assert {skill["name"] for skill in session.candidate_profile["skills"]} >= {"Java", "Spring Boot", "MySQL", "Redis"}


def test_assessment_start_requires_real_resume_text(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)

    try:
        AssessmentAgent().start("candidate_missing_resume", "java_backend")
    except ValueError as exc:
        assert "resume_text is required" in str(exc)
    else:
        raise AssertionError("assessment start should reject missing resume_text")


def test_assessment_question_keeps_one_core_question():
    class MultiPointLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(data={"content": "这个指标是什么，你做了哪些优化动作？", "focus": ["职责"]}, provider_status={"fallback": False})

    session = AssessmentAgent(llm=MultiPointLLM()).start(
        "candidate_one_question",
        "job_ai_agent",
        "技能：Python、RAG。项目：企业知识库 Agent 平台。",
        resume_parse={
            "skills": [{"name": "Python"}, {"name": "RAG"}],
            "projects": [{"name": "企业知识库 Agent 平台"}],
            "evidence": [],
        },
    )

    assert session.next_action.content == "你做了哪些优化动作？"
    assert session.next_action.content.count("？") == 1


def test_assessment_normalizes_model_focus_for_dialogue_ui():
    class LooseShapeLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(
                data={"content": "你负责的关键技术决策是什么？", "focus": {"skill": "技术决策", "topic": "量化结果"}},
                provider_status={"fallback": False},
            )

    session = AssessmentAgent(llm=LooseShapeLLM()).start(
        "candidate_focus_shape",
        "job_ai_agent",
        "技能：Python、RAG。项目：企业知识库 Agent 平台。",
        resume_parse={
            "skills": [{"name": "Python"}, {"name": "RAG"}],
            "projects": [{"name": "企业知识库 Agent 平台"}],
            "evidence": [],
        },
    )

    assert session.next_action.metadata["focus"] == ["技术决策", "量化结果"]


def test_assessment_dialogue_asks_skill_tags_then_stops():
    class FallbackLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(data=kwargs["fallback"], provider_status={"fallback": True})

    assessment = AssessmentAgent(llm=FallbackLLM())
    session = assessment.start(
        "candidate_skill_dialogue",
        "job_ai_agent",
        "技能：Word长文档排版、Python、RAG。",
        resume_parse={
            "skills": [{"name": "Word长文档排版"}, {"name": "Python"}, {"name": "RAG"}],
            "projects": [],
            "evidence": [],
        },
    )

    assert session.next_action.metadata["skill"] == "Python"
    assert session.next_action.metadata["technical"] is True
    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="我用 Python 处理数据清洗和接口开发。"))
    assert session.next_action.metadata["skill"] == "RAG"
    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="我负责检索召回和答案评测。"))
    assert session.next_action.metadata["skill"] == "Word长文档排版"
    assert session.next_action.metadata["technical"] is False
    assert "真实熟练度" not in session.next_action.content
    assert "交付成果" not in session.next_action.content
    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="我维护过百页交付文档模板和目录样式。"))

    assert session.current_stage == "interactive_game"
    assert session.next_action.type == "interactive_game"


def test_assessment_strict_dialogue_rejects_template_fallback():
    class FallbackLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(data=kwargs["fallback"], provider_status={"fallback": True, "reason": "timeout"})

    try:
        AssessmentAgent(llm=FallbackLLM()).start(
            "candidate_strict_dialogue",
            "job_ai_agent",
            "技能：Python、RAG。项目：企业知识库 Agent 平台。",
            resume_parse={
                "skills": [{"name": "Python"}, {"name": "RAG"}],
                "projects": [{"name": "企业知识库 Agent 平台"}],
                "evidence": [],
            },
            require_ai_questions=True,
        )
    except AssessmentQuestionError as exc:
        assert "深度对话模型" in str(exc)
    else:
        raise AssertionError("strict dialogue should reject template fallback")


def test_assessment_strict_dialogue_rejects_generic_model_question():
    class GenericLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(data={"content": "你能介绍一下你最关键的项目经验吗？", "focus": ["项目经验"]}, provider_status={"fallback": False})

    try:
        AssessmentAgent(llm=GenericLLM()).start(
            "candidate_generic_dialogue",
            "job_ai_agent",
            "技能：Python、RAG。项目：企业知识库 Agent 平台。",
            resume_parse={
                "skills": [{"name": "Python"}, {"name": "RAG"}],
                "projects": [{"name": "企业知识库 Agent 平台"}],
                "evidence": [],
            },
            require_ai_questions=True,
        )
    except AssessmentQuestionError as exc:
        assert "过于通用" in str(exc)
    else:
        raise AssertionError("strict dialogue should reject generic model questions")


def test_assessment_retries_initial_question_when_cleaned_to_fallback():
    class RetryLLM:
        configured = True

        def __init__(self):
            self.calls = 0

        def generate_json(self, **kwargs):
            self.calls += 1
            if self.calls == 1:
                return LLMResult(data=kwargs["fallback"], provider_status={"fallback": False, "provider": "fake"})
            return LLMResult(
                data={
                    "content": "In your Python API project, which latency signal did you personally verify first?",
                    "focus": ["Python", "API latency"],
                },
                provider_status={"fallback": False, "provider": "fake"},
            )

    llm = RetryLLM()
    fallback_parse = {
        "skills": [{"name": "Python", "technical": True}],
        "projects": [{"name": "Python API project"}],
        "evidence": [],
    }
    session = AssessmentAgent(llm=llm).start(
        "candidate_retry_first_question",
        "job_ai_agent",
        "Python API project with latency optimization.",
        resume_parse=fallback_parse,
        require_ai_questions=True,
    )

    assert llm.calls == 2
    assert session.next_action.content.startswith("In your Python API project, which latency signal")
    assert session.provider_status["question"]["initial_question_retry"] is True


def test_assessment_fallback_questions_are_not_repetitive_generic_phrases():
    agent = AssessmentAgent()
    questions = [
        agent._skill_question_fallback({"name": "Python", "technical": True}, 1, 4)["content"],
        agent._skill_question_fallback({"name": "RAG", "technical": True}, 2, 4)["content"],
        agent._skill_question_fallback({"name": "Word长文档排版", "technical": False}, 3, 4)["content"],
        agent._skill_question_fallback({"name": "需求分析", "technical": False}, 4, 4)["content"],
    ]

    assert len(set(questions)) == len(questions)
    assert all("真实熟练度" not in question for question in questions)
    assert all("交付成果" not in question for question in questions)


def test_interactive_game_scenario_uses_resume_skills_and_project():
    class FallbackLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(data=kwargs["fallback"], provider_status={"fallback": True})

    assessment = AssessmentAgent(llm=FallbackLLM())
    session = assessment.start(
        "candidate_dynamic_game",
        "job_ai_agent",
        "技能：RAG、LangChain、Python。项目：企业知识库 Agent 平台。",
        resume_parse={
            "skills": [{"name": "RAG"}, {"name": "LangChain"}, {"name": "Python"}],
            "projects": [{"name": "企业知识库 Agent 平台"}],
            "evidence": [],
        },
    )
    while session.current_stage != "interactive_game":
        session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="我负责方案设计、评测和灰度上线。"))

    scenario = session.next_action.metadata["game_scenario"]
    assert scenario["id"] == "rag_quality_rescue"
    assert scenario["project"] == "企业知识库 Agent 平台"
    assert "RAG" in scenario["skills"]
    assert "凌晨两点十三分" not in scenario["title"]


def test_interactive_game_scenario_supports_iot_resume():
    assessment = AssessmentAgent()
    scenario = assessment._build_game_scenario(
        type("SessionLike", (), {
            "candidate_profile": {
                "skills": [{"name": "MQTT"}, {"name": "设备影子"}, {"name": "边缘计算"}],
                "projects": [{"name": "边缘设备数字孪生系统"}],
            }
        })()
    )

    assert scenario["id"] == "iot_device_shadow_recovery"
    assert scenario["project"] == "边缘设备数字孪生系统"


def test_assessment_allows_game_before_dialogue_completion():
    class FallbackLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(data=kwargs["fallback"], provider_status={"fallback": True})

    assessment = AssessmentAgent(llm=FallbackLLM())
    session = assessment.start(
        "candidate_parallel_flow",
        "job_ai_agent",
        "技能：RAG、Python。项目：企业知识库 Agent 平台。",
        resume_parse={
            "skills": [{"name": "RAG"}, {"name": "Python"}],
            "projects": [{"name": "企业知识库 Agent 平台"}],
            "evidence": [],
        },
    )
    game = session.candidate_profile["game_scenario"]
    session = assessment.game_result(
        session,
        GameResultInput(
            session_id=session.session_id,
            events=[{"type": "story_choice", "value": game["chapters"][0]["choices"][0]["id"]}],
        ),
    )

    assert session.candidate_profile["interactive_game_completed"] is True
    assert session.current_stage == "skill_deep_question"
    assert session.next_action.type == "question"

    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="我负责检索评测和灰度发布。"))
    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="我负责 Python 服务开发和指标验证。"))
    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="我用命中率和延迟指标验证上线效果。"))

    assert session.candidate_profile["dialogue_completed"] is True
    assert session.current_stage == "finalize_profile"
    assert session.next_action.type == "finish"


def test_assessment_runs_three_project_oriented_dialogue_rounds_then_scores():
    class FallbackLLM:
        configured = True

        def generate_json(self, **kwargs):
            return LLMResult(data=kwargs["fallback"], provider_status={"fallback": True})

    assessment = AssessmentAgent(llm=FallbackLLM())
    session = assessment.start(
        "candidate_multi_dialogue",
        "job_ai_agent",
        "Skills: Python, FastAPI\nProject: Retail Agent",
        resume_parse={
            "skills": [{"name": "Python"}, {"name": "FastAPI"}],
            "projects": [{"name": "Retail Agent"}],
            "evidence": [],
        },
    )

    assert session.next_action.metadata["skill_total"] == 3
    assert session.next_action.metadata["project"] == "Retail Agent"
    assert session.next_action.metadata["round_type"] == "ownership_scope"
    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="I used Python to build the service."))

    assert session.candidate_profile["dialogue_completed"] is False
    assert "skill_deep_question" not in session.completed_stages
    assert session.current_stage == "skill_deep_question"
    assert session.next_action.type == "question"
    assert session.next_action.metadata["skill_index"] == 2
    assert session.next_action.metadata["round_type"] == "technical_decision"

    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="I used FastAPI for the API layer."))

    assert session.candidate_profile["dialogue_completed"] is False
    assert session.current_stage == "skill_deep_question"
    assert session.next_action.metadata["skill_index"] == 3
    assert session.next_action.metadata["round_type"] == "result_verification"

    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="I compared latency before and after the change, then reviewed failures."))

    assert session.candidate_profile["dialogue_completed"] is True
    assert "skill_deep_question" in session.completed_stages
    assert session.candidate_profile["dialogue_score"]["rounds"] == 3
    assert session.candidate_profile["dialogue_score"]["score"] > 0
    assert session.next_action.type == "interactive_game"


def test_assessment_sanitizes_model_question_before_using_local_template():
    agent = AssessmentAgent()

    assert agent._single_core_question("1. 你用 RAG 解决过什么问题？2. 你怎么评估？", "兜底问题？") == "你用 RAG 解决过什么问题？"
    assert agent._single_core_question("这个指标是什么，你做了哪些优化动作？", "兜底问题？") == "你做了哪些优化动作？"


def test_data_agent_generates_computer_jd_gold_set():
    batch = DataAgent().run(ImportRequest(batch_name="gold", items=generate_demo_jds()))

    assert len(batch.items) == 100
    assert batch.quality_summary["computer_scope_items"] == 100
    assert batch.quality_summary["avg_quality"] >= 80


def test_empty_production_import_does_not_generate_demo_jobs():
    batch = DataAgent().run(ImportRequest(batch_name="empty"))

    assert batch.items == []
    assert batch.quality_summary["fetched"] == 0


def test_agent_chain_contracts_are_json_serializable(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)
    batch = DataAgent().run(ImportRequest(batch_name="gold", items=generate_demo_jds()))
    graph = JobGraphAgent().run(batch, "Java 后端工程师")
    evolution = EvolutionAgent().run(graph)

    assessment = AssessmentAgent()
    session = assessment.start("candidate_json", graph.job_id, DEMO_RESUME)
    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="Spring Boot Redis MySQL 微服务"))
    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="先看监控日志，再处理缓存和数据库。"))
    session = assessment.answer(session, AssessmentAnswer(session_id=session.session_id, answer="回滚高风险发布，保护核心交易链路。"))
    session = assessment.game_result(
        session,
        GameResultInput(session_id=session.session_id, events=[{"time": 1, "type": "allocate_resource", "value": "database:2"}]),
    )
    profile = assessment.finalize(session).candidate_profile
    report = MatchAgent().run(graph, profile)

    assert graph.model_dump()
    assert evolution.model_dump()
    assert profile.model_dump()
    assert report.model_dump()
    assert report.level in {"high", "medium", "low"}


def test_finalize_profile_uses_compact_llm_payload_and_timing(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)

    class ProfileLLM:
        def __init__(self):
            self.calls = []

        def generate_json(self, **kwargs):
            self.calls.append(kwargs)
            return LLMResult(
                data={
                    "code": "BUILD",
                    "title": "工程落地者",
                    "narrative": "能够围绕项目证据拆解方案、验证风险并推进交付。",
                    "traits": ["项目拆解", "证据验证"],
                },
                provider_status={"fallback": False, "duration_ms": 18},
            )

    long_marker = "THIS_FULL_RESUME_MARKER_SHOULD_NOT_APPEAR_" * 80
    assessment = AssessmentAgent()
    session = assessment.start(
        "candidate_profile_fast",
        "job_ai_agent",
        f"求职意向：AI Agent 工程师\n项目：Agent 平台，使用 Python 和 RAG。\n{long_marker}",
    )
    session.candidate_profile["behavior_signals"] = [{"dimension": "risk", "score": 82, "evidence": "优先灰度验证"}]
    session.candidate_profile["evidence"].append(
        {
            "stage": "skill_deep_question",
            "type": "answer",
            "content": "我负责 RAG 检索链路，先做召回评估，再用灰度策略降低上线风险。" + "LONG_EVIDENCE_" * 80,
            "quality_score": 0.86,
            "signals": {"measurable": True, "ownership": True},
        }
    )
    llm = ProfileLLM()
    assessment.llm = llm

    profile = assessment.finalize(session).candidate_profile

    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["timeout_seconds"] == 30.0
    assert call["retries"] == 0
    assert call["max_tokens"] == 520
    assert call["disable_thinking"] is True
    assert "THIS_FULL_RESUME_MARKER_SHOULD_NOT_APPEAR" not in call["user_prompt"]
    assert len(call["user_prompt"]) < 3500
    assert profile.profile_timing["profile_llm_ms"] == 18
    assert profile.provider_status["prompt_mode"] == "compact_profile_summary"


def test_finalize_profile_cache_reuses_session_result(monkeypatch):
    monkeypatch.delenv("TALENTGRAPH_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_API_KEY", raising=False)
    monkeypatch.delenv("TALENTGRAPH_LLM_MODEL", raising=False)

    class CountingProfileLLM:
        def __init__(self):
            self.calls = 0

        def generate_json(self, **kwargs):
            self.calls += 1
            return LLMResult(
                data={"code": "SAGE", "title": "系统构建者", "narrative": "画像已生成。", "traits": ["稳健"]},
                provider_status={"fallback": False, "duration_ms": 11},
            )

    assessment = AssessmentAgent()
    session = assessment.start("candidate_profile_cache", "job_ai_agent", DEMO_RESUME)
    llm = CountingProfileLLM()
    assessment.llm = llm

    first = assessment.finalize(session).candidate_profile
    second = assessment.finalize(session).candidate_profile

    assert llm.calls == 1
    assert first.profile_timing["cache_hit"] is False
    assert second.profile_timing["cache_hit"] is True
    assert second.provider_status["mode"] == "profile_cached"
