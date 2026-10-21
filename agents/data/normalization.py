from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import re
import unicodedata
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


DOMAIN_KEYWORDS = {
    "人工智能": (
        "artificial intelligence", "machine learning", "deep learning", "generative ai", "large language model",
        "llm", "rag", "computer vision", "nlp", "ai engineer", "ml engineer", "算法", "人工智能", "大模型", "机器学习", "深度学习", "智能体",
        "ai agent", "agent工程师", "agent 工程师", "ai平台", "ai 平台", "ai架构", "ai 架构",
    ),
    "大数据": (
        "big data", "data engineer", "data platform", "data warehouse", "analytics engineer", "flink", "spark", "kafka",
        "大数据", "数据工程", "数据开发", "数据仓库", "实时计算", "湖仓", "数据治理",
        "data analyst", "business intelligence", "bi analyst", "数据分析", "数据分析师", "数据平台",
    ),
    "物联网": (
        "internet of things", "iot", "mqtt", "embedded", "firmware", "rtos", "edge gateway", "device platform",
        "物联网", "嵌入式", "固件", "设备接入", "边缘网关", "端侧",
    ),
    "智能系统": (
        "robotics", "robot", "autonomous", "intelligent system", "backend engineer", "software engineer", "cloud native",
        "devops", "sre", "platform engineer", "test automation", "distributed system", "microservice", "kubernetes", "docker",
        "full stack", "web developer", "机器人", "智能系统", "后端", "云原生", "测试开发", "自动驾驶",
        "computer network", "network engineer", "network operations", "system integration", "计算机网络", "网络工程师", "系统集成", "平台工程师",
    ),
}

TECHNICAL_ROLE_KEYWORDS = (
    "engineer", "developer", "data scientist", "ml scientist", "programmer", "devops", "sre", "software", "firmware",
    "architect", "analyst", "data analyst", "network engineer", "platform engineer", "head of engineering",
    "softwareentwickler", "softwareentwicklung", "entwickler", "ingenieur",
    "工程师", "开发", "算法", "数据科学家", "研发", "技术专家", "架构师", "分析师", "网络工程师", "平台工程师",
)
ARCHITECT_DOMAINS = ("ai architect", "data architect", "cloud architect", "software architect", "system architect", "iot architect", "架构师", "解决方案架构师", "数据架构师", "系统架构师")
NON_TECH_TITLE_KEYWORDS = ("sales", "marketing", "seo", "designer", "drafter", "recruiter", "copywriter", "销售", "市场", "设计师", "招聘")
NON_SKILL_TAG_PATTERN = re.compile(
    r"(本科|硕士|博士|大专|学历|经验|应届|五险|一金|双休|年终奖|带薪|团建|餐补|房补|"
    r"节日福利|定期体检|弹性工作|股票期权|招聘|急聘|\d+[年以上])",
    re.IGNORECASE,
)
SKILL_NOISE_PATTERN = re.compile(
    r"(nice|氛围|环境好|领导好|同事|福利|奖金|补贴|包吃|包住|下午茶|生日会|"
    r"五险|一金|双休|年假|团建|体检|股票期权|免费班车|晋升|薪资|待遇|招聘|急聘)",
    re.IGNORECASE,
)
PLAUSIBLE_SKILL_TAG_PATTERN = re.compile(
    r"(开发|算法|数据|模型|系统|平台|架构|测试|网络|数据库|计算|智能|嵌入式|云|"
    r"^[A-Za-z][A-Za-z0-9+.#/_ -]{1,30}$)",
    re.IGNORECASE,
)

SKILL_ALIASES = {
    "Python": ("python",), "Java": ("java",), "C++": ("c++", "cpp"), "Go": ("golang", "go language"),
    "PyTorch": ("pytorch",), "TensorFlow": ("tensorflow",), "RAG": ("rag", "retrieval augmented"),
    "向量数据库": ("vector database", "向量数据库"), "Prompt Engineering": ("prompt engineering", "提示词工程"),
    "LangGraph": ("langgraph",), "LangChain": ("langchain",), "LLM": ("large language model", "llm"),
    "Agent": ("ai agent", "agentic", "智能体"), "工具调用": ("tool calling", "function calling", "工具调用"),
    "多 Agent 协作": ("multi-agent", "multi agent", "多 agent 协作"), "评测体系": ("evaluation framework", "评测体系"),
    "Flink": ("flink",), "Spark": ("spark",), "Kafka": ("kafka",),
    "Hadoop": ("hadoop",), "SQL": ("sql",), "Iceberg": ("iceberg",), "Docker": ("docker",),
    "Hive": ("hive",), "数据仓库": ("data warehouse", "数据仓库"), "消息队列": ("message queue", "消息队列"),
    "微服务": ("microservice", "微服务"), "服务治理": ("service governance", "服务治理"),
    "可观测性": ("observability", "可观测性"), "高并发": ("high concurrency", "高并发"),
    "Kubernetes": ("kubernetes", "k8s"), "Prometheus": ("prometheus",), "OpenTelemetry": ("opentelemetry",),
    "MQTT": ("mqtt",), "RTOS": ("rtos",), "嵌入式 Linux": ("embedded linux", "嵌入式 linux"),
    "时序数据库": ("time series database", "时序数据库"), "设备接入": ("device access", "设备接入"),
    "边缘计算": ("edge computing", "边缘计算"), "计算机视觉": ("computer vision", "计算机视觉"),
    "NLP": ("natural language processing", "nlp"), "ROS": ("robot operating system", "ros2", " ros "),
    "FastAPI": ("fastapi",), "Spring Boot": ("spring boot",), "Redis": ("redis",), "MySQL": ("mysql",),
    "Terraform": ("terraform",), "自动化测试": ("test automation", "自动化测试"),
    "接口测试": ("api testing", "接口测试"), "性能测试": ("performance testing", "性能测试"),
    "pytest": ("pytest",), "CI/CD": ("ci/cd", "continuous integration"),
    "Linux": ("linux",), "Shell": ("shell", "bash"), "C": ("c language", "c语言"),
    "JavaScript": ("javascript",), "TypeScript": ("typescript",), "React": ("react.js", "reactjs"),
    "Vue": ("vue.js", "vuejs"), "Node.js": ("node.js", "nodejs"), "Git": (" git ",),
    "STM32": ("stm32",), "FreeRTOS": ("freertos",), "NVIDIA CUDA": ("cuda",),
    "HDFS": ("hdfs",), "HBase": ("hbase",), "Elasticsearch": ("elasticsearch",),
    "REST API": ("rest api", "restful"), "HTTP/HTTPS": ("http/https", "https"),
    "TCP/IP": ("tcp/ip", "tcp/udp"), "WebSocket": ("websocket",), "TLS": ("tls", "openssl"),
    "OTA": ("ota升级", "ota update", "firmware update"), "日志分析": ("日志分析", "log analysis"),
    "抓包分析": ("抓包", "packet capture", "wireshark"), "回归测试": ("回归测试", "regression testing"),
    "兼容性测试": ("兼容性测试", "compatibility testing"), "稳定性测试": ("稳定性测试", "稳定性压测", "stability testing"),
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"p", "br", "li", "h1", "h2", "h3", "div"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_text(value: Any) -> str:
    raw = unicodedata.normalize("NFKC", unescape(str(value or "")))
    if "<" in raw and ">" in raw:
        parser = _TextExtractor()
        try:
            parser.feed(raw)
            raw = "".join(parser.parts)
        except ValueError:
            raw = re.sub(r"<[^>]+>", " ", raw)
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line)


def canonical_url(value: Any) -> str | None:
    url = str(value or "").strip()
    if not url.startswith(("http://", "https://")):
        return None
    parts = urlsplit(url)
    query = urlencode(sorted((key, value) for key, value in parse_qsl(parts.query) if not key.casefold().startswith("utm_")))
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), query, ""))


def parse_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value, UTC)
        except (ValueError, OSError):
            return None
    text = str(value).strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def classify_domain(blob: str) -> str | None:
    lowered = f" {blob.casefold()} "
    scores = {
        domain: sum(2 if f" {term.casefold()} " in lowered else 1 for term in terms if term.casefold() in lowered)
        for domain, terms in DOMAIN_KEYWORDS.items()
    }
    domain, score = max(scores.items(), key=lambda item: item[1])
    return domain if score else None


def extract_skills(blob: str, supplied: Any = None) -> list[str]:
    supplied_values = supplied if isinstance(supplied, list) else []
    lowered = f" {blob.casefold()} "
    skills = [name for name, aliases in SKILL_ALIASES.items() if any(_contains_alias(lowered, alias) for alias in aliases)]
    for value in supplied_values:
        cleaned = clean_text(value)
        if is_valid_skill(cleaned):
            canonical = next((name for name, aliases in SKILL_ALIASES.items() if cleaned.casefold() == name.casefold() or cleaned.casefold() in aliases), None)
            if canonical or PLAUSIBLE_SKILL_TAG_PATTERN.search(cleaned):
                skills.append(canonical or cleaned)
    return list(dict.fromkeys(skills))[:24]


def is_valid_skill(value: object) -> bool:
    """Return whether a label is suitable for a published capability graph."""
    cleaned = clean_text(value)
    if not cleaned or len(cleaned) > 40:
        return False
    if NON_SKILL_TAG_PATTERN.search(cleaned) or SKILL_NOISE_PATTERN.search(cleaned):
        return False
    if re.fullmatch(r"[\d\W_]+", cleaned):
        return False
    return bool(
        cleaned in SKILL_ALIASES
        or PLAUSIBLE_SKILL_TAG_PATTERN.search(cleaned)
    )


def _contains_alias(blob: str, alias: str) -> bool:
    needle = alias.casefold().strip()
    if len(needle) <= 4 and needle.replace("+", "").isalnum():
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", blob))
    return needle in blob


def _list_field(value: Any) -> list[str]:
    if isinstance(value, list):
        values = value
    elif value:
        values = re.split(r"[；;\n]", str(value))
    else:
        values = []
    return [text for item in values if (text := clean_text(item))][:12]


def _responsibilities(content: str, supplied: Any) -> list[str]:
    explicit = _list_field(supplied)
    if explicit:
        return explicit[:16]
    responsibility_text, _ = _section_texts(content)
    lines = _clauses(responsibility_text)
    action_terms = (
        "负责", "参与", "建设", "开发", "设计", "维护", "搭建", "制定", "编写", "推进", "推动",
        "协助", "支撑", "保障", "优化", "交付", "实施", "落地", "排查", "对接", "分析",
        "implement", "build", "design", "develop", "manage", "deliver", "maintain", "optimize", "you will", "aufgaben",
    )
    selected = [line for line in lines if any(term in line.casefold() for term in action_terms)]
    return (selected or lines)[:12]


def _requirements(content: str, supplied: Any) -> list[str]:
    explicit = _list_field(supplied)
    if explicit:
        return explicit[:20]
    _, requirement_text = _section_texts(content)
    lines = _clauses(requirement_text)
    terms = (
        "熟悉", "掌握", "具备", "精通", "了解", "要求", "经验", "学历", "专业", "优先", "能力",
        "proficient", "experience", "required", "knowledge", "familiar", "degree", "qualification",
    )
    selected = [line for line in lines if any(term in line.casefold() for term in terms)]
    return (selected or lines)[:16]


def _section_texts(content: str) -> tuple[str, str]:
    headings = ("任职要求", "岗位要求", "职位要求", "任职资格", "岗位资格", "我们希望你", "requirements", "qualifications")
    lowered = content.casefold()
    indexes = [lowered.find(heading.casefold()) for heading in headings]
    indexes = [index for index in indexes if index >= 0]
    if not indexes:
        return content, content
    boundary = min(indexes)
    return content[:boundary], content[boundary:]


def _clauses(content: str) -> list[str]:
    prepared = re.sub(
        r"(?=(?:岗位职责|工作职责|职位职责|任职要求|岗位要求|职位要求|任职资格|岗位资格|加分项|优先条件))",
        "\n",
        content,
    )
    prepared = re.sub(r"(?<!\d)(?=(?:[1-9]\d*[.、)）]|[一二三四五六七八九十]+[、.]))", "\n", prepared)
    values = re.split(r"[\n；;。]+", prepared)
    return list(dict.fromkeys(cleaned for value in values if 8 <= len(cleaned := clean_text(value)) <= 360))


def _evidence_segments(content: str, skills: list[str]) -> list[dict[str, Any]]:
    requirement_start = len(_section_texts(content)[0])
    output = []
    search_from = 0
    for index, clause in enumerate(_clauses(content)):
        start = content.find(clause, search_from)
        if start < 0:
            start = content.find(clause)
        end = start + len(clause) if start >= 0 else None
        if start >= 0:
            search_from = end or search_from
        segment_skills = [skill for skill in skills if skill.casefold() in clause.casefold()]
        if not segment_skills:
            segment_skills = extract_skills(clause)
        output.append({
            "segment_id": f"seg_{index + 1:03d}",
            "section": "requirements" if start >= requirement_start and requirement_start < len(content) else "responsibilities",
            "text": clause,
            "start": start if start >= 0 else None,
            "end": end,
            "skills": segment_skills,
        })
    return output[:60]


def _fingerprint(*parts: Any) -> str:
    canonical = "|".join(re.sub(r"\W+", "", clean_text(part).casefold()) for part in parts)
    return sha256(canonical.encode("utf-8")).hexdigest()[:24]


def normalize_recruitment_item(raw: dict[str, Any], learning_policy: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, list[str]]:
    metadata = dict(raw.get("metadata") or {})
    merged = {**metadata, **raw}
    title = clean_text(merged.get("title") or merged.get("position") or merged.get("name"))
    company = clean_text(merged.get("company") or merged.get("company_name")) or None
    raw_content = str(merged.get("raw_content") or merged.get("content") or merged.get("description") or "")
    content = clean_text(raw_content)
    supplied_tags = merged.get("skill_tags") or merged.get("tags") or []
    skill_blob = " ".join((title, content, " ".join(map(str, supplied_tags if isinstance(supplied_tags, list) else []))))
    skills = extract_skills(skill_blob, supplied_tags)
    surface_domain = classify_domain(f"{title} {' '.join(skills)} {merged.get('domain', '')}")
    domain = surface_domain or classify_domain(f"{skill_blob} {merged.get('domain', '')}")
    lowered_title = title.casefold()
    policy = learning_policy or {}
    accepted_entry = dict(policy.get("accepted_titles", {}).get(lowered_title, {}))
    rejected_entry = dict(policy.get("rejected_titles", {}).get(lowered_title, {}))
    if accepted_entry.get("domain") in DOMAIN_KEYWORDS:
        domain = accepted_entry["domain"]
    direct_role = any(re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", lowered_title) for term in TECHNICAL_ROLE_KEYWORDS if term.isascii())
    direct_role = direct_role or any(term in title for term in TECHNICAL_ROLE_KEYWORDS if not term.isascii())
    architect_role = any(term in lowered_title for term in ARCHITECT_DOMAINS)
    blocked_role = any(term in lowered_title for term in NON_TECH_TITLE_KEYWORDS)
    learned_accept = int(accepted_entry.get("count", 0)) >= 1
    learned_reject = int(rejected_entry.get("count", 0)) >= 2
    role_match = (direct_role or architect_role or learned_accept) and not blocked_role and not learned_reject
    issues: list[str] = []
    if not title:
        issues.append("missing_title")
    if not content:
        issues.append("missing_content")
    if not domain or not role_match or not (surface_domain or len(skills) >= 2 or learned_accept):
        issues.append("outside_target_scope")
        return None, issues

    source_url = canonical_url(merged.get("source_url") or merged.get("url"))
    source_platform = clean_text(merged.get("source_platform") or "unknown")
    city = _clean_city(merged.get("city") or merged.get("location"))
    district = _clean_district(merged.get("district"))
    responsibilities = _responsibilities(content, merged.get("responsibilities"))
    requirements = _requirements(content, merged.get("requirements"))
    evidence_segments = _evidence_segments(content, skills)
    published_at = parse_datetime(merged.get("published_at") or merged.get("date") or merged.get("epoch"))
    salary_min = merged.get("salary_min_k")
    salary_max = merged.get("salary_max_k")
    if salary_min is None and merged.get("salary_min") is not None:
        salary_min = round(float(merged["salary_min"]) / 12 / 1000)
    if salary_max is None and merged.get("salary_max") is not None:
        salary_max = round(float(merged["salary_max"]) / 12 / 1000)

    score = 15 + 12 + min(15, len(skills) * 3) + min(10, len(responsibilities) * 2)
    score += 15 if len(content) >= 300 else 8 if len(content) >= 100 else 0
    score += 10 if company else 0
    score += 10 if source_url else 0
    score += 8 if published_at else 0
    score += 3 if city else 0
    score += 2 if salary_min is not None or salary_max is not None else 0
    if not company:
        issues.append("missing_company")
    if not source_url:
        issues.append("missing_source_url")
    if not skills:
        issues.append("missing_skills")
    if not responsibilities:
        issues.append("missing_responsibilities")
    source_id = clean_text(merged.get("source_id") or merged.get("id") or merged.get("slug"))
    if not source_id:
        source_id = _fingerprint(source_platform, company, title, source_url)
    if merged.get("collection_mode") == "live" and not source_id.startswith(f"{source_platform}:"):
        source_id = f"{source_platform}:{source_id}"
    identity_hash = _fingerprint(company, title, city)
    content_hash = _fingerprint(title, company, content, skills)
    normalized = {
        "source_id": source_id,
        "source_type": "jd",
        "source_category": "recruitment",
        "domain": domain,
        "title": title,
        "content": content,
        "raw_content": raw_content,
        "quality_score": min(100, score),
        "dedup_hash": content_hash,
        "company": company,
        "company_industry": merged.get("company_industry"),
        "company_size": merged.get("company_size"),
        "salary_min_k": int(salary_min) if salary_min is not None else None,
        "salary_max_k": int(salary_max) if salary_max is not None else None,
        "salary_months": int(merged.get("salary_months") or 12),
        "currency": str(merged.get("currency") or "CNY"),
        "city": city,
        "district": district,
        "experience_min_years": merged.get("experience_min_years"),
        "experience_max_years": merged.get("experience_max_years"),
        "education": clean_text(merged.get("education")) or None,
        "employment_type": clean_text(merged.get("employment_type") or "full_time"),
        "skill_tags": skills,
        "responsibilities": responsibilities,
        "requirements": requirements,
        "evidence_segments": evidence_segments,
        "benefits": _list_field(merged.get("benefits")),
        "published_at": published_at,
        "changed_at": parse_datetime(merged.get("changed_at")),
        "source_platform": source_platform,
        "source_url": source_url,
        "job_status": merged.get("job_status") if merged.get("job_status") in {"active", "offline"} else "active",
        "change_type": merged.get("change_type") if merged.get("change_type") in {"new", "updated", "unchanged", "offline"} else "unchanged",
        "metadata": {
            **metadata,
            "identity_hash": identity_hash,
            "quality_issues": issues,
            "raw_domain": merged.get("domain"),
            "collection_mode": merged.get("collection_mode"),
            "evidence_role": "primary",
            "salary_period": merged.get("salary_period"),
            "remote": bool(merged.get("remote")),
            "content_char_count": len(content),
            "content_sha256": sha256(content.encode("utf-8")).hexdigest(),
            "section_counts": {
                "responsibilities": len(responsibilities),
                "requirements": len(requirements),
                "evidence_segments": len(evidence_segments),
            },
        },
    }
    return normalized, issues


def _looks_like_salary(value: object) -> bool:
    text = clean_text(value)
    if not text:
        return False
    return bool(re.search(r"\d", text) and re.search(r"万|千|元|k|K|薪|-|~|－", text))


def _clean_city(value: object) -> str | None:
    text = clean_text(value)
    if not text or _looks_like_salary(text):
        return None
    if len(text) > 20:
        return None
    return text


def _clean_district(value: object) -> str | None:
    text = clean_text(value)
    if not text or _looks_like_salary(text):
        return None
    if len(text) > 30:
        return None
    return text


def normalize_community_signal(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    title = clean_text(raw.get("title"))
    content = clean_text(raw.get("content") or raw.get("text"))
    tags = _list_field(raw.get("tags"))
    blob = " ".join((title, content, " ".join(tags)))
    domain_hint = clean_text(raw.get("domain_hint"))
    domain = classify_domain(blob) or (domain_hint if domain_hint in DOMAIN_KEYWORDS else None)
    if not domain:
        return None, ["outside_target_scope"]
    source_url = canonical_url(raw.get("source_url") or raw.get("url"))
    engagement = {key: max(0, int(value or 0)) for key, value in dict(raw.get("engagement") or {}).items()}
    published_at = parse_datetime(raw.get("published_at") or raw.get("created_at") or raw.get("creation_date"))
    issues = []
    score = 20 + (15 if len(content) >= 80 else 6) + (12 if source_url else 0) + (10 if published_at else 0)
    score += min(18, len(tags) * 3) + min(15, sum(engagement.values()) // 5) + (10 if title else 0)
    if not content:
        issues.append("missing_content")
    if not source_url:
        issues.append("missing_source_url")
    platform = clean_text(raw.get("source_platform") or "unknown")
    raw_id = clean_text(raw.get("signal_id") or raw.get("source_id") or raw.get("id") or raw.get("objectID"))
    signal_id = raw_id if raw_id.startswith(f"{platform}:") else f"{platform}:{raw_id or _fingerprint(platform, title, source_url)}"
    return {
        "signal_id": signal_id,
        "source_type": raw.get("source_type") if raw.get("source_type") in {"forum", "social_media", "developer_community"} else "developer_community",
        "source_platform": platform,
        "source_url": source_url or f"https://invalid.local/{signal_id}",
        "domain": domain,
        "title": title or "技术社区信号",
        "content": content or title,
        "author": clean_text(raw.get("author") or raw.get("owner")) or None,
        "tags": tags or extract_skills(blob),
        "engagement": engagement,
        "published_at": published_at,
        "quality_score": min(100, score),
        "dedup_hash": _fingerprint(platform, title, content),
        "metadata": {**dict(raw.get("metadata") or {}), "quality_issues": issues, "auxiliary_only": True},
    }, issues
