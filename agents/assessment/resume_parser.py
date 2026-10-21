from __future__ import annotations

import copy
from dataclasses import dataclass
import hashlib
import json
import os
import re
from time import perf_counter
from typing import Any

from agents.llm import OpenAICompatibleClient, OpenAICompatibleVisionClient


@dataclass(frozen=True)
class SkillAlias:
    canonical: str
    category: str
    aliases: tuple[str, ...]


SKILL_ALIASES = [
    SkillAlias("Java", "programming_language", ("java",)),
    SkillAlias("Python", "programming_language", ("python",)),
    SkillAlias("C", "programming_language", ("c language", "c语言")),
    SkillAlias("C++", "programming_language", ("c++", "cpp")),
    SkillAlias("Go", "programming_language", ("go", "golang")),
    SkillAlias("JavaScript", "programming_language", ("javascript", "js")),
    SkillAlias("TypeScript", "programming_language", ("typescript", "ts")),
    SkillAlias("SQL", "database", ("sql",)),
    SkillAlias("MySQL", "database", ("mysql",)),
    SkillAlias("PostgreSQL", "database", ("postgresql", "postgres")),
    SkillAlias("Redis", "database", ("redis",)),
    SkillAlias("MongoDB", "database", ("mongodb", "mongo")),
    SkillAlias("Elasticsearch", "database", ("elasticsearch", "elastic search", "es")),
    SkillAlias("ClickHouse", "database", ("clickhouse",)),
    SkillAlias("HBase", "database", ("hbase",)),
    SkillAlias("Spring Boot", "backend_framework", ("spring boot", "springboot")),
    SkillAlias("Spring Cloud", "backend_framework", ("spring cloud",)),
    SkillAlias("FastAPI", "backend_framework", ("fastapi",)),
    SkillAlias("Django", "backend_framework", ("django",)),
    SkillAlias("Flask", "backend_framework", ("flask",)),
    SkillAlias("Node.js", "backend_framework", ("node.js", "nodejs", "node")),
    SkillAlias("React", "frontend_framework", ("react", "react.js", "reactjs")),
    SkillAlias("Vue", "frontend_framework", ("vue", "vue.js", "vuejs")),
    SkillAlias("Kafka", "middleware", ("kafka",)),
    SkillAlias("RabbitMQ", "middleware", ("rabbitmq", "rabbit mq")),
    SkillAlias("RocketMQ", "middleware", ("rocketmq", "rocket mq")),
    SkillAlias("Nacos", "middleware", ("nacos",)),
    SkillAlias("Sentinel", "middleware", ("sentinel",)),
    SkillAlias("Docker", "devops", ("docker",)),
    SkillAlias("Kubernetes", "devops", ("kubernetes", "k8s")),
    SkillAlias("CI/CD", "devops", ("ci/cd", "cicd", "continuous integration")),
    SkillAlias("Git", "devops", ("git",)),
    SkillAlias("Nginx", "devops", ("nginx",)),
    SkillAlias("Prometheus", "observability", ("prometheus",)),
    SkillAlias("Grafana", "observability", ("grafana",)),
    SkillAlias("OpenTelemetry", "observability", ("opentelemetry", "otel")),
    SkillAlias("Jaeger", "observability", ("jaeger",)),
    SkillAlias("Flink", "big_data", ("flink",)),
    SkillAlias("Spark", "big_data", ("spark",)),
    SkillAlias("Hive", "big_data", ("hive",)),
    SkillAlias("Hadoop", "big_data", ("hadoop",)),
    SkillAlias("Airflow", "big_data", ("airflow",)),
    SkillAlias("RAG", "ai_engineering", ("rag", "retrieval augmented generation", "检索增强")),
    SkillAlias("LangChain", "ai_engineering", ("langchain",)),
    SkillAlias("LangGraph", "ai_engineering", ("langgraph",)),
    SkillAlias("LLM", "ai_engineering", ("llm", "大模型", "large language model")),
    SkillAlias("PyTorch", "ai_engineering", ("pytorch", "torch")),
    SkillAlias("TensorFlow", "ai_engineering", ("tensorflow",)),
    SkillAlias("Transformers", "ai_engineering", ("transformers", "huggingface", "hugging face")),
    SkillAlias("NLP", "ai_engineering", ("nlp", "自然语言处理")),
    SkillAlias("OCR", "ai_engineering", ("ocr",)),
    SkillAlias("LoRA", "ai_engineering", ("lora",)),
    SkillAlias("Fine-tuning", "ai_engineering", ("fine-tuning", "finetuning", "微调", "大模型微调")),
    SkillAlias("Agent orchestration", "ai_engineering", ("agent 编排", "多智能体", "multi-agent", "agent orchestration")),
    SkillAlias("Vector Database", "ai_engineering", ("向量数据库", "vector database")),
    SkillAlias("Milvus", "ai_engineering", ("milvus",)),
    SkillAlias("FAISS", "ai_engineering", ("faiss",)),
    SkillAlias("ChromaDB", "ai_engineering", ("chromadb", "chroma")),
    SkillAlias("Prompt Engineering", "ai_engineering", ("prompt engineering", "提示词", "prompt工程")),
    SkillAlias("MQTT", "iot", ("mqtt",)),
    SkillAlias("Edge Computing", "iot", ("边缘计算", "edge computing")),
    SkillAlias("Device Shadow", "iot", ("设备影子", "device shadow")),
    SkillAlias("Linux", "os", ("linux",)),
    SkillAlias("C#", "programming_language", ("c#", "csharp")),
    SkillAlias("HTML", "frontend", ("html", "html5")),
    SkillAlias("CSS", "frontend", ("css", "css3")),
    SkillAlias("ROS", "robotics", ("ros",)),
    SkillAlias("ROS 2", "robotics", ("ros 2", "ros2")),
    SkillAlias("OpenCV", "computer_vision", ("opencv",)),
    SkillAlias("YOLO", "computer_vision", ("yolo", "yolov8")),
    SkillAlias("ONNX", "ai_engineering", ("onnx",)),
    SkillAlias("ONNX Runtime", "ai_engineering", ("onnx runtime", "onnxruntime")),
    SkillAlias("A/B测试", "data_science", ("a/b测试", "a/b test", "ab测试")),
    SkillAlias("Pandas", "data_science", ("pandas",)),
    SkillAlias("NumPy", "data_science", ("numpy",)),
    SkillAlias("Matplotlib", "data_visualization", ("matplotlib",)),
    SkillAlias("Kubernetes", "devops", ("kubernetes", "k8s")),
    SkillAlias("MyBatis", "backend_framework", ("mybatis",)),
    SkillAlias("Unity", "game_engine", ("unity", "unity3d", "u3d")),
    SkillAlias("Protobuf", "protocol", ("protobuf",)),
    SkillAlias("Shell", "programming_language", ("shell", "shell script")),
    SkillAlias("Tkinter", "frontend", ("tkinter",)),
    SkillAlias("Excel", "productivity", ("excel",)),
    SkillAlias("Git", "devops", ("git", "git软件")),
]

SKILL_ALIASES.extend(
    [
        SkillAlias("RAG", "ai_engineering", ("检索增强生成", "检索增强", "知识库问答")),
        SkillAlias("LLM", "ai_engineering", ("大模型", "大语言模型")),
        SkillAlias("Fine-tuning", "ai_engineering", ("微调", "模型微调")),
        SkillAlias("Agent orchestration", "ai_engineering", ("agent 编排", "智能体编排", "多智能体", "工具调用")),
        SkillAlias("Vector Database", "ai_engineering", ("向量数据库", "向量检索")),
        SkillAlias("Prompt Engineering", "ai_engineering", ("提示词", "提示词工程", "prompt")),
        SkillAlias("Edge Computing", "iot", ("边缘计算", "端侧推理")),
        SkillAlias("Device Shadow", "iot", ("设备影子",)),
    ]
)


class ResumeParseError(RuntimeError):
    pass


class ResumeParsingAgent:
    """Extracts auditable candidate signals from resume text."""

    def __init__(
        self,
        llm: OpenAICompatibleClient | None = None,
        vision_llm: OpenAICompatibleVisionClient | None = None,
        resume_llm_source: str | None = None,
    ) -> None:
        injected_llm = llm is not None
        self.llm = llm or OpenAICompatibleClient()
        self.vision_llm = vision_llm or OpenAICompatibleVisionClient()
        configured_source = (resume_llm_source or os.getenv("TALENTGRAPH_RESUME_LLM_SOURCE", "main")).strip().lower()
        self.resume_llm_source = "main" if injected_llm and resume_llm_source is None else configured_source
        self.resume_llm = self.vision_llm if self.resume_llm_source == "vision" else self.llm
        self.resume_timeout_seconds = self._env_float(
            "TALENTGRAPH_RESUME_LLM_TIMEOUT_SECONDS",
            float(getattr(self.resume_llm, "timeout_seconds", 180.0)),
        )
        self.resume_retries = self._env_nonnegative_int("TALENTGRAPH_RESUME_LLM_RETRIES", 0)
        self.resume_max_tokens = self._env_int("TALENTGRAPH_RESUME_LLM_MAX_TOKENS", 1400)
        self.resume_repair_max_tokens = self._env_int(
            "TALENTGRAPH_RESUME_LLM_REPAIR_MAX_TOKENS",
            max(3000, self.resume_max_tokens),
        )
        self.resume_input_chars = self._env_int("TALENTGRAPH_RESUME_LLM_INPUT_CHARS", 4200)
        self._parse_cache: dict[str, dict[str, Any]] = {}

    def parse(
        self,
        resume_text: str,
        *,
        candidate_id: str | None = None,
        source_name: str = "resume_text",
        images: list[dict[str, str]] | None = None,
        require_remote: bool = False,
        use_remote: bool = True,
    ) -> dict[str, Any]:
        text = self._normalize_text(resume_text)
        should_parse_images = bool(images) and (use_remote or not text)
        vision = self._parse_images(images or [], source_name=source_name) if should_parse_images else {
            "used": False,
            "image_count": len(images or []),
            "extracted_text": "",
            "layout_notes": [],
            "visual_evidence": [],
            "provider_status": self.vision_llm.status(),
        }
        if require_remote and images and vision.get("provider_status", {}).get("fallback") and not text:
            reason = vision.get("provider_status", {}).get("reason", "vision_parse_failed")
            raise ResumeParseError(f"视觉简历解析失败，请重新解析或换一份文字更清晰的简历：{reason}")
        if vision.get("extracted_text"):
            text = self._normalize_text("\n".join([text, str(vision["extracted_text"])]))
        fallback = self._deterministic_parse(text, candidate_id=candidate_id, source_name=source_name)
        fallback["vision_parse"] = self._public_vision_parse(vision)
        if not text:
            if require_remote:
                raise ResumeParseError("未提取到可读简历文本，请重新解析或换一份文字更清晰的简历")
            return fallback
        if not use_remote:
            return fallback
        if not self.resume_llm.configured:
            if require_remote:
                raise ResumeParseError("简历解析模型未配置，请检查模型环境变量后重新解析")
            return fallback

        cache_key = self._cache_key(text, source_name)
        if cache_key in self._parse_cache:
            cached = copy.deepcopy(self._parse_cache[cache_key])
            cached["candidate_id"] = candidate_id
            cached["source_name"] = source_name
            provider_status = cached.setdefault("provider_status", {})
            provider_status["cache_hit"] = True
            provider_status["duration_ms"] = 0
            cached["parse_timing"] = {
                **cached.get("parse_timing", {}),
                "resume_llm_ms": 0,
                "cache_hit": True,
            }
            return cached

        compact_text, compact_stats = self._compact_resume_for_llm(text, limit=self.resume_input_chars)
        llm_started = perf_counter()
        system_prompt = self._resume_llm_system_prompt()
        user_prompt = self._resume_llm_user_prompt(compact_text, fallback)
        result = self.resume_llm.generate_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            fallback=fallback,
            timeout_seconds=self.resume_timeout_seconds,
            retries=self.resume_retries,
            max_tokens=self.resume_max_tokens,
            disable_thinking=True,
        )
        resume_llm_ms = int(result.provider_status.get("duration_ms") or round((perf_counter() - llm_started) * 1000))
        if result.provider_status.get("fallback") and self._should_retry_resume_json(result.provider_status):
            repair_text, repair_stats = self._compact_resume_for_llm(text, limit=min(self.resume_input_chars, 2800))
            repair = self.resume_llm.generate_json(
                system_prompt=(
                    f"{system_prompt} The previous response was invalid JSON. Retry once. "
                    "Return compact valid JSON only, with no markdown, no comments, no trailing commas, "
                    "and no extra text. Keep evidence strings under 80 characters and limit skills/projects "
                    "to the most important supported items."
                ),
                user_prompt=self._resume_llm_user_prompt(repair_text, fallback),
                fallback=fallback,
                timeout_seconds=self.resume_timeout_seconds,
                retries=self.resume_retries,
                max_tokens=self.resume_repair_max_tokens,
                disable_thinking=True,
            )
            resume_llm_ms += int(repair.provider_status.get("duration_ms") or 0)
            repair.provider_status["json_repair_retry"] = True
            repair.provider_status["first_error"] = result.provider_status.get("reason")
            result = repair
            compact_stats = repair_stats
            user_prompt = self._resume_llm_user_prompt(repair_text, fallback)
        result.provider_status["prompt_mode"] = "compact_resume_summary"
        result.provider_status["user_prompt_chars"] = len(user_prompt)
        if result.provider_status.get("fallback"):
            if require_remote:
                reason = result.provider_status.get("reason", "remote_resume_parse_failed")
                if "Timeout" in str(reason) or "timed out" in str(reason):
                    raise ResumeParseError(
                        f"简历文本已读取，但大模型理解超时。请稍后重试，或在环境变量 TALENTGRAPH_RESUME_LLM_TIMEOUT_SECONDS 中调大等待时间：{reason}"
                    )
                raise ResumeParseError(f"简历解析模型调用失败，请检查模型服务状态后重新解析：{reason}")
            fallback["provider_status"] = result.provider_status
            fallback["provider_status"]["cache_hit"] = False
            fallback["provider_status"]["compact_input_chars"] = compact_stats["compact_input_chars"]
            fallback["provider_status"]["original_input_chars"] = compact_stats["original_input_chars"]
            fallback["parse_timing"] = {"resume_llm_ms": resume_llm_ms, "cache_hit": False}
            return fallback
        merged = self._merge_llm_result(fallback, result.data, text)
        merged["provider_status"] = result.provider_status
        merged["provider_status"]["mode"] = "llm_resume_understanding"
        merged["provider_status"]["cache_hit"] = False
        merged["provider_status"]["compact_input_chars"] = compact_stats["compact_input_chars"]
        merged["provider_status"]["original_input_chars"] = compact_stats["original_input_chars"]
        merged["parse_timing"] = {"resume_llm_ms": resume_llm_ms, "cache_hit": False}
        merged["vision_parse"] = self._public_vision_parse(vision)
        self._parse_cache[cache_key] = copy.deepcopy(merged)
        return merged

    def _cache_key(self, text: str, source_name: str) -> str:
        normalized = self._normalize_text(text).lower()
        payload = f"{source_name.strip().lower()}\n{normalized}".encode("utf-8", errors="ignore")
        return hashlib.sha256(payload).hexdigest()

    def _should_retry_resume_json(self, provider_status: dict[str, Any]) -> bool:
        reason = str(provider_status.get("reason", ""))
        return "JSONDecodeError" in reason or "LLM JSON response" in reason

    def _resume_llm_system_prompt(self) -> str:
        return (
            "You are a fast resume understanding agent. Return one compact valid JSON object only. "
            "Required keys: skills, projects, experience_years, education, certifications, "
            "preferred_locations, expected_salary_k, work_history, semantic_profile. Keep output small: max 10 skills, "
            "max 4 projects, max 4 work_history items, evidence strings <= 60 chars, metrics <= 3 per project. "
            "Extract only facts supported by the supplied snippets. semantic_profile should summarize project capabilities, "
            "skill usage judgments, role graph mappings, and interview focus points from the evidence. Do not infer sensitive attributes. "
            "Use [] or null when evidence is absent. No markdown, no comments, no extra text."
        )

    def _resume_llm_user_prompt(self, compact_text: str, fallback: dict[str, Any]) -> str:
        payload = {
            "task": "calibrate_resume_parse_from_snippets",
            "schema_limits": {
                "skills_max": 10,
                "projects_max": 4,
                "work_history_max": 4,
                "evidence_chars_max": 60,
            },
            "deterministic_hints": {
                "skills": [
                    {
                        "name": item.get("name"),
                        "evidence": str(item.get("evidence", ""))[:80],
                    }
                    for item in fallback.get("skills", [])[:12]
                    if isinstance(item, dict) and item.get("name")
                ],
                "projects": [
                    {
                        "name": item.get("name"),
                        "evidence": str(item.get("evidence", ""))[:100],
                    }
                    for item in fallback.get("projects", [])[:6]
                    if isinstance(item, dict) and item.get("name")
                ],
                "experience_years": fallback.get("experience_years"),
                "education": fallback.get("education"),
                "certifications": fallback.get("certifications", [])[:6],
                "preferred_locations": fallback.get("preferred_locations", [])[:4],
                "expected_salary_k": fallback.get("expected_salary_k", [])[:2],
                "job_intent": fallback.get("job_intent"),
                "city_preferences": fallback.get("city_preferences", [])[:4],
                "skill_evidence": [
                    {
                        "name": item.get("name"),
                        "usage_status": item.get("usage_status"),
                        "occurrences": item.get("occurrences", [])[:2],
                    }
                    for item in fallback.get("skills", [])[:12]
                    if isinstance(item, dict) and item.get("name")
                ],
            },
            "resume_snippets": compact_text,
        }
        return json.dumps(payload, ensure_ascii=False, default=str)

    def _compact_resume_for_llm(self, text: str, *, limit: int | None = None) -> tuple[str, dict[str, int]]:
        target = max(1800, min(int(limit or 4200), 8000))
        normalized = self._normalize_text(text)
        if len(normalized) <= target:
            return normalized, {"original_input_chars": len(normalized), "compact_input_chars": len(normalized)}

        keywords = (
            "skill", "skills", "project", "projects", "experience", "education", "certificate", "certification",
            "work", "job", "intern", "stack", "achievement", "metric", "salary", "location",
            "技能", "技术", "项目", "经历", "经验", "工作", "实习", "教育", "学历", "学校", "专业",
            "证书", "认证", "求职", "意向", "期望", "薪资", "城市", "职责", "成果", "指标", "优化",
            "开发", "负责", "参与", "主导", "平台", "系统", "模型", "算法", "数据",
        )
        lines = [line.strip() for line in normalized.splitlines() if line.strip()]
        kept: list[str] = []
        seen: set[str] = set()

        def add_line(line: str) -> None:
            key = re.sub(r"\s+", "", line.lower())
            if key and key not in seen:
                seen.add(key)
                kept.append(line[:520])

        for line in lines[:18]:
            add_line(line)
        for line in lines:
            lower = line.lower()
            if any(keyword in lower or keyword in line for keyword in keywords):
                add_line(line)
        for line in lines:
            if len("\n".join(kept)) >= target:
                break
            if re.search(r"\d+(?:\.\d+)?\s*(?:年|years?|yrs?|k|K|%|ms|万|人|次|小时|h)", line):
                add_line(line)

        compact = "\n".join(kept).strip()
        if len(compact) < min(1200, target // 2):
            compact = "\n".join([compact, normalized[:target]]).strip()
        compact = compact[:target]
        return compact, {"original_input_chars": len(normalized), "compact_input_chars": len(compact)}

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

    def _env_nonnegative_int(self, name: str, default: int) -> int:
        raw = os.getenv(name, "").strip()
        if not raw:
            return default
        try:
            value = int(raw)
        except ValueError:
            return default
        return value if value >= 0 else default

    def _public_vision_parse(self, vision: dict[str, Any]) -> dict[str, Any]:
        status = vision.get("provider_status", {}) if isinstance(vision.get("provider_status"), dict) else {}
        public_status = {
            "configured": bool(status.get("configured")),
            "ok": status.get("ok"),
            "fallback": status.get("fallback"),
            "reason": status.get("reason"),
        }
        return {
            "used": bool(vision.get("used")),
            "image_count": int(vision.get("image_count") or 0),
            "extracted_text": str(vision.get("extracted_text", ""))[:12000],
            "layout_notes": list(vision.get("layout_notes") or [])[:12],
            "visual_evidence": list(vision.get("visual_evidence") or [])[:20],
            "provider_status": {key: value for key, value in public_status.items() if value is not None},
        }

    def _parse_images(self, images: list[dict[str, str]], *, source_name: str) -> dict[str, Any]:
        status = self.vision_llm.status()
        if not images:
            return {"used": False, "image_count": 0, "provider_status": status}
        fallback = {
            "used": False,
            "image_count": len(images),
            "extracted_text": "",
            "layout_notes": [],
            "visual_evidence": [],
        }
        result = self.vision_llm.generate_json_with_images(
            system_prompt=(
                "You are a multimodal resume OCR and layout understanding agent. Return only one JSON object "
                "with keys: extracted_text, layout_notes, visual_evidence. Extract all readable resume text, "
                "tables, timelines, certificates, project names, skill badges, and chart labels. Do not invent "
                "content that is not visible."
            ),
            text_prompt=(
                f"Parse resume source {source_name}. Keep Chinese and English text as-is. "
                "If a field is unreadable, omit it instead of guessing."
            ),
            images=images[:3],
            fallback=fallback,
        )
        data = result.data if isinstance(result.data, dict) else fallback
        return {
            "used": not result.provider_status.get("fallback", False),
            "image_count": len(images),
            "extracted_text": str(data.get("extracted_text", ""))[:12000],
            "layout_notes": [str(item) for item in data.get("layout_notes", [])][:12] if isinstance(data.get("layout_notes"), list) else [],
            "visual_evidence": [item for item in data.get("visual_evidence", []) if isinstance(item, dict)][:20]
            if isinstance(data.get("visual_evidence"), list)
            else [],
            "provider_status": result.provider_status,
        }

    def _deterministic_parse(self, text: str, *, candidate_id: str | None, source_name: str) -> dict[str, Any]:
        skills = self._extract_skills(text)
        projects = self._extract_projects(text, skills)
        experience_years = self._extract_experience_years(text)
        education = self._extract_education(text)
        certifications = self._extract_certifications(text)
        preferred_locations = self._extract_locations(text)
        expected_salary_k = self._extract_salary(text)
        job_intent = self._extract_job_intent(text)
        evidence = self._build_evidence(text, skills, projects)
        quality = self._quality_summary(text, skills, projects, evidence)
        parsed = {
            "candidate_id": candidate_id,
            "source_name": source_name,
            "job_intent": job_intent,
            "skills": skills,
            "supplemental_skills": self._extract_supplemental_skills(text, skills),
            "projects": projects,
            "experience_years": experience_years,
            "education": education,
            "certifications": certifications,
            "certification_count": len(certifications),
            "preferred_locations": preferred_locations,
            "city_preferences": preferred_locations,
            "expected_salary_k": expected_salary_k,
            "work_history": self._extract_work_history(text),
            "evidence": evidence,
            "quality_summary": quality,
            "provider_status": {
                "provider": "deterministic-resume-parser",
                "configured": False,
                "model": None,
                "mode": "deterministic_fallback",
            },
        }
        parsed["semantic_profile"] = self._deterministic_semantic_profile(parsed)
        return parsed

    def _extract_supplemental_skills(self, text: str, core_skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep project/work evidence visible without adding it to scored core skills."""
        core_keys = {self._compact_for_match(item.get("name", "")) for item in core_skills}
        evidence_area = "\n".join(
            self._section_text(text, headings)
            for headings in (("项目经历", "项目经验", "Projects", "Project"), ("工作经历", "工作", "实习", "Experience", "Work"))
        )
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for alias in self._skill_alias_catalog():
            matched = next((item for item in alias.aliases if self._contains_alias(evidence_area, item)), None)
            if not matched:
                continue
            key = self._compact_for_match(alias.canonical)
            if key in core_keys or key in seen:
                continue
            evidence = self._evidence_window(text, matched)
            if not evidence:
                continue
            seen.add(key)
            result.append({
                "name": alias.canonical,
                "canonical_name": alias.canonical,
                "category": alias.category,
                "evidence": evidence,
                "occurrences": self._skill_occurrences(text, matched, fallback=evidence),
                "usage_status": self._skill_usage_status(text, matched, evidence),
                "confidence": self._skill_confidence(evidence),
            })
        return result[:20]

    def _merge_llm_result(self, fallback: dict[str, Any], data: dict[str, Any], text: str) -> dict[str, Any]:
        merged = dict(fallback)
        experience_years = self._clean_experience_years(data.get("experience_years"))
        if experience_years is not None:
            merged["experience_years"] = experience_years
        education = self._clean_education(data.get("education"))
        if education and self._supported_by_text(text, education, education):
            merged["education"] = education
        for key in ("certifications", "preferred_locations", "expected_salary_k", "work_history"):
            if isinstance(data.get(key), list):
                merged[key] = data[key]
        merged["job_intent"] = self._clean_text_value(data.get("job_intent")) or fallback.get("job_intent")
        merged["certification_count"] = len(merged.get("certifications") or [])
        merged["city_preferences"] = list(merged.get("preferred_locations") or [])
        extra_skills = data.get("skills", []) if isinstance(data.get("skills"), list) else []
        core_extra = []
        supplemental_extra = []
        for item in extra_skills:
            if not isinstance(item, dict) or not item.get("name"):
                continue
            raw_name = str(item["name"]).strip()
            name = self._canonical_skill_token(raw_name)
            (core_extra if self._is_explicit_skill_name(raw_name, name, text) else supplemental_extra).append(item)
        merged["skills"] = self._merge_skills(fallback.get("skills", []), core_extra, text)
        merged["supplemental_skills"] = self._merge_supplemental_skills(
            fallback.get("supplemental_skills", []), supplemental_extra, text, merged["skills"]
        )
        merged["projects"] = self._merge_projects(fallback.get("projects", []), data.get("projects", []), text)
        merged["semantic_profile"] = self._merge_semantic_profile(data.get("semantic_profile"), merged)
        merged["evidence"] = self._build_evidence(
            text,
            merged["skills"],
            merged["projects"],
        ) or fallback["evidence"]
        merged["quality_summary"] = self._quality_summary(text, merged["skills"], merged["projects"], merged["evidence"])
        return merged

    def _merge_skills(self, base: list[dict[str, Any]], extra: Any, text: str) -> list[dict[str, Any]]:
        skills_by_name = {
            self._compact_for_match(str(item.get("name", ""))): dict(item)
            for item in base if item.get("name")
        }
        if isinstance(extra, list):
            for item in extra:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                raw_name = str(item["name"]).strip()
                name = self._canonical_skill_token(raw_name)
                if not self._looks_like_skill_token(raw_name) or not self._looks_like_skill_token(name):
                    continue
                evidence = str(item.get("evidence", "")).strip()
                if not evidence or not self._supported_by_text(text, raw_name, evidence):
                    continue
                key = self._compact_for_match(name)
                alias = self._skill_alias_for_name(name)
                skills_by_name.setdefault(
                    key,
                    {
                        "name": name,
                        "canonical_name": name,
                        "category": alias.category if alias else str(item.get("category", "unknown")),
                        "level": self._clean_level(item.get("level")),
                        "evidence": evidence[:240],
                        "occurrences": self._skill_occurrences(text, raw_name, fallback=evidence),
                        "usage_status": self._skill_usage_status(text, raw_name, evidence),
                        "confidence": self._bounded_float(item.get("confidence"), default=0.68),
                    },
                )
        for skill in skills_by_name.values():
            evidence = str(skill.get("evidence", ""))
            skill.setdefault("occurrences", self._skill_occurrences(text, str(skill.get("name", "")), fallback=evidence))
            skill.setdefault("usage_status", self._skill_usage_status(text, str(skill.get("name", "")), evidence))
        return sorted(skills_by_name.values(), key=lambda item: (-float(item.get("confidence", 0)), item["name"]))

    def _merge_supplemental_skills(
        self, base: list[dict[str, Any]], extra: list[dict[str, Any]], text: str, core: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        core_keys = {self._compact_for_match(str(item.get("name", ""))) for item in core if item.get("name")}
        result = {
            self._compact_for_match(str(item.get("name", ""))): dict(item)
            for item in base
            if item.get("name") and self._compact_for_match(str(item.get("name", ""))) not in core_keys
        }
        for item in extra:
            raw_name = str(item.get("name", "")).strip()
            name = self._canonical_skill_token(raw_name)
            evidence = str(item.get("evidence", "")).strip()
            if not name or not self._looks_like_skill_token(raw_name) or not evidence or not self._supported_by_text(text, raw_name, evidence):
                continue
            key = self._compact_for_match(name)
            if key in core_keys or key in result:
                continue
            alias = self._skill_alias_for_name(name)
            result[key] = {
                "name": name,
                "canonical_name": name,
                "category": alias.category if alias else str(item.get("category", "unknown")),
                "evidence": evidence[:240],
                "occurrences": self._skill_occurrences(text, raw_name, fallback=evidence),
                "usage_status": self._skill_usage_status(text, raw_name, evidence),
                "confidence": self._bounded_float(item.get("confidence"), default=0.65),
            }
        return sorted(result.values(), key=lambda item: (-float(item.get("confidence", 0)), item["name"]))[:20]

    def _is_explicit_skill_name(self, raw_name: str, canonical_name: str, text: str) -> bool:
        skills_section = self._section_text(
            text, ("技能", "技能栏", "核心技能", "技能栈", "技术栈", "专业技能", "技术能力", "职业技能", "工作技能")
        )
        if skills_section:
            alias = self._skill_alias_for_name(canonical_name)
            candidates = (raw_name, canonical_name) + (alias.aliases if alias else ())
            return any(self._contains_alias(skills_section, candidate) for candidate in candidates if candidate)
        evidence_area = "\n".join(
            self._section_text(text, headings)
            for headings in (("项目经历", "项目经验", "Projects", "Project"), ("工作经历", "工作", "实习", "Experience", "Work"))
        )
        return not any(self._contains_alias(evidence_area, candidate) for candidate in (raw_name, canonical_name) if candidate)

    def _merge_projects(self, base: list[dict[str, Any]], extra: Any, text: str) -> list[dict[str, Any]]:
        projects_by_name = {str(item.get("name", "")).lower(): dict(item) for item in base if item.get("name")}
        if isinstance(extra, list):
            for item in extra:
                if not isinstance(item, dict) or not item.get("name"):
                    continue
                name = str(item["name"]).strip()
                if not self._looks_like_project_name(name):
                    continue
                evidence = str(item.get("evidence", "")).strip()
                if not self._supported_by_text(text, name, evidence):
                    continue
                projects_by_name.setdefault(
                    name.lower(),
                    {
                        "name": name,
                        "role": str(item.get("role", ""))[:120],
                        "tech_stack": [str(skill) for skill in item.get("tech_stack", []) if str(skill).strip()][:10],
                        "metrics": [str(metric) for metric in item.get("metrics", []) if str(metric).strip()][:8],
                        "evidence": evidence[:300],
                        "verification_status": str(item.get("verification_status", "pending")),
                    },
                )
        return list(projects_by_name.values())[:8]

    def _extract_skills(self, text: str) -> list[dict[str, Any]]:
        skills_section = self._section_text(text, ("技能", "技能栏", "核心技能", "技能栈", "技术栈", "专业技能", "技术能力", "职业技能", "工作技能", "技能概况", "技能特长", "技能&证书"))
        search_area = skills_section or text
        skills_by_name: dict[str, dict[str, Any]] = {}
        for alias in self._skill_alias_catalog():
            matched_alias = next((item for item in alias.aliases if self._contains_alias(search_area, item)), None)
            if not matched_alias and not skills_section:
                matched_alias = next((item for item in alias.aliases if self._contains_alias(text, item)), None)
            if matched_alias and self._alias_is_shadowed(search_area, matched_alias):
                matched_alias = None
            if not matched_alias:
                continue
            evidence = self._evidence_window(text, matched_alias)
            if not evidence and skills_section:
                evidence = skills_section[:240]
            confidence = self._skill_confidence(evidence)
            occurrences = self._skill_occurrences(text, matched_alias, fallback=evidence)
            if skills_section and self._contains_alias(skills_section, matched_alias):
                confidence = round(min(0.95, confidence + 0.06), 2)
            skills_by_name[self._compact_for_match(alias.canonical)] = {
                    "name": alias.canonical,
                    "canonical_name": alias.canonical,
                    "category": alias.category,
                    "level": self._infer_skill_level(text, matched_alias),
                    "evidence": evidence,
                    "occurrences": occurrences,
                    "usage_status": self._skill_usage_status(text, matched_alias, evidence, skills_section=skills_section),
                    "confidence": confidence,
            }
        for token in self._skill_section_tokens(skills_section):
            canonical = self._canonical_skill_token(token)
            key = self._compact_for_match(canonical)
            if not canonical or key in skills_by_name:
                continue
            skills_by_name[key] = {
                "name": canonical,
                "canonical_name": canonical,
                "category": "technical_skill",
                "level": self._infer_skill_level(text, token),
                "evidence": self._evidence_window(text, token) or skills_section[:240],
                "occurrences": self._skill_occurrences(text, token, fallback=skills_section[:240]),
                "usage_status": self._skill_usage_status(text, token, self._evidence_window(text, token), skills_section=skills_section),
                "confidence": 0.78,
            }
        return sorted(skills_by_name.values(), key=lambda item: (-item["confidence"], item["name"]))

    def _skill_section_tokens(self, skills_section: str) -> list[str]:
        if not skills_section:
            return []
        normalized = re.sub(r"[；;，,、|]+", "\n", skills_section)
        lines = []
        for raw_line in normalized.splitlines():
            # Preserve compound skills such as A/B测试 and CI/CD.
            raw_token = raw_line.strip()
            known_alias = any(
                any(self._same_skill_token(raw_token, candidate) for candidate in alias.aliases)
                for alias in self._skill_alias_catalog()
            )
            if "/" in raw_line and not known_alias:
                raw_line = re.sub(r"\s*/\s*", "\n", raw_line)
            lines.append(raw_line)
        normalized = "\n".join(lines)
        tokens = []
        for raw in re.split(r"\n+", normalized):
            raw = re.sub(r"^[\s\-*•\d.、]+", "", raw).strip()
            if ":" in raw or "：" in raw:
                raw = re.split(r"[:：]", raw, maxsplit=1)[1]
            token = raw.strip(" ：:。()（）[]【】")
            token = re.sub(r"^(熟悉|掌握|精通|了解|负责|使用|具备|熟练使用)\s*", "", token)
            token = re.sub(r"(等|相关)$", "", token).strip()
            if self._looks_like_skill_token(token):
                tokens.append(token)
        return list(dict.fromkeys(tokens))[:30]

    def _canonical_skill_token(self, token: str) -> str:
        for alias in self._skill_alias_catalog():
            if any(self._same_skill_token(token, item) for item in alias.aliases) or self._same_skill_token(token, alias.canonical):
                return alias.canonical
        return token

    def _skill_alias_for_name(self, name: str) -> SkillAlias | None:
        return next((alias for alias in self._skill_alias_catalog() if self._same_skill_token(name, alias.canonical)), None)

    def _skill_alias_catalog(self) -> tuple[SkillAlias, ...]:
        merged: dict[str, SkillAlias] = {}
        for item in SKILL_ALIASES:
            key = self._compact_for_match(item.canonical)
            previous = merged.get(key)
            aliases = tuple(dict.fromkeys((*(previous.aliases if previous else ()), *item.aliases)))
            merged[key] = SkillAlias(item.canonical, item.category, tuple(sorted(aliases, key=len, reverse=True)))
        return tuple(merged.values())

    def _alias_is_shadowed(self, text: str, alias: str) -> bool:
        short = self._compact_for_match(alias)
        if not short:
            return False
        for item in self._skill_alias_catalog():
            for candidate in (*item.aliases, item.canonical):
                long = self._compact_for_match(candidate)
                if len(long) <= len(short) or not long.startswith(short):
                    continue
                if self._contains_alias(text, candidate):
                    return True
        return False

    def _same_skill_token(self, left: str, right: str) -> bool:
        return self._compact_for_match(left) == self._compact_for_match(right)

    def _looks_like_skill_token(self, token: str) -> bool:
        if not token or len(token) > 40:
            return False
        if re.search(r"[。？！?]|经历|职责|负责.*(开发|建设|优化)|提升|降低|下降|\d+(?:\.\d+)?\s*%", token):
            return False
        if re.search(r"(?:命中率|准确率|召回率|成功率|延迟|人工复核量|误报率).*\d", token):
            return False
        if re.search(r"(?:接口|服务|模块|系统|功能)?(?:开发|建设|优化|描述|动作)$", token):
            return False
        if re.match(r"^(?:负责|参与|主导|使用|通过|完成|设计|实现|开发|搭建|维护|熟悉|掌握|具备|能够|擅长|采用|基于|结合|利用|针对|在|将|把)", token):
            return False
        if len(token) < 2 and not re.search(r"[A-Za-z+#]", token):
            return False
        if re.search(r"[A-Za-z0-9+#.]", token):
            return True
        return 2 <= len(token) <= 12

    def _skill_occurrences(self, text: str, term: str, *, fallback: str = "", limit: int = 3) -> list[dict[str, Any]]:
        if not term:
            return []
        lines = [line.strip() for line in self._normalize_text(text).splitlines() if line.strip()]
        occurrences: list[dict[str, Any]] = []
        for index, line in enumerate(lines, start=1):
            if not self._contains_alias(line, term):
                continue
            occurrences.append(
                {
                    "snippet": line[:240],
                    "line_index": index,
                    "section": self._guess_section(lines, index - 1),
                }
            )
            if len(occurrences) >= limit:
                break
        if not occurrences and fallback:
            occurrences.append({"snippet": fallback[:240], "line_index": None, "section": "unknown"})
        return occurrences

    def _guess_section(self, lines: list[str], line_index: int) -> str:
        headings = {
            "skills": ("技能", "技术", "专业技能", "Skills", "Skill"),
            "projects": ("项目", "项目经历", "Projects", "Project"),
            "work": ("工作", "实习", "工作经历", "Experience", "Work"),
            "education": ("教育", "学历", "Education"),
            "certification": ("证书", "认证", "Certificate", "Certification"),
            "intent": ("求职", "期望", "意向", "Job", "Objective"),
        }
        for offset in range(line_index, max(-1, line_index - 8), -1):
            line = lines[offset]
            for section, tokens in headings.items():
                if any(token.lower() in line.lower() for token in tokens):
                    return section
        return "resume"

    def _skill_usage_status(
        self,
        text: str,
        term: str,
        evidence: str,
        *,
        skills_section: str = "",
    ) -> str:
        joined = "\n".join([evidence or "", self._evidence_window(text, term, width=220)])
        if self._section_contains_alias(text, ("项目", "项目经历", "Projects", "Project"), term):
            return "project_used"
        if self._section_contains_alias(text, ("工作", "工作经历", "实习", "Experience", "Work"), term):
            return "work_used"
        if skills_section and self._contains_alias(skills_section, term):
            return "listed_only"
        if any(marker in joined for marker in ("负责", "使用", "开发", "实现", "优化", "主导", "参与", "owner", "developed", "designed")):
            return "work_used"
        return "mentioned"

    def _section_contains_alias(self, text: str, headings: tuple[str, ...], term: str) -> bool:
        section = self._section_text(text, headings)
        return bool(section and self._contains_alias(section, term))

    def _extract_projects(self, text: str, skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
        project_blocks = self._project_blocks(text)
        tech_stack = [skill["name"] for skill in skills[:10]]
        metrics = self._extract_metrics(text)
        projects = []
        seen_names: set[str] = set()
        for block in project_blocks:
            name = self._project_name(block)
            if not name:
                continue
            key = self._compact_for_match(name)
            if not key or key in seen_names:
                continue
            seen_names.add(key)
            evidence = block[:320] if block else self._evidence_window(text, name, width=180)
            projects.append(
                {
                    "name": name,
                    "role": self._extract_role(evidence),
                    "tech_stack": [skill for skill in tech_stack if self._contains_alias(evidence, skill)] or tech_stack[:5],
                    "metrics": [metric for metric in metrics if metric in evidence] or metrics[:3],
                    "evidence": evidence,
                    "verification_status": "supported" if evidence else "pending",
                }
            )
        return projects[:8]

    def _section_text(self, text: str, headings: tuple[str, ...]) -> str:
        stop_headings = (
            "基本信息",
            "个人信息",
            "教育",
            "教育经历",
            "工作",
            "工作经历",
            "实习",
            "实习经历",
            "项目",
            "项目经历",
            "项目经验",
            "项目名称",
            "技能",
            "技能栏",
            "核心技能",
            "技能栈",
            "技术栈",
            "技术能力",
            "专业技能",
            "技能证据",
            "技能证书",
            "证书",
            "证书认证",
            "期望",
            "求职意向",
            "自我评价",
            "优势",
            "合理弱点与改进",
            "校园经历",
            "社会实践",
            "校园实践",
            "个人荣誉",
            "荣誉与奖项",
            "奖项荣誉",
            "证书及荣誉",
            "证书与荣誉",
            "语言能力",
            "工作技能",
            "职业技能",
            "技能&证书",
            "项目经历/个人作品",
        )
        normalized = self._normalize_text(text)
        heading_set = {item.lower() for item in headings}

        def clean_heading(line: str) -> str:
            line = re.sub(r"^\s*(?:[•●▪▶▸]|\d+[.、)])\s*", "", line).strip()
            line = re.sub(r"\s+", "", line).rstrip(":：")
            return line.lower()

        def is_heading(line: str, candidates: tuple[str, ...]) -> bool:
            cleaned = clean_heading(line)
            return any(cleaned == candidate.lower() or cleaned.startswith(candidate.lower() + "：") for candidate in candidates)

        lines = normalized.splitlines()
        start = next((index for index, line in enumerate(lines) if is_heading(line, headings)), None)
        if start is None:
            return ""
        stop_candidates = tuple(item for item in stop_headings if item.lower() not in heading_set)
        body: list[str] = []
        for line in lines[start + 1:]:
            if is_heading(line, stop_candidates):
                break
            body.append(line)
        return "\n".join(body).strip()

    def _project_blocks(self, text: str) -> list[str]:
        has_project_section = bool(re.search(r"(?im)^\s*(?:项目经历|项目经验|项目经历/个人作品|项目经验/个人作品|Projects?|项目)\s*$", text))
        section = (
            self._section_text(text, ("项目经历", "项目经验", "项目经历/个人作品", "项目经验/个人作品", "Projects", "Project"))
            if has_project_section
            else ""
        )
        source = section or text
        blocks: list[str] = []
        if section:
            pipe_header = re.compile(r"^\s*项目\s*\d*\s*[|｜]\s*([^|｜\n]+)(?:[|｜].*)?", re.I)
            current: list[str] = []
            for line in section.splitlines():
                if pipe_header.match(line) or self._looks_like_project_header(line):
                    if current:
                        blocks.append("\n".join(current).strip())
                    current = [line.strip()]
                elif current and line.strip():
                    current.append(line.strip())
            if current:
                blocks.append("\n".join(current).strip())
            if blocks:
                return blocks[:12]
        explicit = re.finditer(
            r"(?:^|\n|[。；;])\s*(?:项目|项目名称|Project)\s*[:：]\s*(.*?)(?=(?:\n|[。；;])\s*(?:项目名称|项目|Project)\s*[:：]|\n\s*(?:工作经历|教育经历|技能|证书|求职意向|优势|合理弱点与改进)\s*[:：]?|\Z)",
            source,
            flags=re.I | re.S,
        )
        blocks.extend(match.group(1).strip() for match in explicit if match.group(1).strip())
        if not blocks and section:
            candidates = re.split(r"\n\s*(?:[-*•]|\d+[.、])\s*", section)
            blocks.extend(item.strip() for item in candidates if len(item.strip()) >= 8)
        return blocks[:12]

    def _looks_like_project_header(self, line: str) -> bool:
        if not line.strip() or line.lstrip().startswith(("•", "●", "▪", "▶", "▸", "", "", "-", "*")):
            return False
        if not re.search(r"(?:19|20)\d{2}[./年-]\d{1,2}", line):
            return False
        return not re.search(r"^(?:技术栈|项目描述|项目介绍|项目实现|背景|量化结果|成果|职责|工作动作|教育)", line.strip(), re.I)

    def _project_name(self, block: str) -> str:
        first_line = block.strip().splitlines()[0] if block.strip() else ""
        cleaned = re.sub(r"\s+", " ", first_line).strip(" ：:;-，,。")
        if re.match(r"^(?:项目|项目名称|Project)\s*[:：]", cleaned, re.I):
            cleaned = re.split(r"[。；;]", cleaned, maxsplit=1)[0]
        cleaned = re.sub(r"^\s*[（(]?[一二三四五六七八九十\d]+[）)]\s*", "", cleaned)
        date_range = r"(?:19|20)\d{2}[./年]\d{1,2}\W+(?:19|20)\d{2}[./年]\d{1,2}"
        cleaned = re.sub(rf"^\s*{date_range}\s*", "", cleaned)
        cleaned = re.sub(rf"\s+{date_range}.*$", "", cleaned)
        cleaned = re.sub(r"\s+(?:项目负责人|核心开发者|开发工程师|前端负责人|后端开发|全栈独立开发|独立开发|项目经理|项目成员)\s*$", "", cleaned)
        explicit_match = re.match(r"^(?:项目|项目名称|Project)\s*[:：]\s*([^。；;，,]{2,50})", cleaned, re.I)
        if explicit_match:
            explicit_name = explicit_match.group(1).strip(" ：:;-，,。")
            if self._looks_like_project_name(explicit_name):
                return explicit_name[:50]
        patterns = [
            r"^项目\s*\d*\s*[|｜]\s*([^|｜]{2,50})",
            r"^(?:项目|项目名称|Project)\s*[:：]\s*([^。；;，,\n]{2,50})",
            r"^([^。；;，,\n]{2,50})",
            r"^([^。；;，,\n]{2,50}(?:系统|平台|项目|中台|引擎|助手|Agent))",
        ]
        for pattern in patterns:
            match = re.search(pattern, cleaned, flags=re.I)
            if not match:
                continue
            name = match.group(1).strip(" ：:;-，,。")
            name = re.sub(r"^(参与|负责|主导|设计|实现|开发)\s*", "", name)
            if self._looks_like_project_name(name):
                return name[:50]
        return ""

    def _looks_like_project_name(self, name: str) -> bool:
        if len(name) < 2 or len(name) > 50:
            return False
        if any(marker in name for marker in ("负责", "实现", "熟悉", "了解", "编排", "部署", "链路", "接口")):
            return False
        base = re.sub(
            r"(?:[·・\s_-]*(?:第\s*[0-9一二三四五六七八九十百]+期|[一二三四五六七八九十百]+期|v\d+(?:\.\d+)*|\d{4}版))$",
            "",
            name.strip(),
            flags=re.I,
        ).strip(" ·・_-．")
        base = re.sub(r"[（(][^）)]{1,24}[）)]$", "", base).strip()
        return bool(
            base
            and re.search(
                r"(系统|平台|项目|中台|引擎|助手|Agent|库|服务|工作台|管道|定位|检测|感知|分流|检索|抽取|预警|预测|分析|控制|排产|终端|门户|看板|流水线|机器人|采集器|闭环|诊断|集市|宽表|目录|固件|计算|调度|接入|盒|中心|运维|云)$",
                base,
                flags=re.I,
            )
        )

    def _contains_alias(self, text: str, alias: str) -> bool:
        if not text or not alias:
            return False
        if re.search(r"[A-Za-z0-9+#./-]", alias):
            escaped = re.escape(alias)
            return bool(re.search(rf"(?<![A-Za-z0-9+#./-]){escaped}(?![A-Za-z0-9+#./-])", text, flags=re.I))
        return alias.lower() in text.lower()

    def _extract_experience_years(self, text: str) -> float | None:
        explicit = re.search(r"(?:工作|相关|从业|项目)?\s*(?:经验|经历)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*(?:年|years?|yrs?)|(?:工作|从业)\s*(\d+(?:\.\d+)?)\s*(?:年|years?|yrs?)", text, re.I)
        numeric = explicit or re.search(
            r"(?<![\d.])(\d{1,2}(?:\.\d+)?)\s*(?:年|years?|yrs?)\s*"
            r"[^，。；,;\n]{0,24}?(?:经验|经历|experience)",
            text,
            re.I,
        )
        if numeric:
            return float(next(group for group in numeric.groups() if group is not None))
        chinese_numbers = {
            "一年": 1,
            "两年": 2,
            "二年": 2,
            "三年": 3,
            "四年": 4,
            "五年": 5,
            "六年": 6,
            "七年": 7,
            "八年": 8,
            "九年": 9,
            "十年": 10,
        }
        explicit_chinese = re.search(r"(?:工作|相关|从业)?\s*(?:经验|经历)\s*[:：]?\s*(一年|两年|二年|三年|四年|五年|六年|七年|八年|九年|十年)", text)
        if not explicit_chinese:
            explicit_chinese = re.search(r"(一年|两年|二年|三年|四年|五年|六年|七年|八年|九年|十年)[^。\n]{0,24}(?:工作|开发|工程|项目)?经验", text)
        if explicit_chinese:
            return float(chinese_numbers[explicit_chinese.group(1)])
        history = self._extract_work_history(text)
        months = self._merged_months(history)
        return round(months / 12, 2) if months else None

    def _merged_months(self, history: list[dict[str, Any]]) -> int:
        intervals = []
        for item in history:
            start, end = item.get("start"), item.get("end")
            if not start or not end or end.lower() in {"至今", "now"}:
                continue
            start_match = re.match(r"(\d{4})[./-](\d{1,2})", start)
            end_match = re.match(r"(\d{4})[./-](\d{1,2})", end)
            if start_match and end_match:
                intervals.append((int(start_match.group(1)) * 12 + int(start_match.group(2)), int(end_match.group(1)) * 12 + int(end_match.group(2))))
        merged: list[list[int]] = []
        for start, end in sorted(intervals):
            if not merged or start > merged[-1][1]:
                merged.append([start, end])
            else:
                merged[-1][1] = max(merged[-1][1], end)
        return sum(max(0, end - start) for start, end in merged)

    def _extract_education(self, text: str) -> str | None:
        section = self._section_text(text, ("教育背景", "教育经历", "学历", "Education", "Academic Background"))
        for level in ("博士", "PhD", "硕士", "研究生", "Master", "本科", "学士", "Bachelor", "大专", "专科", "Associate"):
            if level.lower() in section.lower():
                return "博士" if level in {"博士", "PhD"} else "硕士" if level in {"硕士", "研究生", "Master"} else "本科" if level in {"本科", "学士", "Bachelor"} else "大专"
        explicit = re.findall(r"(?:学历|教育|毕业|[，,])\s*(博士|PhD|硕士|研究生|Master|本科|学士|Bachelor|大专|专科|Associate)", text, re.I)
        for level in ("博士", "PhD", "硕士", "研究生", "Master", "本科", "学士", "Bachelor", "大专", "专科", "Associate"):
            if any(item.lower() == level.lower() for item in explicit):
                return "博士" if level in {"博士", "PhD"} else "硕士" if level in {"硕士", "研究生", "Master"} else "本科" if level in {"本科", "学士", "Bachelor"} else "大专"
        return None

    def _extract_certifications(self, text: str) -> list[str]:
        section = self._section_text(text, ("证书", "证书认证", "证书及荣誉", "技能&证书", "Certifications", "Certificate"))
        source = section or text
        candidates = [item for item in ("PMP", "软考", "AWS", "CKA", "CFA", "CPA", "华为认证", "阿里云认证") if item.lower() in source.lower()]
        candidates += re.findall(r"CET[-－]?[四六46]", source, flags=re.I)
        if re.search(r"大学英语[四六]级", source):
            candidates.append(re.search(r"大学英语[四六]级(?:证书)?", source).group(0))
        candidates += re.findall(r"普通话[一二三四]级[甲乙丙等]?", source)
        candidates += re.findall(r"[^，。；\n]{0,12}驾驶证", source)
        candidates += re.findall(r"[^，。；\n]{0,20}(?:管理员|工程师)四级[^，。；\n]{0,12}(?:证|工)", source)
        return list(dict.fromkeys(item.strip() for item in candidates if item.strip()))

    def _extract_locations(self, text: str) -> list[str]:
        cities = (
            "北京", "上海", "深圳", "广州", "杭州", "南京", "成都", "武汉", "合肥", "苏州", "宁波", "台州",
            "西安", "长沙", "重庆", "天津", "厦门", "郑州", "青岛", "Remote", "远程",
        )
        lines = [line for line in self._normalize_text(text).splitlines() if re.search(r"(期望|意向|目标|现居|居住|长期在|发展|地点|城市|地址|city|location|address)", line, re.I)]
        source = "\n".join(lines)
        return [city for city in cities if city.lower() in source.lower()]

    def _extract_job_intent(self, text: str) -> str | None:
        lines = [line.strip() for line in self._normalize_text(text).splitlines() if line.strip()]
        heading_pattern = re.compile(
            r"(?:求职意向|岗位意向|目标岗位|应聘岗位|应聘职位|期望职位|意向职位|意向岗位|求职目标|Objective|Target Role|Desired Position)\s*[:：|]?\s*(.+)?",
            re.I,
        )
        for index, line in enumerate(lines[:80]):
            match = heading_pattern.search(line)
            if not match:
                continue
            raw = (match.group(1) or "").strip()
            if not raw and index + 1 < len(lines):
                raw = lines[index + 1]
            intent = self._clean_job_intent_value(raw)
            if intent:
                return intent

        role_patterns = [
            r"([A-Za-z0-9 +#./-]{1,30}\s*(?:Engineer|Developer|Architect|Analyst|Scientist|Manager))",
            r"([\u4e00-\u9fffA-Za-z0-9 +#./-]{2,36}(?:工程师|开发工程师|算法工程师|架构师|分析师|产品经理|运维工程师|测试工程师|数据科学家))",
        ]
        for line in lines[:30]:
            if any(marker in line for marker in ("公司", "学校", "邮箱", "电话", "教育", "经历", "项目")):
                continue
            for pattern in role_patterns:
                match = re.search(pattern, line, flags=re.I)
                if match:
                    intent = self._clean_job_intent_value(match.group(1))
                    if intent:
                        return intent
        return None

    def _clean_job_intent_value(self, value: str) -> str | None:
        cleaned = re.sub(r"\s+", " ", value or "").strip(" ，,。；;|/\\-")
        if not cleaned:
            return None
        parts = [part.strip() for part in re.split(r"[|｜/／,，;；·•]", cleaned) if part.strip()]
        role_keywords = (
            "工程师", "开发", "算法", "架构师", "分析师", "产品经理", "运维", "测试", "数据科学家",
            "Engineer", "Developer", "Architect", "Analyst", "Scientist", "Manager",
        )
        noise_pattern = re.compile(
            r"(北京|上海|深圳|广州|杭州|南京|成都|武汉|合肥|苏州|西安|长沙|重庆|天津|厦门|郑州|青岛|远程|Remote|全职|实习|到岗|薪资|\d+\s*[kK]|面议)",
            re.I,
        )
        for part in parts or [cleaned]:
            part = re.sub(r"(期望|目标|意向|岗位|职位|求职|应聘)\s*[:：]?", "", part).strip()
            if noise_pattern.fullmatch(part):
                continue
            if any(keyword.lower() in part.lower() for keyword in role_keywords):
                part = noise_pattern.sub("", part).strip(" ，,。；;|/\\-")
                return part[:60] if len(part) >= 2 else None
        cleaned = noise_pattern.sub("", cleaned).strip(" ，,。；;|/\\-")
        return cleaned[:60] if 2 <= len(cleaned) <= 60 else None

    def _extract_salary(self, text: str) -> list[int]:
        match = re.search(r"(\d+)\s*[kK]?\s*[-~到]\s*(\d+)\s*[kK]", text)
        if not match:
            return []
        low, high = int(match.group(1)), int(match.group(2))
        return [low, high] if low <= high else [high, low]

    def _extract_work_history(self, text: str) -> list[dict[str, Any]]:
        section = self._section_text(text, ("工作经历", "工作经验", "工作经验与实习经历", "实习经历", "科研及工作经历", "工作经验", "Work Experience", "Experience"))
        history = []
        for match in re.finditer(r"((?:20\d{2}|19\d{2})[./-]\d{1,2})\s*[-至~—–]\s*((?:20\d{2}|19\d{2})[./-]\d{1,2}|至今|now)", section, re.I):
            evidence = next((line.strip() for line in section.splitlines() if match.group(0) in line), match.group(0))
            evidence = re.sub(re.escape(match.group(0)), "", evidence, count=1).strip(" ：:|-—–")
            history.append({"start": match.group(1), "end": match.group(2), "evidence": evidence[:240]})
        return history[:6]

    def _build_evidence(self, text: str, skills: list[dict[str, Any]], projects: list[dict[str, Any]]) -> list[dict[str, Any]]:
        evidence = []
        for index, skill in enumerate(skills[:12], start=1):
            evidence.append(
                {
                    "evidence_id": f"resume_skill_{index}",
                    "stage": "resume_parse",
                    "type": "skill",
                    "target": skill["name"],
                    "content": skill.get("evidence", ""),
                    "confidence": skill.get("confidence", 0.6),
                }
            )
        for index, project in enumerate(projects[:6], start=1):
            evidence.append(
                {
                    "evidence_id": f"resume_project_{index}",
                    "stage": "resume_parse",
                    "type": "project",
                    "target": project["name"],
                    "content": project.get("evidence", ""),
                    "confidence": 0.72 if project.get("verification_status") == "supported" else 0.5,
                }
            )
        if not evidence and text:
            evidence.append(
                {
                    "evidence_id": "resume_text_1",
                    "stage": "resume_parse",
                    "type": "resume",
                    "target": "raw_resume",
                    "content": text[:500],
                    "confidence": 0.35,
                }
            )
        return evidence

    def _quality_summary(self, text: str, skills: list[dict[str, Any]], projects: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> dict[str, Any]:
        has_metrics = bool(self._extract_metrics(text)) if text else any(project.get("metrics") for project in projects)
        avg_confidence = round(sum(float(item.get("confidence", 0)) for item in evidence) / max(len(evidence), 1), 2)
        return {
            "skill_count": len(skills),
            "project_count": len(projects),
            "evidence_count": len(evidence),
            "has_quantified_metrics": has_metrics,
            "avg_evidence_confidence": avg_confidence,
            "needs_manual_review": len(skills) == 0 or avg_confidence < 0.55,
        }

    def _deterministic_semantic_profile(self, parsed: dict[str, Any]) -> dict[str, Any]:
        project_capabilities = []
        for project in parsed.get("projects", [])[:4]:
            if not isinstance(project, dict):
                continue
            project_capabilities.append(
                {
                    "project": project.get("name"),
                    "capabilities": self._capabilities_from_terms(project.get("tech_stack", [])),
                    "evidence": project.get("evidence", ""),
                }
            )
        skill_usage = [
            {
                "name": skill.get("name"),
                "usage_status": skill.get("usage_status", "mentioned"),
                "level": skill.get("level", "intermediate"),
                "evidence": skill.get("evidence", ""),
            }
            for skill in parsed.get("skills", [])[:12]
            if isinstance(skill, dict) and skill.get("name")
        ]
        graph_mappings = [
            {
                "skill": skill.get("name"),
                "category": skill.get("category", "technical_skill"),
                "capability": self._capability_from_category(str(skill.get("category", ""))),
            }
            for skill in parsed.get("skills", [])[:12]
            if isinstance(skill, dict) and skill.get("name")
        ]
        focus = []
        for project in project_capabilities[:2]:
            if project.get("project"):
                focus.append(f"核验 {project['project']} 中的个人贡献和可量化结果")
        for skill in skill_usage[:4]:
            focus.append(f"追问 {skill['name']} 的使用深度与证据")
        return {
            "status": "structured_only",
            "project_capabilities": project_capabilities,
            "skill_usage_assessments": skill_usage,
            "graph_mappings": graph_mappings,
            "interview_focus": focus[:6],
        }

    def _merge_semantic_profile(self, raw: Any, parsed: dict[str, Any]) -> dict[str, Any]:
        fallback = self._deterministic_semantic_profile(parsed)
        if not isinstance(raw, dict):
            return fallback
        merged = {
            **fallback,
            "status": "llm_enriched",
        }
        for key in ("project_capabilities", "skill_usage_assessments", "graph_mappings", "interview_focus"):
            value = raw.get(key)
            if isinstance(value, list) and value:
                merged[key] = value[:12]
        return merged

    def _capabilities_from_terms(self, terms: list[Any]) -> list[str]:
        joined = " ".join(str(term) for term in terms).lower()
        capabilities = []
        if any(token in joined for token in ("rag", "llm", "agent", "langchain", "langgraph", "pytorch", "tensorflow")):
            capabilities.append("AI 工程应用")
        if any(token in joined for token in ("redis", "mysql", "postgres", "sql", "mongodb", "clickhouse", "hive", "spark", "flink")):
            capabilities.append("数据建模与检索")
        if any(token in joined for token in ("docker", "kubernetes", "k8s", "ci/cd", "nginx")):
            capabilities.append("工程部署与运维")
        if any(token in joined for token in ("react", "vue", "javascript", "typescript")):
            capabilities.append("前端应用实现")
        return capabilities or ["项目交付与问题拆解"]

    def _capability_from_category(self, category: str) -> str:
        mapping = {
            "ai_engineering": "AI 工程应用",
            "database": "数据处理与存储",
            "big_data": "大数据处理",
            "devops": "工程部署与稳定性",
            "backend_framework": "后端系统开发",
            "frontend_framework": "前端应用开发",
            "programming_language": "编程实现能力",
            "middleware": "分布式中间件",
            "observability": "可观测与质量保障",
            "iot": "物联网系统应用",
        }
        return mapping.get(category, "通用技术能力")

    def _extract_metrics(self, text: str) -> list[str]:
        patterns = [
            r"\d+(?:\.\d+)?\s*%",
            r"\d+(?:\.\d+)?\s*(?:ms|s|秒|分钟|小时)",
            r"\d+(?:\.\d+)?\s*(?:QPS|TPS|qps|tps)",
            r"\d+(?:\.\d+)?\s*(?:万|千|w|k)?\s*(?:用户|订单|请求|数据)",
        ]
        metrics = []
        for pattern in patterns:
            metrics.extend(re.findall(pattern, text))
        return list(dict.fromkeys(metric.strip() for metric in metrics))[:10]

    def _extract_role(self, text: str) -> str:
        role_terms = ("负责", "主导", "参与", "设计", "实现", "owner", "lead", "developed", "designed")
        for term in role_terms:
            if term.lower() in text.lower():
                return self._evidence_window(text, term, width=80)
        return ""

    def _infer_skill_level(self, text: str, term: str) -> str:
        evidence = self._evidence_window(text, term, width=120).lower()
        if any(marker in evidence for marker in ("精通", "主导", "架构", "expert", "lead")):
            return "advanced"
        if any(marker in evidence for marker in ("熟悉", "负责", "实现", "proficient", "developed")):
            return "intermediate"
        if any(marker in evidence for marker in ("了解", "入门", "basic", "familiar")):
            return "basic"
        return "intermediate"

    def _skill_confidence(self, evidence: str) -> float:
        score = 0.58
        if any(term in evidence for term in ("负责", "主导", "设计", "实现", "优化", "排查")):
            score += 0.12
        if self._extract_metrics(evidence):
            score += 0.1
        if len(evidence) >= 40:
            score += 0.06
        return round(min(score, 0.92), 2)

    def _evidence_window(self, text: str, term: str, *, width: int = 120) -> str:
        if not term:
            return ""
        index = text.lower().find(term.lower())
        if index < 0:
            return ""
        start = max(0, index - width // 2)
        end = min(len(text), index + len(term) + width // 2)
        return text[start:end].strip()

    def _clean_level(self, value: Any) -> str:
        level = str(value or "intermediate").lower()
        if level in {"basic", "intermediate", "advanced", "expert"}:
            return level
        return "intermediate"

    def _clean_experience_years(self, value: Any) -> float | None:
        if value in (None, "", []):
            return None
        if isinstance(value, dict):
            value = value.get("years") or value.get("value") or value.get("experience_years")
        match = re.search(r"\d+(?:\.\d+)?", str(value))
        return float(match.group(0)) if match else None

    def _clean_education(self, value: Any) -> str | None:
        if value in (None, "", []):
            return None
        for _ in range(3):
            if not isinstance(value, (dict, list)):
                break
            if isinstance(value, list):
                value = next((item for item in value if item), None)
                continue
            value = value.get("degree") or value.get("level") or value.get("name") or value.get("value")
        return str(value)[:40] if value else None

    def _clean_text_value(self, value: Any, *, limit: int = 80) -> str | None:
        if value in (None, "", []):
            return None
        if isinstance(value, dict):
            value = value.get("name") or value.get("value") or value.get("title")
        if isinstance(value, list):
            value = next((item for item in value if item), None)
        text = re.sub(r"\s+", " ", str(value or "")).strip()
        return text[:limit] if text else None

    def _bounded_float(self, value: Any, *, default: float) -> float:
        try:
            return round(min(1.0, max(0.0, float(value))), 2)
        except (TypeError, ValueError):
            return default

    def _supported_by_text(self, text: str, name: str, evidence: str) -> bool:
        normalized_text = self._compact_for_match(text)
        normalized_name = self._compact_for_match(name)
        normalized_evidence = self._compact_for_match(evidence)
        if normalized_name and normalized_name in normalized_text:
            return True
        return len(normalized_evidence) >= 8 and normalized_evidence in normalized_text

    def _compact_for_match(self, value: str) -> str:
        # Keep '+' so the short token C cannot normalize to the same key as C++.
        return re.sub(r"[\s._/\-]+", "", value or "", flags=re.UNICODE).lower()

    def _normalize_text(self, text: str | None) -> str:
        value = re.sub(r"\r\n?", "\n", text or "")
        value = re.sub(r"[ \t\f\v]+", " ", value)
        value = re.sub(r"\n{3,}", "\n\n", value)
        return value.strip()
