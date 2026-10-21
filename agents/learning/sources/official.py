from __future__ import annotations

import hashlib

from ..models import CourseDocument


RESOURCES = [
    (["Python", "自动化测试"], "Python 官方教程", "https://docs.python.org/zh-cn/3/tutorial/", "Python Software Foundation", "从语法、数据结构到模块、异常和类的免费官方教程。", "入门"),
    (["Java"], "Dev.java Java 学习中心", "https://dev.java/learn/", "Oracle Java", "Java语言、API、集合、I/O与工程实践的官方学习资料。", "入门"),
    (["Spring Boot", "微服务"], "Spring 官方入门指南", "https://spring.io/guides", "Spring", "通过可运行示例学习Spring Boot、数据访问、REST与微服务。", "实战"),
    (["RAG", "LangChain"], "LangChain RAG 教程", "https://python.langchain.com/docs/tutorials/rag/", "LangChain", "从文档加载、切分、检索到回答生成的官方RAG教程。", "实战"),
    (["LangGraph", "Agent"], "LangGraph 官方教程", "https://docs.langchain.com/oss/python/langgraph/quickstart", "LangChain", "状态图、持久化、人机协作和多智能体工作流教程。", "进阶"),
    (["向量数据库", "RAG"], "Qdrant 快速入门", "https://qdrant.tech/documentation/quick-start/", "Qdrant", "向量集合、写入、过滤和相似度检索的免费官方教程。", "实战"),
    (["LLM", "PyTorch", "深度学习"], "PyTorch 官方教程", "https://pytorch.org/tutorials/", "PyTorch", "覆盖张量、训练、视觉、NLP和模型部署的官方教程集合。", "综合"),
    (["TensorFlow", "深度学习"], "TensorFlow 官方教程", "https://www.tensorflow.org/tutorials?hl=zh-cn", "TensorFlow", "从Keras基础到高级模型训练和部署的官方教程。", "综合"),
    (["Docker"], "Docker Get Started", "https://docs.docker.com/get-started/", "Docker", "容器、镜像、Compose与应用容器化的官方实践课程。", "入门"),
    (["Kubernetes"], "Kubernetes 官方教程", "https://kubernetes.io/zh-cn/docs/tutorials/", "CNCF", "集群、应用部署、服务暴露、伸缩和滚动升级教程。", "实战"),
    (["Kafka"], "Apache Kafka Quickstart", "https://kafka.apache.org/quickstart", "Apache Kafka", "事件流平台的安装、生产消费与Connect入门。", "入门"),
    (["Spark"], "Apache Spark 快速入门", "https://spark.apache.org/docs/latest/quick-start.html", "Apache Spark", "DataFrame、Dataset和Spark应用的官方快速入门。", "入门"),
    (["Flink"], "Apache Flink Training", "https://nightlies.apache.org/flink/flink-docs-stable/docs/learn-flink/", "Apache Flink", "DataStream、状态、事件时间和容错机制的官方学习路径。", "进阶"),
    (["Hadoop", "HDFS"], "Apache Hadoop 教程", "https://hadoop.apache.org/docs/stable/hadoop-project-dist/hadoop-common/SingleCluster.html", "Apache Hadoop", "搭建单节点集群并理解HDFS与MapReduce。", "实战"),
    (["Hive", "数据仓库"], "Apache Hive Language Manual", "https://cwiki.apache.org/confluence/display/Hive/LanguageManual", "Apache Hive", "Hive数据定义、查询、分区和函数的官方学习资料。", "进阶"),
    (["Redis"], "Redis Learn", "https://redis.io/learn/", "Redis", "数据结构、缓存、查询和Redis应用开发的免费课程。", "综合"),
    (["MySQL", "SQL"], "MySQL 官方教程与手册", "https://dev.mysql.com/doc/refman/8.4/en/tutorial.html", "Oracle MySQL", "数据库创建、查询、索引和常用SQL操作教程。", "入门"),
    (["MQTT", "设备接入", "物联网"], "HiveMQ MQTT Essentials", "https://www.hivemq.com/mqtt-essentials/", "HiveMQ", "MQTT发布订阅、QoS、会话和安全机制免费系列课程。", "综合"),
    (["Linux"], "Linux Foundation 免费课程", "https://training.linuxfoundation.org/resources/free-courses/", "Linux Foundation", "Linux、云原生、DevOps和开源技术免费课程目录。", "综合"),
    (["C++"], "LearnCpp", "https://www.learncpp.com/", "LearnCpp", "覆盖现代C++语法、对象、模板、STL和工程实践的免费系统教程。", "综合"),
    (["Prompt Engineering", "LLM"], "Prompt Engineering Guide", "https://www.promptingguide.ai/zh", "DAIR.AI", "提示词技术、应用场景、风险与研究进展的开放学习指南。", "综合"),
]


class OfficialLearningSource:
    source_name = "官方免费课程"

    def search(self, skill: str, limit: int = 5) -> list[CourseDocument]:
        result = []
        target = skill.lower()
        for skills, title, url, instructor, summary, difficulty in RESOURCES:
            if not any(target == item.lower() or target in item.lower() or item.lower() in target for item in skills):
                continue
            resource_id = hashlib.sha1(title.encode("utf-8")).hexdigest()[:16]
            result.append(CourseDocument(
                course_id=f"official:{resource_id}", source=self.source_name, title=title, url=url,
                summary=summary, instructor=instructor, quality_score=92, difficulty=difficulty,
                skills=list(dict.fromkeys([skill, *skills])), content=f"{title}\n{summary}\n覆盖技能：{'、'.join(skills)}",
                raw={"curated": True, "license_note": "仅保存公开元数据和原链接"},
            ))
            if len(result) >= limit:
                break
        return result
