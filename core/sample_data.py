"""Deterministic gold fixtures for validation tests; never used by the runtime graph."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from hashlib import sha1


COMPUTER_JOB_TEMPLATES = [
    {"domain": "AI / 大模型", "title": "大模型应用工程师", "skills": ["Python", "RAG", "LangChain", "向量数据库", "Prompt Engineering", "FastAPI"], "salary": (22, 45), "experience": (3, 5), "education": "本科", "responsibilities": ["建设企业知识库与 RAG 检索链路", "开发大模型应用服务并持续优化效果", "建立提示词、评测与发布流程"]},
    {"domain": "AI / 大模型", "title": "AI Agent 工程师", "skills": ["Python", "LangGraph", "工具调用", "多 Agent 协作", "RAG", "评测体系"], "salary": (25, 50), "experience": (3, 7), "education": "本科", "responsibilities": ["设计多 Agent 编排与工具调用链路", "建设任务规划、记忆和评测能力", "推动 Agent 在业务场景稳定落地"]},
    {"domain": "后端 / Java", "title": "Java 后端工程师", "skills": ["Java", "Spring Boot", "MySQL", "Redis", "消息队列", "微服务"], "salary": (18, 35), "experience": (3, 5), "education": "本科", "responsibilities": ["负责核心交易服务设计与开发", "治理数据库、缓存和消息链路", "承担性能优化与线上故障排查"]},
    {"domain": "后端 / Java", "title": "微服务工程师", "skills": ["Spring Cloud", "Kubernetes", "服务治理", "可观测性", "高并发", "Redis"], "salary": (24, 42), "experience": (5, 8), "education": "本科", "responsibilities": ["建设高并发微服务架构", "推进服务治理与可观测体系", "保障发布、容灾和容量稳定性"]},
    {"domain": "大数据", "title": "数据开发工程师", "skills": ["SQL", "Spark", "Flink", "Hive", "Kafka", "数据仓库"], "salary": (20, 38), "experience": (3, 6), "education": "本科", "responsibilities": ["建设离线与实时数据链路", "设计数据仓库模型和质量规则", "优化计算任务成本与时效"]},
    {"domain": "智能系统 / IoT", "title": "物联网平台工程师", "skills": ["MQTT", "嵌入式 Linux", "边缘计算", "设备接入", "时序数据库", "C++"], "salary": (18, 36), "experience": (3, 6), "education": "本科", "responsibilities": ["建设海量设备接入与管理平台", "开发边缘计算和消息链路", "保障设备数据安全与稳定"]},
    {"domain": "云原生 / 测试", "title": "DevOps 工程师", "skills": ["Docker", "Kubernetes", "CI/CD", "Prometheus", "Linux", "Terraform"], "salary": (20, 40), "experience": (3, 7), "education": "本科", "responsibilities": ["建设云原生交付平台", "维护监控告警和应急响应体系", "提升发布效率与基础设施可靠性"]},
    {"domain": "云原生 / 测试", "title": "测试开发工程师", "skills": ["Python", "自动化测试", "接口测试", "性能测试", "pytest", "CI/CD"], "salary": (16, 30), "experience": (2, 5), "education": "本科", "responsibilities": ["建设接口和端到端自动化测试", "执行性能与稳定性验证", "完善质量门禁和缺陷分析"]},
]


def generate_demo_jds(count: int = 100) -> list[dict]:
    companies = [("星河智联科技", "互联网 / 企业服务", "500-999人"), ("云岫数字科技", "云计算", "1000-9999人"), ("矩阵智能", "人工智能", "100-499人"), ("新核数据", "大数据", "500-999人"), ("远澜网络", "互联网", "1000-9999人"), ("启明工业智能", "智能制造", "500-999人"), ("融信科技", "金融科技", "1000-9999人"), ("极光软件", "软件服务", "100-499人"), ("深蓝物联", "物联网", "500-999人"), ("万象云原生", "云计算", "100-499人"), ("智谷信息", "企业服务", "500-999人"), ("青云研发中心", "互联网", "1000-9999人")]
    locations = [("北京", "海淀区"), ("上海", "浦东新区"), ("杭州", "余杭区"), ("深圳", "南山区"), ("合肥", "高新区"), ("成都", "高新区"), ("南京", "雨花台区"), ("武汉", "洪山区")]
    benefits_pool = ["五险一金", "补充医疗", "年度体检", "弹性工作", "餐补", "交通补贴", "带薪年假", "技术培训", "年终奖", "股票期权"]
    now = datetime.now(UTC).replace(microsecond=0)
    items: list[dict] = []
    for i in range(count):
        tpl = COMPUTER_JOB_TEMPLATES[i % len(COMPUTER_JOB_TEMPLATES)]
        skills = "、".join(tpl["skills"])
        company, industry, company_size = companies[i % len(companies)]
        city, district = locations[(i + i // len(COMPUTER_JOB_TEMPLATES)) % len(locations)]
        salary_min, salary_max = tpl["salary"]
        salary_min += i % 4
        salary_max += i % 7
        exp_min, exp_max = tpl["experience"]
        published_at = now - timedelta(days=i % 21, hours=i % 11)
        change_type = ("new", "updated", "offline")[i % 3] if i < 18 else "unchanged"
        job_status = "offline" if change_type == "offline" else "active"
        benefits = [benefits_pool[(i + j * 2) % len(benefits_pool)] for j in range(5)]
        content = (f"岗位：{tpl['title']}。公司：{company}，地点：{city}{district}，薪资：{salary_min}-{salary_max}K·{13 + i % 4}薪。" f"经验：{exp_min}-{exp_max}年，学历：{tpl['education']}。职责：{'；'.join(tpl['responsibilities'])}。" f"要求：熟悉{skills}，具备工程化交付能力，理解分布式系统、数据质量与团队协作。" f"福利：{'、'.join(benefits)}。加分：有生产环境项目、开源项目或技术方案沉淀。")
        sid = f"jd_{i + 1:03d}"
        common = {
            "source_id": sid, "source_type": "jd", "domain": tpl["domain"], "title": tpl["title"], "content": content,
            "quality_score": 82 + (i % 15), "dedup_hash": sha1(content.encode("utf-8")).hexdigest()[:12],
            "company": company, "company_industry": industry, "company_size": company_size,
            "salary_min_k": salary_min, "salary_max_k": salary_max, "salary_months": 13 + i % 4,
            "city": city, "district": district, "experience_min_years": exp_min, "experience_max_years": exp_max,
            "education": tpl["education"], "skill_tags": tpl["skills"], "responsibilities": tpl["responsibilities"],
            "benefits": benefits, "published_at": published_at.isoformat(),
            "changed_at": (now if change_type != "unchanged" else published_at).isoformat(),
            "source_platform": "结构化模拟样本", "source_url": f"https://demo.talentgraph.local/synthetic/{sid}",
            "job_status": job_status, "change_type": change_type,
        }
        common["metadata"] = {key: value for key, value in common.items() if key not in {"source_id", "source_type", "domain", "title", "content", "quality_score", "dedup_hash", "metadata"}}
        items.append(common)
    return items


DEMO_RESUME = """
候选人：陈明。应聘 Java 后端工程师。三年后端开发经验，参与电商订单系统、支付回调服务和库存同步系统。
技术栈包括 Java、Spring Boot、MySQL、Redis、RabbitMQ、Docker。负责订单模块接口设计、Redis 缓存优化、
慢 SQL 排查和服务监控接入。了解 Kubernetes，有一次灰度发布和故障回滚经验。
"""
