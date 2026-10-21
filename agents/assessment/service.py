from __future__ import annotations

import copy
from datetime import UTC, datetime
import json
import os
import re
from time import perf_counter
from types import SimpleNamespace

from agents.llm import OpenAICompatibleClient
from agents.assessment.resume_parser import ResumeParsingAgent
from contracts import (
    AssessmentAction,
    AssessmentAnswer,
    AssessmentFinalizeOutput,
    AssessmentSession,
    CandidateProfile,
    GameResultInput,
)


class AssessmentQuestionError(RuntimeError):
    pass


class AssessmentAgent:
    stages = ["resume_parse", "resume_probe", "skill_deep_question", "scenario_task", "interactive_game", "finalize_profile"]
    stage_labels = {
        "resume_parse": "档案解析",
        "resume_probe": "项目真实性追问",
        "skill_deep_question": "技能深挖",
        "scenario_task": "场景决策",
        "interactive_game": "互动任务",
        "finalize_profile": "能力画像",
    }

    def __init__(
        self,
        llm: OpenAICompatibleClient | None = None,
        resume_parser: ResumeParsingAgent | None = None,
        *,
        require_ai_questions: bool = False,
    ) -> None:
        self.llm = llm or OpenAICompatibleClient()
        self.resume_parser = resume_parser or ResumeParsingAgent(
            self.llm,
            resume_llm_source=os.getenv("TALENTGRAPH_RESUME_LLM_SOURCE", "main"),
        )
        self.require_ai_questions = require_ai_questions
        self.dialogue_timeout_seconds = self._env_float("TALENTGRAPH_DIALOGUE_LLM_TIMEOUT_SECONDS", 25.0)
        self.dialogue_max_tokens = self._env_int("TALENTGRAPH_DIALOGUE_LLM_MAX_TOKENS", 220)
        self.dialogue_model = os.getenv("TALENTGRAPH_DIALOGUE_LLM_MODEL", "").strip() or None
        self.profile_timeout_seconds = self._env_float("TALENTGRAPH_PROFILE_LLM_TIMEOUT_SECONDS", 30.0)
        self.profile_max_tokens = self._env_int("TALENTGRAPH_PROFILE_LLM_MAX_TOKENS", 520)
        self.profile_model = os.getenv("TALENTGRAPH_PROFILE_LLM_MODEL", "").strip() or None

    def start(
        self,
        candidate_id: str,
        target_job_id: str,
        resume_text: str | None = None,
        *,
        resume_parse: dict | None = None,
        require_ai_questions: bool | None = None,
        fast_start: bool = False,
    ) -> AssessmentSession:
        resume = (resume_text or "").strip()
        if not resume:
            raise ValueError("resume_text is required; upload and parse a real resume before starting assessment")
        strict_questions = self.require_ai_questions if require_ai_questions is None else require_ai_questions
        parsed, parse_status = self._resume_parse_or_parse(resume, resume_parse, candidate_id=candidate_id)
        skills = parsed["skills"]
        resume_evidence = parsed.get("evidence") or [
            {
                "evidence_id": "resume_parse_1",
                "stage": "resume_parse",
                "type": "resume",
                "content": resume[:500],
                "extracted_skills": [item["name"] for item in skills],
                "confidence": 0.72 if skills else 0.45,
            }
        ]
        skill_plan = self._dialogue_skill_plan(skills, parsed.get("projects", []))
        fallback = self._skill_question_fallback(skill_plan[0] if skill_plan else None, 1, len(skill_plan))
        if fast_start:
            generated = SimpleNamespace(
                data=fallback,
                provider_status={
                    "mode": "evidence_grounded_fast_start",
                    "fallback": False,
                    "duration_ms": 0,
                    "dialogue_question_ms": 0,
                },
            )
            question_content = fallback["content"]
        else:
            generated = self._question(
                "skill_deep_question",
                resume,
                [],
                fallback,
                parsed_resume=parsed,
                require_ai=strict_questions,
            )
            question_content = self._single_core_question(str(generated.data.get("content", fallback["content"])), fallback["content"])
            fallback_content = self._single_core_question(fallback["content"], fallback["content"])
            if strict_questions and self._same_question(question_content, fallback_content):
                retry_fallback = {
                    **fallback,
                    "rejected_question": fallback["content"],
                    "retry_instruction": (
                        "The previous generated first question was rejected because it cleaned back to the local fallback. "
                        "Generate one different, resume-specific, single-sentence interview question."
                    ),
                }
                retry = self._question(
                    "skill_deep_question",
                    resume,
                    [],
                    retry_fallback,
                    parsed_resume=parsed,
                    require_ai=True,
                )
                retry_content = self._single_core_question(str(retry.data.get("content", fallback["content"])), fallback["content"])
                if self._same_question(retry_content, fallback_content):
                    raise AssessmentQuestionError("initial deep-dialogue question cleaned back to fallback after retry")
                retry.provider_status["initial_question_retry"] = True
                retry.provider_status["retry_reason"] = "cleaned_to_fallback"
                generated = retry
                question_content = retry_content
        action = AssessmentAction(
            type="question",
            content=question_content,
            metadata={
                "stage": "skill_deep_question",
                "focus": self._normalize_list(generated.data.get("focus", fallback["focus"])),
                "skill": fallback.get("skill"),
                "project": fallback.get("project"),
                "round_type": fallback.get("round_type"),
                "skill_index": 1,
                "skill_total": len(skill_plan),
                "technical": fallback.get("technical", False),
            },
        )
        profile_data = {
            "skills": skills,
            "resume_text": resume,
            "resume_parse": parsed,
            "candidate_name": parsed.get("candidate_name"),
            "evidence": resume_evidence,
            "projects": parsed["projects"],
            "job_intent": parsed.get("job_intent"),
            "semantic_profile": parsed.get("semantic_profile"),
            "dialogue_skill_plan": skill_plan,
            "dialogue_round_total": len(skill_plan),
            "dialogue_score": None,
            "dialogue_skill_index": 0,
            "dialogue_completed": False,
            "require_ai_questions": strict_questions,
            "interactive_game_completed": False,
            "asked_skill_tags": [],
            "experience_years": parsed.get("experience_years"),
            "education": parsed.get("education"),
            "certifications": parsed.get("certifications", []),
            "preferred_locations": parsed.get("preferred_locations", []),
            "city_preferences": parsed.get("city_preferences", []),
            "expected_salary_k": parsed.get("expected_salary_k", []),
        }
        profile_data["game_scenario"] = self._build_game_scenario_from_profile(profile_data)
        return AssessmentSession(
            candidate_id=candidate_id,
            target_job_id=target_job_id,
            current_stage="skill_deep_question",
            stage_progress=0.2,
            completed_stages=["resume_parse"],
            evidence=resume_evidence,
            candidate_profile=profile_data,
            history=[{"role": "assistant", "stage": "skill_deep_question", "content": action.content, "skill": fallback.get("skill")}],
            next_action=action,
            provider_status={
                "resume_parse": parse_status,
                "question": generated.provider_status,
                "dialogue_question_ms": generated.provider_status.get("duration_ms"),
            },
        )

    def answer(self, session: AssessmentSession, payload: AssessmentAnswer) -> AssessmentSession:
        if session.status == "finished":
            return session
        answer = payload.answer.strip()
        stage = session.current_stage
        session.history.append({"role": "candidate", "stage": stage, "content": answer, "at": datetime.now(UTC).isoformat()})
        evidence = self._answer_evidence(stage, answer, len(session.evidence) + 1)
        session.evidence.append(evidence)
        session.candidate_profile.setdefault("evidence", []).append(evidence)

        if stage in {"resume_probe", "skill_deep_question", "scenario_task"}:
            current_skill = session.next_action.metadata.get("skill") if session.next_action else None
            if current_skill:
                session.candidate_profile.setdefault("asked_skill_tags", []).append(current_skill)
                self._append_skill(session, str(current_skill), self._level_from_score(evidence["quality_score"]), answer)
            else:
                self._append_skill(session, "深度对话能力证据", self._level_from_score(evidence["quality_score"]), answer)
            if not self._advance_to_next_skill_question(session):
                self._enter_interactive_game(session)
        else:
            session.next_action = AssessmentAction(type="finish", content="评估信息已收集，可以生成能力画像。")
        session.updated_at = datetime.now(UTC)
        return session

    def game_result(self, session: AssessmentSession, payload: GameResultInput) -> AssessmentSession:
        session.history.append({"role": "game", "stage": session.current_stage, "events": payload.events, "at": datetime.now(UTC).isoformat()})
        signals = self._game_signals(payload.events)
        session.candidate_profile.setdefault("behavior_signals", []).extend(signals)
        game_evidence = {
            "evidence_id": f"game_{len(session.evidence) + 1}",
            "stage": "interactive_game",
            "type": "behavior",
            "content": f"记录 {len(payload.events)} 个交互事件",
            "events": payload.events,
            "signals": signals,
            "confidence": min(0.92, 0.55 + len(payload.events) * 0.04),
        }
        session.evidence.append(game_evidence)
        session.candidate_profile.setdefault("evidence", []).append(game_evidence)
        session.candidate_profile["interactive_game_completed"] = True
        session.completed_stages = list(dict.fromkeys([*session.completed_stages, "interactive_game"]))
        dialogue_done = bool(session.candidate_profile.get("dialogue_completed") or "skill_deep_question" in session.completed_stages)
        if dialogue_done:
            session.current_stage = "finalize_profile"
            session.stage_progress = 1.0
            session.next_action = AssessmentAction(type="finish", content="互动任务已完成，可以生成最终画像。", metadata={"stage": "finalize_profile"})
        else:
            session.stage_progress = max(session.stage_progress, 0.55)
        session.updated_at = datetime.now(UTC)
        return session

    def finalize(self, session: AssessmentSession) -> AssessmentFinalizeOutput:
        profile = session.candidate_profile
        cached_profile = profile.get("final_candidate_profile")
        if isinstance(cached_profile, dict):
            cached_data = copy.deepcopy(cached_profile)
            cached_data["provider_status"] = {
                **cached_data.get("provider_status", {}),
                "cache_hit": True,
                "mode": "profile_cached",
            }
            cached_data["profile_timing"] = {
                **cached_data.get("profile_timing", {}),
                "profile_llm_ms": 0,
                "cache_hit": True,
            }
            candidate_profile = CandidateProfile(**cached_data)
            session.status = "finished"
            session.current_stage = "finalize_profile"
            session.stage_progress = 1.0
            session.completed_stages = list(dict.fromkeys([*session.completed_stages, "finalize_profile"]))
            session.updated_at = datetime.now(UTC)
            return AssessmentFinalizeOutput(session_id=session.session_id, candidate_profile=candidate_profile)

        skills = profile.get("skills", [])
        behavior = profile.get("behavior_signals", [])
        skill_scores = {skill["name"]: self._skill_score(skill.get("level", "intermediate")) for skill in skills}
        evidence = profile.get("evidence", [])
        dimensions = self._competency_dimensions(skills, behavior)
        projects = profile.get("projects") or [{"name": "待核验项目", "evidence": "来自档案与多轮追问"}]
        archetype_fallback = {
            "code": "SAGE",
            "title": "系统型架构者",
            "narrative": "先建立全局视图，再沿证据链定位关键约束，偏好可验证、可回退的工程决策。",
            "traits": ["结构化拆解", "风险优先", "证据驱动", "稳健协作"],
        }
        profile_started = perf_counter()
        archetype_payload = self._profile_archetype_payload(profile, dimensions)
        archetype_prompt = json.dumps(archetype_payload, ensure_ascii=False, default=str)
        archetype = self.llm.generate_json(
            system_prompt=(
                "你是企业能力画像 Agent。只输出 JSON 对象 code、title、narrative、traits。"
                "这是工作风格原型而非心理诊断；只能依据能力维度、项目追问证据和互动任务行为，不得使用敏感属性。"
                "叙述控制在 120 字以内，traits 最多 4 个。"
            ),
            user_prompt=archetype_prompt,
            fallback=archetype_fallback,
            timeout_seconds=self.profile_timeout_seconds,
            retries=0,
            max_tokens=self.profile_max_tokens,
            disable_thinking=True,
            model=self.profile_model,
        )
        profile_llm_ms = int(archetype.provider_status.get("duration_ms") or round((perf_counter() - profile_started) * 1000))
        archetype.provider_status["duration_ms"] = profile_llm_ms
        archetype.provider_status["profile_llm_ms"] = profile_llm_ms
        archetype.provider_status["prompt_mode"] = "compact_profile_summary"
        archetype.provider_status["user_prompt_chars"] = len(archetype_prompt)
        archetype.provider_status["cache_hit"] = False
        raw_code = re.sub(r"[^A-Za-z]", "", str(archetype.data.get("code", ""))).upper()
        archetype_code = raw_code if 3 <= len(raw_code) <= 6 else archetype_fallback["code"]
        candidate_profile = CandidateProfile(
            candidate_id=session.candidate_id,
            target_job_id=session.target_job_id,
            name=str(profile.get("candidate_name") or ""),
            skills=skills,
            projects=projects,
            behavior_signals=behavior,
            evidence=evidence,
            confidence=round(min(0.96, 0.58 + len(evidence) * 0.045 + len(behavior) * 0.025), 2),
            summary=f"完成 {len(session.completed_stages)} 个评估阶段，形成 {len(evidence)} 条证据，识别 {len(skills)} 项能力。",
            experience_years=profile.get("experience_years") or self._experience_years(profile.get("resume_text", "")),
            education=profile.get("education") or self._education(profile.get("resume_text", "")),
            skill_scores=skill_scores,
            competency_dimensions=dimensions,
            preferred_locations=profile.get("preferred_locations", []),
            expected_salary_k=profile.get("expected_salary_k", []),
            archetype_code=archetype_code,
            archetype_title=str(archetype.data.get("title", archetype_fallback["title"])),
            archetype_narrative=str(archetype.data.get("narrative", archetype_fallback["narrative"])),
            traits=[str(item) for item in archetype.data.get("traits", archetype_fallback["traits"])][:6],
            provider_status=archetype.provider_status,
            profile_timing={"profile_llm_ms": profile_llm_ms, "cache_hit": False},
        )
        session.status = "finished"
        session.current_stage = "finalize_profile"
        session.stage_progress = 1.0
        session.completed_stages = list(dict.fromkeys([*session.completed_stages, "finalize_profile"]))
        session.candidate_profile["final_candidate_profile"] = candidate_profile.model_dump()
        session.updated_at = datetime.now(UTC)
        return AssessmentFinalizeOutput(session_id=session.session_id, candidate_profile=candidate_profile)

    def _profile_archetype_payload(self, profile: dict, dimensions: list[dict]) -> dict:
        evidence = profile.get("evidence", [])
        dialogue_evidence = [
            {
                "content": str(item.get("content", ""))[:220],
                "quality_score": item.get("quality_score"),
                "signals": item.get("signals", {}),
            }
            for item in evidence
            if item.get("stage") == "skill_deep_question" and item.get("type") == "answer"
        ][-3:]
        behavior = [
            {
                "dimension": item.get("dimension"),
                "score": item.get("score"),
                "evidence": str(item.get("evidence", ""))[:120],
            }
            for item in (profile.get("behavior_signals") or [])[-6:]
            if isinstance(item, dict)
        ]
        projects = [
            {
                "name": item.get("name"),
                "role": item.get("role"),
                "tech_stack": item.get("tech_stack", [])[:6] if isinstance(item.get("tech_stack"), list) else item.get("tech_stack"),
                "metrics": item.get("metrics", [])[:3] if isinstance(item.get("metrics"), list) else item.get("metrics"),
                "evidence": self._short_profile_evidence(item.get("evidence"), 160),
            }
            for item in (profile.get("projects") or [])[:3]
            if isinstance(item, dict)
        ]
        return {
            "task": "generate_compact_capability_archetype",
            "dimensions": dimensions,
            "dialogue_evidence": dialogue_evidence,
            "interactive_behavior": behavior,
            "projects": projects,
            "semantic_profile": self._compact_profile_semantic(profile.get("semantic_profile")),
        }

    def _compact_profile_semantic(self, semantic: object) -> dict:
        if not isinstance(semantic, dict):
            return {}
        compact: dict[str, object] = {}
        for key in ("project_capabilities", "skill_usage_assessments", "graph_mappings", "interview_focus"):
            value = semantic.get(key)
            if isinstance(value, list):
                compact[key] = [self._compact_profile_value(item) for item in value[:4]]
            elif value:
                compact[key] = str(value)[:320]
        if semantic.get("status"):
            compact["status"] = semantic.get("status")
        return compact

    def _compact_profile_value(self, value: object) -> object:
        if isinstance(value, dict):
            compact = {}
            for key, item in list(value.items())[:8]:
                if str(key) in {"content", "evidence", "snippet"}:
                    compact[str(key)] = self._short_profile_evidence(item, 180)
                else:
                    compact[str(key)] = self._compact_profile_value(item)
            return compact
        if isinstance(value, list):
            return [self._compact_profile_value(item) for item in value[:5]]
        if isinstance(value, str):
            return value[:180]
        return value

    def _short_profile_evidence(self, value: object, limit: int) -> str:
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        if not text:
            return ""
        parts = [part.strip() for part in re.split(r"[。！？!?；;\n]", text) if part.strip()]
        return (parts[0] if parts else text)[:limit]

    def _advance(self, session: AssessmentSession, next_stage: str, action_type: str, fallback: dict) -> None:
        generated = self._question(next_stage, session.candidate_profile.get("resume_text", ""), session.history, fallback)
        session.completed_stages = list(dict.fromkeys([*session.completed_stages, session.current_stage]))
        session.current_stage = next_stage
        session.stage_progress = {"skill_deep_question": 0.4, "scenario_task": 0.6}.get(next_stage, session.stage_progress)
        session.provider_status = generated.provider_status
        session.next_action = AssessmentAction(
            type=action_type,
            content=self._single_core_question(str(generated.data.get("content", fallback["content"])), fallback["content"]),
            options=self._normalize_list(generated.data.get("options", fallback.get("options", []))),
            metadata={"stage": next_stage, "focus": self._normalize_list(generated.data.get("focus", fallback.get("focus", [])))},
        )
        session.history.append({"role": "assistant", "stage": next_stage, "content": session.next_action.content})

    def _advance_to_next_skill_question(self, session: AssessmentSession) -> bool:
        plan = session.candidate_profile.get("dialogue_skill_plan") or []
        next_index = int(session.candidate_profile.get("dialogue_skill_index") or 0) + 1
        session.candidate_profile["dialogue_skill_index"] = next_index
        if next_index >= len(plan):
            return False
        fallback = self._skill_question_fallback(plan[next_index], next_index + 1, len(plan))
        generated = self._question(
            "skill_deep_question",
            session.candidate_profile.get("resume_text", ""),
            session.history,
            fallback,
            parsed_resume=session.candidate_profile.get("resume_parse", {}),
            require_ai=bool(session.candidate_profile.get("require_ai_questions", self.require_ai_questions)),
        )
        session.current_stage = "skill_deep_question"
        session.stage_progress = min(0.75, 0.2 + ((next_index + 1) / max(len(plan), 1)) * 0.55)
        session.provider_status = generated.provider_status
        session.next_action = AssessmentAction(
            type="question",
            content=self._single_core_question(str(generated.data.get("content", fallback["content"])), fallback["content"]),
            metadata={
                "stage": "skill_deep_question",
                "focus": self._normalize_list(generated.data.get("focus", fallback.get("focus", []))),
                "skill": fallback.get("skill"),
                "project": fallback.get("project"),
                "round_type": fallback.get("round_type"),
                "skill_index": next_index + 1,
                "skill_total": len(plan),
                "technical": fallback.get("technical", False),
            },
        )
        session.history.append({
            "role": "assistant",
            "stage": "skill_deep_question",
            "content": session.next_action.content,
            "skill": fallback.get("skill"),
        })
        return True

    def _enter_interactive_game(self, session: AssessmentSession) -> None:
        scenario = session.candidate_profile.get("game_scenario") or self._build_game_scenario(session)
        session.candidate_profile["dialogue_completed"] = True
        session.candidate_profile["dialogue_score"] = self._dialogue_score(session)
        session.candidate_profile["game_scenario"] = scenario
        session.completed_stages = list(dict.fromkeys([*session.completed_stages, "skill_deep_question"]))
        if session.candidate_profile.get("interactive_game_completed"):
            session.current_stage = "finalize_profile"
            session.stage_progress = 1.0
            session.completed_stages = list(dict.fromkeys([*session.completed_stages, "interactive_game"]))
            session.next_action = AssessmentAction(type="finish", content="深度对话和互动任务均已完成，可以生成最终画像。", metadata={"stage": "finalize_profile"})
            session.history.append({"role": "assistant", "stage": "finalize_profile", "content": session.next_action.content})
            return
        if not session.candidate_profile.get("interactive_game_completed"):
            session.current_stage = "interactive_game"
        session.stage_progress = 0.8
        session.next_action = AssessmentAction(
            type="interactive_game",
            content=scenario["brief"],
            options=[choice["id"] for chapter in scenario["chapters"] for choice in chapter["choices"]],
            metadata={
                "stage": "interactive_game",
                "budget": scenario["budget"],
                "time_limit_seconds": scenario["time_limit_seconds"],
                "scoring_dimensions": scenario["scoring_dimensions"],
                "game_scenario": scenario,
            },
        )
        session.history.append({"role": "assistant", "stage": "interactive_game", "content": session.next_action.content})

    def _dialogue_score(self, session: AssessmentSession) -> dict:
        answers = [
            item
            for item in session.evidence
            if item.get("type") == "answer" and item.get("stage") == "skill_deep_question"
        ]
        if not answers:
            return {
                "score": 0,
                "rounds": 0,
                "level": "待评估",
                "signals": {"measurable_count": 0, "ownership_count": 0, "technical_term_total": 0},
            }
        avg = sum(float(item.get("quality_score", 0)) for item in answers) / len(answers)
        measurable_count = sum(1 for item in answers if item.get("signals", {}).get("measurable"))
        ownership_count = sum(1 for item in answers if item.get("signals", {}).get("ownership"))
        technical_total = sum(int(item.get("signals", {}).get("technical_term_count") or 0) for item in answers)
        score = round(avg * 100)
        if score >= 82:
            level = "强证据"
        elif score >= 68:
            level = "较充分"
        elif score >= 55:
            level = "需复核"
        else:
            level = "证据不足"
        return {
            "score": score,
            "rounds": len(answers),
            "level": level,
            "signals": {
                "measurable_count": measurable_count,
                "ownership_count": ownership_count,
                "technical_term_total": technical_total,
            },
        }

    def _build_game_scenario(self, session: AssessmentSession) -> dict:
        return self._build_game_scenario_from_profile(session.candidate_profile)

    def _build_game_scenario_from_profile(self, profile: dict) -> dict:
        skill_names = [str(item.get("name", "")).strip() for item in profile.get("skills", []) if item.get("name")]
        project_names = [str(item.get("name", "")).strip() for item in profile.get("projects", []) if item.get("name")]
        technical = [name for name in skill_names if self._is_technical_skill(name)]
        anchor_skill = technical[0] if technical else (skill_names[0] if skill_names else "核心能力")
        secondary_skill = technical[1] if len(technical) > 1 else (skill_names[1] if len(skill_names) > 1 else anchor_skill)
        project = project_names[0] if project_names else "候选人简历中的核心项目"
        lower_skills = " ".join(skill_names).lower()
        if any(term in lower_skills for term in ("rag", "llm", "langchain", "langgraph", "向量", "检索", "大模型")):
            return self._rag_game_scenario(anchor_skill, secondary_skill, project, skill_names)
        if any(term in lower_skills for term in ("mqtt", "设备影子", "边缘计算", "数字孪生", "iot", "物联网")):
            return self._iot_game_scenario(anchor_skill, secondary_skill, project, skill_names)
        if any(term in lower_skills for term in ("kafka", "clickhouse", "大数据", "实时计算", "数据仓库", "流式", "etl")):
            return self._data_game_scenario(anchor_skill, secondary_skill, project, skill_names)
        return self._general_game_scenario(anchor_skill, secondary_skill, project, skill_names)

    def _scenario_base(self, scenario_id: str, title: str, brief: str, project: str, skills: list[str], chapters: list[dict]) -> dict:
        return {
            "id": scenario_id,
            "title": title,
            "brief": brief,
            "project": project,
            "skills": skills[:6],
            "budget": 12,
            "time_limit_seconds": 180,
            "scoring_dimensions": ["信息搜集", "优先级", "风险控制", "资源配置", "协作沟通"],
            "meters": {"health": "任务稳定", "evidence": "证据完整", "trust": "协作信任"},
            "initial_metrics": {"health": 42, "evidence": 18, "trust": 58},
            "chapters": chapters,
        }

    def _rag_game_scenario(self, anchor: str, secondary: str, project: str, skills: list[str]) -> dict:
        return self._scenario_base(
            "rag_quality_rescue",
            "知识库问答质量急救",
            f"基于「{project}」和 {anchor} 相关经历，模拟一次企业知识库问答质量突然下降的处置任务。",
            project,
            skills,
            [
                {"time": "09:42", "title": "第一幕 · 命中率骤降", "objective": "先确认质量下降的真实范围", "scene": f"业务反馈知识库答案开始引用旧制度，{anchor} 相关召回命中率明显下降，客服已经暂停部分自动回复。", "choices": [
                    {"id": "rag_eval_set", "title": "抽取失败样本建评测集", "description": "先把错误答案、缺失文档和命中 query 做成小评测集。", "effect": "证据 +28 · 恢复较慢", "delta": {"health": -2, "evidence": 28, "trust": 6}},
                    {"id": "rag_reindex", "title": "立即重建向量索引", "description": "跳过定位，直接全量重建索引并替换线上。", "effect": "恢复机会 +14 · 根因不明", "delta": {"health": 14, "evidence": 5, "trust": -4}},
                    {"id": "rag_prompt_patch", "title": "先改提示词兜住回答", "description": "要求模型遇到不确定内容必须拒答。", "effect": "风险下降 · 覆盖不足", "delta": {"health": 6, "evidence": 8, "trust": 2}},
                ]},
                {"time": "10:05", "title": "第二幕 · 证据冲突", "objective": "选择验证召回还是生成链路", "scene": f"评测显示部分问题召回正确但回答仍错，另一些问题完全检索不到。团队怀疑 {secondary} 链路和文档切片都有问题。", "choices": [
                    {"id": "rag_ab_trace", "title": "做检索到生成链路追踪", "description": "逐条记录 query、topK、引用片段和最终回答。", "effect": "证据 +32 · 定位清晰", "delta": {"health": 10, "evidence": 32, "trust": 8}},
                    {"id": "rag_raise_topk", "title": "提高 topK 和上下文长度", "description": "先扩大召回范围，观察答案是否恢复。", "effect": "覆盖 +12 · 延迟上升", "delta": {"health": 9, "evidence": 10, "trust": -1}},
                    {"id": "rag_manual_answer", "title": "切人工审核队列", "description": "关键问题转人工，暂停自动回答。", "effect": "风险可控 · 效率下降", "delta": {"health": 12, "evidence": 14, "trust": 4}},
                ]},
                {"time": "10:28", "title": "第三幕 · 热点压力", "objective": "在质量和响应速度间做取舍", "scene": "业务要求今天恢复自动回复，但评测集仍有一批边界问题不稳定。", "choices": [
                    {"id": "rag_gate_release", "title": "按置信度分级放量", "description": "高置信自动答，低置信转人工，并持续记录失败样本。", "effect": "健康 +24 · 闭环清晰", "delta": {"health": 24, "evidence": 18, "trust": 12}},
                    {"id": "rag_full_release", "title": "全量恢复自动回复", "description": "先满足业务效率，后续再修边界问题。", "effect": "健康 +20 · 信任风险", "delta": {"health": 20, "evidence": -4, "trust": -14}},
                    {"id": "rag_keep_pause", "title": "继续暂停自动回复", "description": "等待全部问题修完再恢复。", "effect": "质量稳 · 业务压力大", "delta": {"health": 6, "evidence": 16, "trust": -6}},
                ]},
                {"time": "11:10", "title": "终幕 · 复盘上线", "objective": "定义长期治理动作", "scene": "问答质量恢复，但新增文档仍可能再次引入污染。你需要决定后续治理机制。", "choices": [
                    {"id": "rag_regression_suite", "title": "建立回归评测流水线", "description": "新增文档入库前自动跑召回和回答一致性评测。", "effect": "信任 +24 · 长期收益", "delta": {"health": 18, "evidence": 24, "trust": 24}},
                    {"id": "rag_owner_review", "title": "只要求业务人工复核", "description": "文档负责人手动确认后再入库。", "effect": "成本低 · 漏检风险", "delta": {"health": 8, "evidence": 8, "trust": 4}},
                    {"id": "rag_vendor_switch", "title": "更换模型供应商", "description": "把问题归因为模型能力，切换到更强模型。", "effect": "不确定收益 · 成本上升", "delta": {"health": 10, "evidence": 2, "trust": -3}},
                ]},
            ],
        )

    def _iot_game_scenario(self, anchor: str, secondary: str, project: str, skills: list[str]) -> dict:
        return self._scenario_base(
            "iot_device_shadow_recovery",
            "设备状态漂移处置",
            f"基于「{project}」和 {anchor} 相关经历，模拟一次设备状态与平台数据不一致的现场处置。",
            project,
            skills,
            [
                {"time": "14:08", "title": "第一幕 · 状态漂移", "objective": "判断问题来自设备、网络还是平台", "scene": f"一批设备在线但平台显示离线，{anchor} 数据延迟超过 12 分钟，现场人员无法确认真实状态。", "choices": [
                    {"id": "iot_trace_topic", "title": "追踪主题链路", "description": "检查设备上报、网关转发、平台消费和设备影子更新时间。", "effect": "证据 +30 · 定位更稳", "delta": {"health": 8, "evidence": 30, "trust": 8}},
                    {"id": "iot_restart_gateway", "title": "重启边缘网关", "description": "先恢复连接，再观察状态是否同步。", "effect": "健康 +15 · 原因不明", "delta": {"health": 15, "evidence": 5, "trust": -2}},
                    {"id": "iot_mark_offline", "title": "全部标记离线", "description": "避免错误控制指令下发。", "effect": "风险下降 · 业务中断", "delta": {"health": 4, "evidence": 10, "trust": -8}},
                ]},
                {"time": "14:21", "title": "第二幕 · 指令堆积", "objective": "处理积压指令和状态一致性", "scene": f"排查发现 {secondary} 相关消费堆积，历史控制指令可能在设备恢复后集中下发。", "choices": [
                    {"id": "iot_quarantine_commands", "title": "隔离过期控制指令", "description": "按时间窗和设备批次冻结风险指令。", "effect": "风险控制 +22", "delta": {"health": 16, "evidence": 18, "trust": 10}},
                    {"id": "iot_scale_consumer", "title": "扩容消费服务", "description": "优先清空消息积压。", "effect": "吞吐 +20 · 风险未分级", "delta": {"health": 18, "evidence": 8, "trust": -1}},
                    {"id": "iot_manual_sync", "title": "人工同步设备状态", "description": "让现场逐台确认关键设备。", "effect": "准确 · 慢", "delta": {"health": 6, "evidence": 16, "trust": 4}},
                ]},
                {"time": "14:39", "title": "第三幕 · 分批恢复", "objective": "选择恢复策略", "scene": "平台链路已恢复，但不同型号设备固件版本不一致，批量恢复可能再次触发漂移。", "choices": [
                    {"id": "iot_canary_models", "title": "按型号灰度恢复", "description": "先恢复低风险型号，并监控状态差异率。", "effect": "健康 +24 · 可回退", "delta": {"health": 24, "evidence": 18, "trust": 12}},
                    {"id": "iot_all_resume", "title": "全部设备恢复", "description": "一次性恢复所有设备在线状态。", "effect": "速度快 · 风险高", "delta": {"health": 18, "evidence": 1, "trust": -12}},
                    {"id": "iot_keep_lock", "title": "保持控制锁定", "description": "暂不恢复远程控制能力。", "effect": "安全 · 业务受限", "delta": {"health": 8, "evidence": 14, "trust": -4}},
                ]},
                {"time": "15:05", "title": "终幕 · 规则沉淀", "objective": "定义防复发机制", "scene": "状态一致性恢复。你需要决定如何避免设备影子再次漂移。", "choices": [
                    {"id": "iot_consistency_guard", "title": "建立影子一致性校验", "description": "加入版本号、水位线和过期指令拦截。", "effect": "信任 +22 · 长期稳定", "delta": {"health": 18, "evidence": 22, "trust": 22}},
                    {"id": "iot_dashboard_only", "title": "增加监控看板", "description": "只展示状态漂移率和告警。", "effect": "可见性提升 · 防护不足", "delta": {"health": 8, "evidence": 16, "trust": 4}},
                    {"id": "iot_vendor_ticket", "title": "交给设备厂商处理", "description": "要求厂商修复固件差异。", "effect": "责任外移 · 周期不可控", "delta": {"health": 4, "evidence": 6, "trust": -6}},
                ]},
            ],
        )

    def _data_game_scenario(self, anchor: str, secondary: str, project: str, skills: list[str]) -> dict:
        return self._scenario_base(
            "data_pipeline_quality_war",
            "数据链路质量保卫战",
            f"基于「{project}」和 {anchor} 相关经历，模拟一次核心指标异常的数据链路排障任务。",
            project,
            skills,
            [
                {"time": "08:55", "title": "第一幕 · 指标突变", "objective": "先判断是真实业务变化还是数据异常", "scene": f"经营看板核心指标突然下降 37%，{anchor} 相关链路昨晚有任务重跑，业务方准备据此调整投放预算。", "choices": [
                    {"id": "data_lineage_check", "title": "检查血缘和重跑记录", "description": "沿数据血缘确认采集、清洗、汇总和报表层变化。", "effect": "证据 +30 · 决策更稳", "delta": {"health": 8, "evidence": 30, "trust": 8}},
                    {"id": "data_patch_report", "title": "直接修正报表数值", "description": "按昨日趋势回填指标，先避免业务误判。", "effect": "表面恢复 · 审计风险", "delta": {"health": 12, "evidence": -6, "trust": -10}},
                    {"id": "data_wait_batch", "title": "等待下一批任务", "description": "先观察下一个调度周期是否自动恢复。", "effect": "低成本 · 延误判断", "delta": {"health": -8, "evidence": 6, "trust": -5}},
                ]},
                {"time": "09:18", "title": "第二幕 · 口径冲突", "objective": "处理技术口径和业务口径不一致", "scene": f"排查发现 {secondary} 任务输出正常，但业务定义变更没有同步到下游聚合。", "choices": [
                    {"id": "data_contract_sync", "title": "建立口径变更确认", "description": "拉齐字段定义、影响面和下游消费方。", "effect": "信任 +18 · 证据完整", "delta": {"health": 12, "evidence": 22, "trust": 18}},
                    {"id": "data_hotfix_sql", "title": "临时改 SQL 适配", "description": "先在报表层兼容新字段。", "effect": "恢复快 · 技术债", "delta": {"health": 18, "evidence": 8, "trust": -1}},
                    {"id": "data_reject_change", "title": "回退业务口径", "description": "要求业务恢复原定义。", "effect": "技术简单 · 协作受损", "delta": {"health": 8, "evidence": 5, "trust": -8}},
                ]},
                {"time": "09:46", "title": "第三幕 · 下游扩散", "objective": "决定是否冻结下游使用", "scene": "多个团队已经下载异常数据，继续扩散会影响日报和模型特征。", "choices": [
                    {"id": "data_freeze_downstream", "title": "冻结下游并发布数据公告", "description": "阻断异常版本继续被使用，说明影响范围。", "effect": "风险控制 +24", "delta": {"health": 18, "evidence": 16, "trust": 14}},
                    {"id": "data_silent_fix", "title": "静默修复数据", "description": "不打扰业务，修完后覆盖旧数据。", "effect": "效率高 · 可追溯差", "delta": {"health": 20, "evidence": -3, "trust": -12}},
                    {"id": "data_parallel_versions", "title": "保留双版本对比", "description": "提供新旧口径并行结果。", "effect": "透明 · 解释成本高", "delta": {"health": 12, "evidence": 20, "trust": 10}},
                ]},
                {"time": "10:30", "title": "终幕 · 质量门禁", "objective": "设计防复发机制", "scene": "数据恢复正常。你需要决定后续上线门禁和监控方式。", "choices": [
                    {"id": "data_quality_gate", "title": "增加数据质量门禁", "description": "对波动、空值、枚举和血缘变更建立自动拦截。", "effect": "长期稳定 +24", "delta": {"health": 20, "evidence": 22, "trust": 22}},
                    {"id": "data_more_alarm", "title": "只增加告警阈值", "description": "发现异常后通知负责人。", "effect": "可见性提升 · 拦截不足", "delta": {"health": 8, "evidence": 14, "trust": 3}},
                    {"id": "data_manual_review", "title": "上线前人工审批", "description": "所有口径变更走人工确认。", "effect": "稳妥 · 效率下降", "delta": {"health": 10, "evidence": 16, "trust": 6}},
                ]},
            ],
        )

    def _general_game_scenario(self, anchor: str, secondary: str, project: str, skills: list[str]) -> dict:
        return self._scenario_base(
            "project_delivery_decision",
            "项目交付决策模拟",
            f"基于「{project}」和 {anchor} 相关经历，模拟一次交付前质量、范围和协作压力同时出现的任务。",
            project,
            skills,
            [
                {"time": "16:20", "title": "第一幕 · 需求压缩", "objective": "确认最先澄清的任务边界", "scene": f"项目验收提前，{anchor} 相关工作还有边界不清的部分，业务希望今天给出可交付版本。", "choices": [
                    {"id": "delivery_scope", "title": "锁定验收范围", "description": "先确认必须交付、可延期和不可接受风险。", "effect": "证据 +24 · 协作更稳", "delta": {"health": 10, "evidence": 24, "trust": 10}},
                    {"id": "delivery_overtime", "title": "直接加班赶完", "description": "不调整范围，尽量完成所有要求。", "effect": "速度 +16 · 质量风险", "delta": {"health": 14, "evidence": 2, "trust": -6}},
                    {"id": "delivery_delay", "title": "要求整体延期", "description": "拒绝今天交付。", "effect": "质量稳 · 业务压力", "delta": {"health": 4, "evidence": 10, "trust": -8}},
                ]},
                {"time": "16:45", "title": "第二幕 · 质量缺口", "objective": "决定如何验证交付质量", "scene": f"你发现 {secondary} 相关结果在复杂样例下不稳定，但普通样例看起来通过。", "choices": [
                    {"id": "delivery_edge_cases", "title": "补充边界样例验证", "description": "挑选最容易失败的样例做快速验证。", "effect": "证据 +28 · 风险显性", "delta": {"health": 8, "evidence": 28, "trust": 8}},
                    {"id": "delivery_happy_path", "title": "只验收主流程", "description": "先保证展示链路顺畅。", "effect": "速度快 · 漏洞风险", "delta": {"health": 14, "evidence": 4, "trust": -8}},
                    {"id": "delivery_manual_fix", "title": "人工修正异常样例", "description": "把已知问题逐个手动处理。", "effect": "短期可控 · 不可扩展", "delta": {"health": 10, "evidence": 12, "trust": 1}},
                ]},
                {"time": "17:10", "title": "第三幕 · 资源冲突", "objective": "在有限资源中安排优先级", "scene": "同伴同时请求你支援文档、演示和问题修复，时间只够完整做好其中一类。", "choices": [
                    {"id": "delivery_risk_first", "title": "优先修最高风险问题", "description": "先处理会影响验收结论的问题。", "effect": "健康 +22 · 取舍清晰", "delta": {"health": 22, "evidence": 14, "trust": 10}},
                    {"id": "delivery_demo_first", "title": "优先打磨演示", "description": "保证现场观感和叙事完整。", "effect": "展示好 · 实质风险", "delta": {"health": 10, "evidence": 4, "trust": -3}},
                    {"id": "delivery_docs_first", "title": "优先补齐文档", "description": "把说明、边界和操作步骤写清楚。", "effect": "协作 +12 · 修复不足", "delta": {"health": 8, "evidence": 18, "trust": 12}},
                ]},
                {"time": "17:45", "title": "终幕 · 验收沟通", "objective": "决定如何对外说明结果", "scene": "交付版本基本完成，但仍有一项低概率边界风险。你需要决定如何向评审或业务说明。", "choices": [
                    {"id": "delivery_transparent", "title": "透明说明风险和预案", "description": "明确已验证范围、剩余风险和回退方案。", "effect": "信任 +24 · 专业闭环", "delta": {"health": 18, "evidence": 20, "trust": 24}},
                    {"id": "delivery_hide_risk", "title": "不主动提风险", "description": "避免影响验收信心。", "effect": "短期顺利 · 信任风险", "delta": {"health": 12, "evidence": -4, "trust": -16}},
                    {"id": "delivery_more_time", "title": "争取补充验证时间", "description": "延迟交付，补齐所有边界测试。", "effect": "质量更稳 · 节奏变慢", "delta": {"health": 12, "evidence": 18, "trust": 4}},
                ]},
            ],
        )

    def _question(
        self,
        stage: str,
        resume: str,
        history: list[dict],
        fallback: dict,
        *,
        parsed_resume: dict | None = None,
        require_ai: bool = False,
    ):
        prompt_payload = {
            "stage": stage,
            "resume_summary": self._dialogue_resume_context(parsed_resume or {}),
            "recent_history": history[-8:],
            "previous_answer": next((item.get("content") for item in reversed(history) if item.get("role") == "candidate"), ""),
            "question_focus": fallback,
            "already_asked_skills": [
                item.get("skill")
                for item in history
                if item.get("role") == "assistant" and item.get("skill")
            ],
        }
        started = perf_counter()
        result = self.llm.generate_json(
            system_prompt=(
                "你是企业技术招聘评估官。只输出 JSON 对象，包含 content、focus，可选 options。"
                "像真实面试官一样基于简历、项目证据、当前技能焦点和上一轮回答继续深挖。content 必须只包含一个核心问题。"
                "禁止编号、列表、多个补充点、多个问号或一次问多个问题。"
                "如 question_focus 中提供 skill，问题必须围绕该技能标签。"
                "问题必须引用或贴合候选人简历中的具体项目、技术栈、指标、职责边界或上一轮回答细节之一。"
                "不要使用通用模板句，不要反复问“最关键/最棘手/如何验证”这类空泛问题。"
                "技术类技能优先询问工程机制、设计取舍、故障定位、性能边界或验证指标。"
                "非强技术技能只询问真实使用场景、质量标准、交付难点或成果证明，不要硬问底层技术。"
                "避免使用“真实熟练度”“交付成果”这类泛化话术，问题要像面试现场自然追问。"
                "问题要聚焦候选人的个人行动、技术依据、量化结果或可验证证据之一，不得询问敏感个人信息。"
            ),
            user_prompt=json.dumps(prompt_payload, ensure_ascii=False, default=str),
            fallback=fallback,
            timeout_seconds=self.dialogue_timeout_seconds,
            max_tokens=self.dialogue_max_tokens,
            disable_thinking=True,
            model=self.dialogue_model,
        )
        result.provider_status["duration_ms"] = result.provider_status.get("duration_ms") or round((perf_counter() - started) * 1000)
        result.provider_status["dialogue_question_ms"] = result.provider_status["duration_ms"]
        result.provider_status["prompt_mode"] = "structured_resume_summary"
        if require_ai and result.provider_status.get("fallback"):
            reason = result.provider_status.get("reason", "question_generation_failed")
            raise AssessmentQuestionError(f"深度对话模型未能生成个性化问题，请检查模型配置或稍后重试：{reason}")
        if require_ai and not self._question_has_context(str(result.data.get("content", "")), fallback, parsed_resume or {}, history):
            raise AssessmentQuestionError("深度对话模型返回的问题过于通用，未贴合当前简历、技能或上一轮回答，请重新生成。")
        return result

    def _dialogue_resume_context(self, parsed: dict) -> dict:
        skills = [
            {
                "name": item.get("name"),
                "level": item.get("level"),
                "usage_status": item.get("usage_status"),
                "evidence": item.get("evidence"),
                "occurrences": item.get("occurrences", [])[:2],
            }
            for item in parsed.get("skills", [])[:8]
            if isinstance(item, dict) and item.get("name")
        ]
        projects = [
            {
                "name": item.get("name"),
                "role": item.get("role"),
                "tech_stack": item.get("tech_stack", []),
                "metrics": item.get("metrics", []),
                "evidence": item.get("evidence"),
            }
            for item in parsed.get("projects", [])[:5]
            if isinstance(item, dict) and item.get("name")
        ]
        return {
            "job_intent": parsed.get("job_intent"),
            "skills": skills,
            "projects": projects,
            "semantic_profile": parsed.get("semantic_profile"),
            "experience_years": parsed.get("experience_years"),
            "education": parsed.get("education"),
            "certifications": parsed.get("certifications", [])[:6],
            "city_preferences": parsed.get("city_preferences") or parsed.get("preferred_locations", [])[:4],
            "evidence": parsed.get("evidence", [])[:6],
        }

    def _env_float(self, name: str, default: float) -> float:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = float(raw)
        except ValueError:
            return default
        return value if value > 0 else default

    def _env_int(self, name: str, default: int) -> int:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return value if value > 0 else default

    def _question_has_context(self, content: str, fallback: dict, parsed: dict, history: list[dict]) -> bool:
        text = re.sub(r"\s+", "", content or "").lower()
        if not text:
            return False
        anchors: list[str] = []
        if fallback.get("skill"):
            anchors.append(str(fallback["skill"]))
        for item in parsed.get("skills", [])[:8]:
            if isinstance(item, dict):
                anchors.append(str(item.get("name", "")))
        for item in parsed.get("projects", [])[:5]:
            if isinstance(item, dict):
                anchors.append(str(item.get("name", "")))
        for item in reversed(history[-4:]):
            if item.get("role") == "candidate":
                anchors.extend(re.findall(r"[A-Za-z][A-Za-z0-9+#./-]{1,}|[\u4e00-\u9fff]{2,8}", str(item.get("content", "")))[:6])
                break
        cleaned = [re.sub(r"\s+", "", anchor).lower() for anchor in anchors if len(str(anchor).strip()) >= 2]
        return any(anchor and anchor in text for anchor in cleaned)

    def _parse_resume(self, resume: str, *, candidate_id: str | None = None) -> tuple[dict, dict]:
        data = self.resume_parser.parse(resume, candidate_id=candidate_id)
        data["skills"] = [item for item in data.get("skills", []) if isinstance(item, dict) and item.get("name")]
        data["projects"] = [item for item in data.get("projects", []) if isinstance(item, dict) and item.get("name")]
        return data, data.get("provider_status", {})

    def _resume_parse_or_parse(self, resume: str, resume_parse: dict | None, *, candidate_id: str | None = None) -> tuple[dict, dict]:
        if not isinstance(resume_parse, dict):
            return self._parse_resume(resume, candidate_id=candidate_id)
        data = dict(resume_parse)
        data["candidate_id"] = data.get("candidate_id") or candidate_id
        data["raw_text"] = data.get("raw_text") or resume
        data["skills"] = [item for item in data.get("skills", []) if isinstance(item, dict) and item.get("name")]
        data["projects"] = [item for item in data.get("projects", []) if isinstance(item, dict) and item.get("name")]
        data.setdefault("evidence", [])
        data.setdefault("quality_summary", self._resume_parse_summary(data["skills"], data["projects"], data["evidence"]))
        return data, data.get("provider_status", {"source": "uploaded_resume_parse"})

    def _resume_parse_summary(self, skills: list[dict], projects: list[dict], evidence: list[dict]) -> dict:
        confidences = [float(item.get("confidence", 0)) for item in evidence if isinstance(item, dict)]
        avg_confidence = round(sum(confidences) / max(len(confidences), 1), 2)
        return {
            "skill_count": len(skills),
            "project_count": len(projects),
            "evidence_count": len(evidence),
            "has_quantified_metrics": any(project.get("metrics") for project in projects),
            "avg_evidence_confidence": avg_confidence,
            "needs_manual_review": len(skills) == 0 or avg_confidence < 0.55,
        }

    def _dialogue_skill_plan(self, skills: list[dict], projects: list[dict] | None = None) -> list[dict]:
        project = next((item for item in projects or [] if isinstance(item, dict) and item.get("name")), None)
        skill_names = []
        for skill in skills:
            if isinstance(skill, dict) and skill.get("name"):
                name = str(skill["name"]).strip()
                if name and name not in skill_names:
                    skill_names.append(name)
        skill_names.sort(key=lambda item: (not self._is_technical_skill(item), item.lower()))
        project_name = str((project or {}).get("name") or "核心项目经历").strip()
        project_evidence = str((project or {}).get("evidence") or "").strip()
        tech_stack = [str(item).strip() for item in (project or {}).get("tech_stack", []) if str(item).strip()]
        if not tech_stack:
            tech_stack = skill_names[:5]
        anchors = tech_stack or skill_names or ["核心能力"]
        return [
            {
                "name": project_name,
                "project": project_name,
                "skill": anchors[0],
                "technical": self._is_technical_skill(anchors[0]),
                "round_type": "ownership_scope",
                "level": None,
                "evidence": project_evidence,
            },
            {
                "name": project_name,
                "project": project_name,
                "skill": anchors[1] if len(anchors) > 1 else anchors[0],
                "technical": self._is_technical_skill(anchors[1] if len(anchors) > 1 else anchors[0]),
                "round_type": "technical_decision",
                "level": None,
                "evidence": project_evidence,
            },
            {
                "name": project_name,
                "project": project_name,
                "skill": anchors[2] if len(anchors) > 2 else anchors[-1],
                "technical": self._is_technical_skill(anchors[2] if len(anchors) > 2 else anchors[-1]),
                "round_type": "result_verification",
                "level": None,
                "evidence": project_evidence,
            },
        ]

    def _is_technical_skill(self, name: str) -> bool:
        text = name.lower()
        nontechnical = {
            "word", "excel", "powerpoint", "ppt", "office", "visio", "photoshop",
            "沟通", "协作", "文档", "长文档排版", "项目管理", "需求分析",
        }
        if text in nontechnical or name in nontechnical:
            return False
        technical_patterns = (
            "python", "java", "javascript", "typescript", "go", "rust", "c++", "sql",
            "react", "vue", "fastapi", "spring", "django", "flask", "node", "redis",
            "mysql", "postgres", "clickhouse", "mongodb", "kafka", "rabbitmq", "docker",
            "kubernetes", "linux", "rag", "llm", "langchain", "langgraph", "pytorch",
            "tensorflow", "opencv", "ocr", "nlp", "mqtt", "nacos", "sentinel", "api",
            "微服务", "数据库", "缓存", "向量", "检索", "算法", "模型", "训练",
            "部署", "容器", "边缘计算", "设备影子", "数字孪生", "大数据", "实时计算",
            "数据仓库", "数据湖", "流式", "运维", "监控", "测试开发", "接口",
        )
        return any(pattern in text or pattern in name for pattern in technical_patterns)

    def _skill_question_fallback(self, skill: dict | None, index: int, total: int) -> dict:
        name = str((skill or {}).get("project") or (skill or {}).get("name") or "核心项目经历").strip()
        anchor = str((skill or {}).get("skill") or "关键技术").strip()
        technical = bool((skill or {}).get("technical"))
        round_type = str((skill or {}).get("round_type") or "ownership_scope")
        templates = {
            "ownership_scope": (
                f"围绕「{name}」，请只讲一个最能证明你个人贡献的关键任务：你具体负责哪一段，边界是什么？",
                ["项目真实性", "个人贡献", "职责边界"],
            ),
            "technical_decision": (
                f"在「{name}」里和 {anchor} 相关的实现中，你做过最关键的一次技术取舍是什么，依据是什么？",
                ["技术深度", "方案取舍", "技术依据"],
            ),
            "result_verification": (
                f"你如何验证「{name}」最终确实产生了效果？请说明指标、对比方式或失败后的复盘动作。",
                ["结果验证", "量化指标", "复盘改进"],
            ),
        }
        content, detail_focus = templates.get(round_type, templates["ownership_scope"])
        focus = [name, anchor, *detail_focus]
        return {
            "content": content,
            "focus": focus,
            "skill": anchor,
            "project": name,
            "round_type": round_type,
            "technical": technical,
            "skill_index": index,
            "skill_total": total,
        }

    def _initial_question_fallback(self, parsed: dict) -> dict:
        projects = [str(item.get("name", "")).strip() for item in parsed.get("projects", []) if item.get("name")]
        skills = [str(item.get("name", "")).strip() for item in parsed.get("skills", []) if item.get("name")]
        if projects:
            content = f"在「{projects[0]}」中，最能证明你个人贡献的关键技术决策是什么？"
        elif skills:
            content = f"围绕 {self._join_terms(skills[:3])}，哪一个项目最能证明你的真实技术深度？"
        else:
            content = "简历中最能代表你能力的一段经历是什么？"
        return {"content": content, "focus": ["个人职责", "技术决策", "量化结果", "可验证材料"]}

    def _stage_fallback(self, session: AssessmentSession, next_stage: str) -> dict:
        profile = session.candidate_profile
        skills = [str(item.get("name", "")).strip() for item in profile.get("skills", []) if item.get("name")]
        projects = [str(item.get("name", "")).strip() for item in profile.get("projects", []) if item.get("name")]
        if next_stage == "skill_deep_question":
            anchor = self._join_terms(skills[:3]) or (projects[0] if projects else "刚才提到的关键技术")
            content = f"围绕 {anchor}，你亲自验证过的最关键技术机制是什么？"
            return {"content": content, "focus": ["核心机制", "技术权衡", "性能边界", "验证指标"]}
        if next_stage == "scenario_task":
            anchor = projects[0] if projects else (skills[0] if skills else "你的项目经验")
            return {
                "content": f"如果「{anchor}」相关系统线上延迟突然升高，你前 15 分钟最先验证的关键假设是什么？",
                "focus": ["优先级", "证据链", "止损", "协作升级"],
                "options": ["先建立影响面", "立即无条件扩容", "直接回滚", "等待更多反馈"],
            }
        return {"content": "你这段回答里最关键的判断依据是什么？", "focus": ["个人行动", "判断依据", "量化结果", "复盘"]}

    def _single_core_question(self, content: str, fallback: str) -> str:
        text = re.sub(r"\s+", " ", content or "").strip()
        if not text:
            return fallback
        text = re.sub(r"^(?:问题|追问|面试官|content)\s*[：:]\s*", "", text, flags=re.I)
        text = re.sub(r"(^|[。；;]\s*)(?:[-*•]|\d+|[一二三四五六七八九十])[）).、]\s*", r"\1", text)
        banned_generic = ("真实熟练度", "交付成果")
        if any(phrase in text for phrase in banned_generic):
            return fallback
        question_candidates = [item.strip(" 。；;") for item in re.findall(r"[^。！？!?；;]*[？?]", text)]
        sentence_candidates = [item.strip(" 。；;") for item in re.split(r"[。！!；;]", text) if item.strip()]
        for candidate in [*question_candidates, *sentence_candidates]:
            question = self._trim_to_one_question(candidate)
            if question:
                return question[:120]
        return fallback

    def _same_question(self, left: str, right: str) -> bool:
        return re.sub(r"\s+", "", left or "") == re.sub(r"\s+", "", right or "")

    def _trim_to_one_question(self, candidate: str) -> str:
        text = re.sub(r"\s+", " ", candidate or "").strip(" 。；;")
        if not text:
            return ""
        clauses = [item.strip(" ，,、") for item in re.split(r"(?:，|,|、|以及|并且|同时|然后|和)", text) if item.strip(" ，,、")]
        if len(re.findall(r"(什么|哪些|哪一|哪个|如何|怎么|为什么|是否|能否|多少)", text)) > 1 and clauses:
            action_terms = ("做", "处理", "验证", "设计", "排查", "优化", "判断", "负责", "解决", "落地")
            clauses.sort(key=lambda item: (not any(term in item for term in action_terms), len(item)))
            text = clauses[0]
        text = text.strip(" ？?")
        if not text or len(text) < 4:
            return ""
        if len(text) > 140:
            text = text[:140].rsplit("，", 1)[0] or text[:120]
        if not re.search(r"[？?]$", text):
            text = f"{text}？"
        return text

    def _normalize_list(self, value: object) -> list[str]:
        if isinstance(value, list):
            items = value
        elif isinstance(value, str):
            items = re.split(r"[、,，;；\n]", value)
        elif isinstance(value, dict):
            items = value.values()
        else:
            items = []
        normalized: list[str] = []
        for item in items:
            if isinstance(item, dict):
                item = item.get("name") or item.get("label") or item.get("skill") or item.get("topic") or ""
            text = str(item).strip()
            if text and text not in normalized:
                normalized.append(text)
        return normalized[:6]

    def _join_terms(self, terms: list[str]) -> str:
        clean = [item for item in terms if item]
        if not clean:
            return ""
        if len(clean) == 1:
            return clean[0]
        return "、".join(clean[:-1]) + f" 和 {clean[-1]}"

    def _answer_evidence(self, stage: str, answer: str, index: int) -> dict:
        measurable = bool(re.search(r"\d+(?:\.\d+)?\s*(?:%|ms|秒|分钟|万|QPS|TPS)", answer, re.I))
        technical_terms = sum(term.lower() in answer.lower() for term in ("日志", "监控", "指标", "回滚", "缓存", "数据库", "链路", "压测", "trace", "sql", "qps"))
        ownership = any(term in answer for term in ("我负责", "我设计", "我实现", "我排查", "我推动"))
        score = min(0.95, 0.42 + min(len(answer), 240) / 1200 + technical_terms * 0.045 + measurable * 0.09 + ownership * 0.08)
        return {
            "evidence_id": f"answer_{index}",
            "stage": stage,
            "type": "answer",
            "content": answer,
            "quality_score": round(score, 2),
            "signals": {"measurable": measurable, "technical_term_count": technical_terms, "ownership": ownership},
            "confidence": round(min(0.92, score), 2),
        }

    def _project_verification(self, answer: str) -> dict:
        evidence = self._answer_evidence("resume_probe", answer, 0)
        return {
            "credibility_score": round(evidence["quality_score"] * 100),
            "has_ownership_boundary": evidence["signals"]["ownership"],
            "has_measurable_result": evidence["signals"]["measurable"],
            "needs_follow_up": evidence["quality_score"] < 0.7,
        }

    def _extract_resume_skills(self, resume: str) -> list[dict]:
        candidates = ["Java", "Spring Boot", "MySQL", "Redis", "RabbitMQ", "Docker", "Kubernetes", "Python", "Flink", "Kafka", "RAG", "LangGraph", "MQTT"]
        return [{"name": skill, "level": "intermediate", "evidence": "档案文本命中"} for skill in candidates if skill.lower() in resume.lower()]

    def _extract_projects(self, resume: str) -> list[dict]:
        names = re.findall(r"([\u4e00-\u9fffA-Za-z0-9]+(?:系统|平台|服务|项目))", resume)
        return [{"name": name, "evidence": "档案文本", "verification_status": "pending"} for name in list(dict.fromkeys(names))[:5]]

    def _append_skill(self, session: AssessmentSession, name: str, level: str, answer: str) -> None:
        session.candidate_profile.setdefault("skills", []).append({"name": name, "level": level, "evidence": answer})

    def _level_from_score(self, score: float) -> str:
        if score >= 0.82:
            return "advanced"
        if score >= 0.62:
            return "intermediate"
        return "basic"

    def _game_signals(self, events: list[dict]) -> list[dict]:
        blob = " ".join(f"{event.get('type', '')} {event.get('value', '')}" for event in events).lower()
        signals = []
        checks = [
            (("observability", "trace", "lineage", "eval_set", "ab_trace", "topic"), "证据驱动", "优先建立可验证证据链"),
            (("testing", "测试", "regression", "quality_gate", "edge_cases"), "质量意识", "为验证和质量保障分配资源"),
            (("communication", "沟通", "contract_sync", "freeze_downstream", "transparent"), "协作升级", "主动同步影响面并触发协作"),
            (("rollback", "回滚", "止损", "quarantine", "gate_release", "freeze"), "风险控制", "及时选择可逆的止损动作"),
            (("canary", "gray", "灰度", "分级", "gate_release", "parallel_versions"), "渐进发布", "采用分级、灰度或双版本策略降低不确定性"),
        ]
        for terms, name, evidence in checks:
            if any(term in blob for term in terms):
                signals.append({"name": name, "level": "strong", "evidence": evidence})
        if not signals:
            signals.append({"name": "任务规划", "level": "medium", "evidence": "完成资源分配与决策任务"})
        return signals

    def _skill_score(self, level: str) -> int:
        return {"basic": 45, "intermediate": 68, "advanced": 84, "expert": 95}.get(level, 60)

    def _experience_years(self, resume: str) -> float | None:
        match = re.search(r"([一二三四五六七八九十\d]+)年", resume)
        if not match:
            return None
        chinese = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
        return float(chinese.get(match.group(1), int(match.group(1)) if match.group(1).isdigit() else 0))

    def _education(self, resume: str) -> str | None:
        return next((level for level in ("博士", "硕士", "本科", "大专") if level in resume), None)

    def _competency_dimensions(self, skills: list[dict], behavior: list[dict]) -> list[dict]:
        names = {skill.get("name") for skill in skills}
        return [
            {"name": "专业技术", "score": min(95, 45 + len(names) * 5), "evidence_count": len(skills)},
            {"name": "工程实践", "score": 82 if {"Docker", "Kubernetes", "技术原理与工程深度"} & names else 65, "evidence_count": sum(name in names for name in ("Docker", "Kubernetes", "技术原理与工程深度"))},
            {"name": "问题解决", "score": 82 if "复杂场景决策" in names else 62, "evidence_count": sum(skill.get("name") == "复杂场景决策" for skill in skills)},
            {"name": "行为素质", "score": min(92, 58 + len(behavior) * 9), "evidence_count": len(behavior)},
        ]
