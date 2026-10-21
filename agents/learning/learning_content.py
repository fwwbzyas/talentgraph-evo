from __future__ import annotations


SKILL_ALIASES = {
    "Agent": ["AI Agent", "智能体", "Agent开发"],
    "LLM": ["大语言模型", "大模型", "LLM"],
    "RAG": ["RAG", "检索增强生成", "知识库问答"],
    "工具调用": ["Function Calling", "工具调用", "MCP"],
    "向量数据库": ["向量数据库", "Qdrant", "Milvus", "FAISS"],
    "Prompt Engineering": ["Prompt Engineering", "提示词工程"],
    "Spring Boot": ["Spring Boot", "SpringBoot"],
    "CI/CD": ["CI/CD", "持续集成", "持续部署"],
    "自动化测试": ["自动化测试", "pytest", "Selenium"],
    "边缘计算": ["边缘计算", "Edge Computing"],
    "设备接入": ["物联网设备接入", "MQTT", "IoT平台"],
}

SKILL_CONTENT = {
    "Python": (["语法、数据结构与函数", "面向对象、异常与模块管理", "虚拟环境、依赖和工程结构", "完成一个可测试的小型服务"], ["独立实现并运行一个 Python 项目", "使用 pytest 编写核心测试"]),
    "Java": (["Java语法、集合与泛型", "并发编程与JVM基础", "网络、数据库和工程化", "完成后端接口服务"], ["实现带数据库的 REST API", "解释线程安全和JVM内存模型"]),
    "RAG": (["文档解析、切分与元数据", "Embedding和向量检索", "召回、重排与上下文构建", "回答质量评测与幻觉防控"], ["构建可引用证据的知识库问答", "完成召回率和答案忠实度评测"]),
    "Agent": (["Agent状态、工具和记忆", "任务拆解与工作流编排", "异常恢复和人工介入", "Agent评测与可观测性"], ["实现一个可恢复的多步骤Agent", "保存完整运行轨迹并完成评测"]),
    "LLM": (["Transformer与注意力机制", "提示词、结构化输出与上下文", "模型调用、成本和延迟", "微调、评测与安全边界"], ["完成结构化大模型应用", "能比较提示、RAG和微调方案"]),
    "LangChain": (["模型、Prompt与Runnable", "文档加载和检索链", "工具封装与Agent", "回调、追踪和部署"], ["实现带检索和工具调用的应用"]),
    "LangGraph": (["状态图与节点边", "条件路由和循环", "检查点与人工介入", "多智能体编排"], ["实现可持久化、可恢复的状态工作流"]),
    "向量数据库": (["向量与相似度度量", "索引结构和过滤", "写入、检索和更新", "召回评测与容量规划"], ["建立向量集合并实现混合检索"]),
    "MySQL": (["关系模型与SQL", "索引和执行计划", "事务、锁与隔离级别", "备份和性能诊断"], ["完成表设计和慢查询优化"]),
    "Redis": (["核心数据结构", "缓存、过期与淘汰", "持久化和高可用", "缓存穿透、击穿和一致性"], ["设计高并发缓存方案并说明一致性策略"]),
    "Kafka": (["主题、分区和消费组", "生产与消费语义", "可靠性和顺序性", "监控与容量规划"], ["实现消息链路并处理重复和失败消息"]),
    "Spring Boot": (["IoC、配置与Web接口", "数据访问和事务", "鉴权、测试与异常处理", "微服务部署与观测"], ["完成可测试的业务服务"]),
    "Hadoop": (["HDFS与分布式存储", "MapReduce计算模型", "资源调度和生态组件", "集群运维和性能"], ["解释数据分片和容错机制"]),
    "Spark": (["RDD、DataFrame与Spark SQL", "Shuffle和执行计划", "流批处理", "性能调优与故障排查"], ["完成数据处理任务并优化执行计划"]),
    "Flink": (["流处理模型和时间语义", "状态与Checkpoint", "窗口、Watermark和Exactly-once", "作业部署与调优"], ["实现带状态的实时计算任务"]),
    "Hive": (["数据仓库分层", "Hive SQL与分区", "文件格式和执行引擎", "数仓建模与治理"], ["完成分层数仓模型和核心指标SQL"]),
    "Docker": (["镜像、容器和网络", "Dockerfile与多阶段构建", "Compose编排", "安全与镜像优化"], ["容器化一个完整Web服务"]),
    "Kubernetes": (["Pod、Deployment和Service", "配置、存储与网络", "调度、弹性和健康检查", "可观测性与故障排查"], ["部署可滚动升级的服务"]),
    "Linux": (["文件、权限与进程", "网络和系统服务", "Shell与自动化", "日志和性能排查"], ["通过命令定位CPU、内存和网络问题"]),
    "MQTT": (["发布订阅与主题", "QoS和会话", "保留消息与遗嘱", "认证、安全和设备规模化"], ["实现设备到平台的可靠消息链路"]),
    "C++": (["语法、对象模型和STL", "内存、RAII与智能指针", "并发和性能", "构建、调试与测试"], ["实现资源安全的C++模块"]),
    "PyTorch": (["Tensor与自动求导", "模型、损失和优化器", "数据加载与训练循环", "推理、评估和部署"], ["训练并评估一个神经网络模型"]),
}

DEPENDENCIES = {
    "Agent": ["Python", "LLM"], "RAG": ["Python", "向量数据库"], "LangChain": ["Python", "LLM"],
    "LangGraph": ["Python", "LangChain"], "Spring Boot": ["Java"], "Spark": ["SQL"], "Flink": ["Java"],
    "Hive": ["SQL", "Hadoop"], "Kubernetes": ["Docker", "Linux"], "MQTT": ["TCP/IP"],
    "PyTorch": ["Python"], "TensorFlow": ["Python"], "自动化测试": ["Python"],
}


def aliases_for(skill: str) -> list[str]:
    return list(dict.fromkeys([skill, *SKILL_ALIASES.get(skill, [])]))


def content_for(skill: str) -> tuple[list[str], list[str]]:
    return SKILL_CONTENT.get(
        skill,
        (
            [f"理解{skill}的核心概念和适用边界", f"掌握{skill}的常用工具与基本操作", f"完成一个包含{skill}的岗位场景练习", f"总结常见错误、性能与安全问题"],
            [f"能够独立完成一个{skill}实践任务", f"能够用证据解释{skill}方案的选择"],
        ),
    )

