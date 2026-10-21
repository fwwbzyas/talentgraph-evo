# 讯飞智聘数据采集与三维知识图谱二次开发提示词

> 用途：本文件既是当前实现的代码级分析说明，也是一份可直接交给其他大模型继续开发的上下文提示词。结论以仓库代码和 `data/talentgraph.db` 中的当前持久化配置为准，而不是只依据 README 或设计文档。

## 一、项目总体开发目标

讯飞智聘不是普通招聘信息展示网站，而是一个面向企业招聘决策、岗位治理和求职者能力成长的新一代信息技术岗位能力平台。项目聚焦以下四个领域：

1. 人工智能；
2. 大数据；
3. 智能系统；
4. 物联网。

系统希望形成一条可追溯的业务闭环：

```text
招聘与社区多源采集
  -> 标准化、去重、质量审核、版本保存
  -> 岗位资产与辅助技术信号分库存储
  -> 岗位族、岗位实例、技能、职责和 JD 证据图谱
  -> 岗位与技能随时间的演化分析
  -> 新岗位候选发现
  -> 候选人简历/对话/任务评估
  -> 人岗匹配、能力差距和学习建议
```

项目的核心价值不是“收集尽可能多的招聘信息”，而是让岗位定义、技能要求、趋势判断和匹配结论都能够追溯到合法采集的原始证据。

主要技术结构：

- 后端：FastAPI、Pydantic、多 Agent 服务、SQLite 持久化；
- 前端：React、Vite、Three.js、Cytoscape.js；
- 当前图存储：主要由 Python/Pydantic 结构和接口动态生成，Neo4j 仅在部署设计中声明，尚未成为实际主存储；
- LLM：OpenAI 兼容接口，可选；未配置时走确定性规则和状态机；
- 主要入口：`apps/api/main.py`、`core/orchestrator.py`、`apps/web/src/App.jsx`。

## 二、数据采集部分的实际运作逻辑

### 2.1 数据源及证据等级

正式招聘主数据源：

- BOSS 直聘：`agents/data/boss_browser.py`；
- 智联招聘：`agents/data/zhaopin_browser.py`；
- 前程无忧（51job）：`agents/data/job51_browser.py`；
- 猎聘：`agents/data/liepin_browser.py`。

四者采用浏览器辅助采集，不绕过验证码、WAF 或平台验证。BOSS/智联保留原实现与原采集策略；51job/猎聘共用 `agents/data/supplemental_recruitment.py` 的低量调度、检查点、脱敏和风险停止逻辑。采集结果经过同一标准化和质量治理后写入 `job_assets`，可以成为岗位和技能图谱的正式证据。猎聘搜索 URL 受 robots 规则限制，只有设置 `TALENTGRAPH_LIEPIN_ROBOTS_ACKNOWLEDGED=1` 后才启用。

辅助信号源：

- Remote OK；
- Arbeitnow；
- Hacker News；
- Stack Overflow；
- GitHub。

辅助源写入 `community_signals`，标记为 `auxiliary_only`，只能用于趋势观察、搜索词扩展和新岗位候选置信度增强，不能单独创建正式岗位或发布正式能力节点。

### 2.2 当前实际限定的城市

读取 `data/talentgraph.db` 中 `app_settings.collection_strategy` 后，四个招聘源共享 **12 个城市**：

```text
北京、上海、广州、深圳、杭州、南京、苏州、成都、武汉、西安、合肥、长沙
```

说明：

- `contracts/schemas.py` 的模型默认值是 `cities=["全国"]`；采集器对象初始化时也默认全国。
- `agents/data/city_catalog.py` 的离线兜底目录恰好也是上述 12 城，但 `data/recruitment_city_catalog.json` 可以缓存平台返回的更大城市全集。
- 当前数据库持久化策略明确选择了上述 12 城，所以常规调度应按 12 城运行。
- `scripts/isolate_out_of_scope_jobs.py` 也使用相同的 12 城作为保留范围，用于归档范围外岗位。
- `scripts/full_recruitment_crawl.py` 的 `--city-scope` 默认值是 `all`。在该模式下，脚本会读取接口返回的全部可选城市，而不一定只跑上述 12 城；只有使用 `--city-scope configured` 时才严格采用当前配置城市。二次开发时必须避免把“城市目录全集”“模型默认全国”和“当前实际启用 12 城”混为一谈。

### 2.3 当前实际限定的岗位搜索词

BOSS、智联、51job、猎聘以及全量采集脚本共用 **24 个岗位搜索词**，可按四个领域理解：

| 领域 | 数量 | 搜索词 |
| --- | ---: | --- |
| 人工智能 | 8 | AI Agent 工程师、大模型应用工程师、RAG 工程师、机器学习工程师、算法工程师、多模态工程师、模型评测工程师、AI 平台工程师 |
| 大数据 | 7 | 大数据开发工程师、实时计算工程师、Flink 工程师、数据平台工程师、数据治理工程师、数据仓库工程师、湖仓架构师 |
| 智能系统 | 4 | 智能系统工程师、机器人软件工程师、边缘智能工程师、自动驾驶系统工程师 |
| 物联网 | 5 | 物联网平台工程师、物联网嵌入式工程师、IoT 工程师、边缘网关工程师、固件工程师 |
| 合计 | 24 | — |

常规配置下，每个招聘源共有 `12 × 24 = 288` 个“城市—搜索词”组合。当前持久化策略中：

- BOSS：启用，`discovery` 模式，每次最多 100 条，间隔 10080 分钟（7 天）；
- 智联：启用，`monitor` 模式，每次最多 100 条，间隔 10080 分钟（7 天）；
- 51job：适量 `discovery`，默认每次 36 条，间隔 1440 分钟（24 小时）；
- 猎聘：同为每次 36 条、每日补充，需先完成人工研究用途确认；验证码/WAF 只静默暂停该来源本轮。
- 四个源合计 1152 个配置组合；原 `scripts/full_recruitment_crawl.py` 仍只运行 BOSS/智联，避免新来源在已有大数据量上执行全量放大。

`scripts/full_recruitment_crawl.py` 若选择两个源、`both` 模式且城市范围为 configured，则工作项为：

```text
2 个阶段（discovery + monitor）× 2 个招聘源 × 12 城 × 24 词 = 1152 个工作项
```

该脚本带检查点、失败重连、分页游标和结束页判断，可以恢复长时间遍历。

### 2.4 “搜索词限定”不等于最终岗位准入

岗位是否进入主数据和知识图谱，还会经过多层限制：

1. 搜索入口限制：仅使用以上 24 个搜索词与配置城市组合查询。
2. 卡片标题初筛：标题必须命中 `工程师|开发|研发|算法|架构|测试|数据|嵌入式|智能体|Agent` 之一。
3. 排除词过滤：BOSS 排除销售、客服、班主任、课程、招生、运营、市场、合伙人、兼职；智联排除销售、客服、招生、课程顾问、运营、市场、兼职。
4. 四领域分类：`agents/data/normalization.py` 根据标题、正文和标签中的中英文领域关键词，将数据归入人工智能、大数据、物联网或智能系统。
5. 技术岗位校验：标题需具备工程师、开发、算法、架构、分析师、平台工程师等技术角色特征；销售、市场、设计、招聘等非技术标题会被排除。
6. 治理审核：范围外、非岗位内容为硬拒绝；标题正文冲突、技能膨胀、薪资异常进入人工复核；质量分低于阈值的记录被拒绝。
7. 证据发布：只有状态为 accepted 的招聘记录可以发布到正式图谱；社区信号始终不能发布正式能力。

因此，24 个关键词是“召回范围”，四领域分类和治理规则才是“最终准入范围”。

### 2.5 数据采集主流程

```text
CollectionStrategy / DataCollectionRequest
  -> DataCollectionAgent 按来源并发执行
  -> BOSS/智联/51job/猎聘按 城市×关键词×页码 轮询
  -> 搜索卡片初筛并进入详情页获取完整 JD
  -> normalize_recruitment_item 标准化字段
  -> DataGovernanceAgent 规则审核
  -> 去重、身份指纹、内容摘要、版本判断
  -> accepted 招聘数据写 job_assets
  -> rejected/manual_review 写审计与质量隔离记录
  -> 社区数据单独标准化后写 community_signals
  -> 岗位新增、重发、真实修改和下线进入观测/版本链
```

关键文件：

- `agents/data/collection.py`：采集编排、并发、策略应用、分库存储；
- `agents/data/boss_browser.py`：BOSS 搜索、详情采集、分页游标；
- `agents/data/zhaopin_browser.py`：智联搜索、详情采集、分页游标；
- `agents/data/job51_browser.py`：51job 浏览器响应捕获与字段适配；
- `agents/data/liepin_browser.py`：猎聘渲染卡片、详情 JD 与字段适配；
- `agents/data/supplemental_recruitment.py`：新增来源共享的低量采集、脱敏、检查点和风控停止；
- `agents/data/source_policy.py`：正式招聘源白名单、显示名称和默认采集量；
- `agents/data/normalization.py`：领域、字段、技能标准化；
- `agents/data/governance.py`：质量规则、拒绝和灰区复核；
- `agents/data/sources.py`：社区辅助源适配器；
- `core/store.py`：岗位、版本、观测、审计和配置持久化；
- `scripts/full_recruitment_crawl.py`：长时间全量遍历与断点恢复。

## 三、三维知识图谱的运作逻辑

### 3.1 数据入口和后端构图

前端 `apps/web/src/ThreeGraph.jsx` 请求：

```http
GET /api/graph/temporal?max_nodes=1800
```

紧凑首页模式使用 `max_nodes=420`。接口在 `apps/api/main.py` 中调用 `KnowledgeGraphService.build_career_galaxy()`。

后端只把以下岗位作为三维图的正式岗位基础：

- `job_status == "active"`；
- `source_platform` 为 `boss`、`zhaopin`、`51job` 或 `liepin`；
- 满足可选的领域和来源过滤；
- 依据质量分和发布时间排序，在“月份×领域”桶中按配额采样，最多返回接口指定的岗位节点数。

时间字段优先使用 `published_at`，缺失时使用 `collected_at`，当前代码按月生成 `YYYY-MM` 时间切片。

### 3.2 三维空间含义

图的空间不是物理仿真，而是业务语义布局：

- Z 轴：月份时间轴，每相邻月份间隔 34 个场景单位，越后的月份 Z 值越小；
- X/Y 平面：岗位领域、岗位族和经验层级的关系布局；
- 四个领域：人工智能、大数据、智能系统、物联网分别占据不同方向/弧带；
- 岗位族：位于领域中心附近，作为局部中心节点；
- 岗位实例：围绕所属岗位族分布；
- 技能节点：围绕岗位族形成局部轨道；
- 经验年轮：inner、middle、outer 分别表达高级/资深、具有一定经验、初级或经验不限岗位。

前端会重新计算更适合显示的场景位置：全局模式按四领域扇区排列；选中单领域时采用聚类式年轮布局；单时间切片或领域模式使用俯视平面视角，全时段使用可旋转的 3D 虫洞视角。

### 3.3 节点类型

1. `family`：岗位族节点，包含岗位数、企业数、城市、Top 技能、技能覆盖率、职责摘要和证据 ID。
2. `job`：真实岗位实例，包含公司、城市、薪资、经验、学历、技能、职责、来源链接和质量分。
3. `skill`：岗位族在某个月份的技能节点，包含支持岗位数和覆盖率；真实技能节点可以发布能力。
4. `signal`：社区辅助信号，最多 80 个，以已有技能为挂载目标；`canPublishAbility=false`，只作趋势观察。

### 3.4 关系类型

- `family_member`：岗位族包含岗位实例；
- `requires_skill`：岗位族需要某项技能，权重参考覆盖率；
- `evolution`：同一岗位族相邻月份之间的演化连接，记录新增技能、移除技能、上升技能和岗位数变化；
- `auxiliary_signal`：社区信号到技能的低权重辅助关系；
- `job_similarity`：同领域岗位族的技能相似；
- `possible_fusion`：技能高度重叠的潜在岗位融合；
- `talent_mobility`：跨领域但技能重叠的潜在人才迁移；
- `skill_cooccurrence`：在同一批 JD 中共同出现的技能关系。

岗位族的 `evolutionState` 根据相邻切片岗位数判为 `emerging`、`declining`、`exited` 或 `stable`。技能变化根据覆盖率差异产生 `added`、`strengthened`、`weakened` 或 `stable`。

### 3.5 前端渲染和交互

- Three.js 创建 Scene、PerspectiveCamera、WebGLRenderer 和 OrbitControls；
- 岗位实例使用 `InstancedMesh` 批量绘制，以降低大量节点的 draw call；
- 岗位族用低面数二十面体，技能用八面体，辅助信号使用线框材质；
- 月份层由同心圆和月份标签组成，中轴螺旋粒子表现“时间虫洞”；
- 演化边上有流动粒子，用颜色区分形成、增强、减弱和退出；
- 悬停通过 Raycaster 命中节点并高亮邻接关系；
- 单击节点会聚焦摄像机并展开最多 8 个技能子节点；同时最多保留 3 个父节点的技能轨道；
- 双击岗位族切换到该岗位族的真实岗位实例视图；
- 支持领域筛选、月份滑块、节点搜索、缩放、重置和全屏；
- 全局概览每月最多保留 18 个主要岗位族，单月最多 42 个；技能视图每个岗位族最多保留 5 个技能，以控制场景规模。

### 3.6 必须注意的真实数据与推演数据问题

当前实际代码与部分旧设计说明存在差异：

- `build_career_galaxy()` 固定建立最近 12 个月的月轴；
- 如果数据库的真实招聘数据没有覆盖完整 12 个月，代码会基于最新真实岗位族，使用哈希种子、波动函数和趋势因子反向生成缺失月份；
- 这些节点被标记为 `isSimulated=true`、`evidenceStatus=simulated_historical_projection`、`canPublishAbility=false`，且没有 `evidenceIds`；
- 返回值也包含 `simulation_notice` 和每层的 `isSimulated/dataLabel`；
- 但前端部分详情文案仍可能统一显示“基于当前真实招聘样本统计”，容易让用户误解推演节点为真实历史。

二次开发不得删除这些标记或把推演数据包装成真实招聘证据。更推荐的产品策略是：默认只展示真实时间切片；如果需要演示推演，应提供显著的“真实/推演”开关、水印、图例和独立统计，并禁止推演数据进入岗位趋势结论、匹配报告及正式证据接口。

## 四、当前实现的关键风险与二次开发优先级

### P0：数据可信度

- 统一 README、设计文档和实际代码对时间粒度及推演数据的描述；
- 在三维节点详情、时间轴、统计卡片和导出结果中显式显示 `isSimulated`；
- 确保模拟节点永远不能进入正式能力发布、趋势结论和候选人匹配证据；
- 对每条图关系保留来源、计算方法、证据 ID 和推断标记。

### P0：采集合规和稳定性

- 不绕过登录、验证码、反爬限制或站点授权；
- 给采集策略增加速率限制、失败退避、会话状态、检查点和可审计日志；
- 把城市全集、启用城市和岗位搜索词做成版本化配置，避免代码常量与数据库配置漂移；
- 明确 BOSS discovery 与智联 monitor 的业务差异，并提供可观测的组合完成率。

### P1：时间演化真实性

- 优先从 `job_versions` 和 `job_observations` 重建真实历史，而不是从当前快照反推；
- 只有达到足够真实历史跨度后才计算增长、减弱和退出；
- 新增最小样本量、置信区间和多源一致性门槛。

### P1：图谱性能和可维护性

- 后端为时间图增加分页、层级加载、ETag/缓存和预计算；
- 前端避免每次筛选都完全销毁并重建 WebGL 场景；
- 将节点/边 schema 提取为共享契约并补充校验；
- 为大量节点考虑 Web Worker、LOD、对象池和 GPU picking。

### P2：生产化

- 将 SQLite 迁移到生产数据库并补齐租户隔离；
- 评估 Neo4j 是否真正必要，避免仅为“使用图数据库”而迁移；
- 加入任务队列、权限、隐私删除、数据保留策略、监控告警和独立金标评测集。

## 五、可直接复制给其他大模型的二次开发提示词

```text
你是一名资深全栈架构师、数据工程师和知识图谱工程师。请在讯飞智聘仓库中继续开发，先阅读代码并验证事实，不要只依赖 README。

【产品目标】
本项目面向企业招聘决策、岗位治理和求职者能力成长，聚焦人工智能、大数据、智能系统、物联网。系统将多源招聘采集、数据治理、证据化岗位能力图谱、岗位演化、新岗位发现、候选人评估和人岗匹配连接成闭环。所有正式结论必须可追溯到招聘 JD 证据。

【当前技术栈】
- 后端：FastAPI + Pydantic + Python Agent 服务 + SQLite。
- 前端：React + Vite + Three.js + Cytoscape.js。
- LLM：可选 OpenAI 兼容接口；未配置时必须保持确定性流程可运行。
- Neo4j/PostgreSQL 目前主要存在于部署设计，不能假设业务已完成迁移。

【采集现状】
- 正式招聘源：BOSS 直聘、智联招聘、前程无忧、猎聘，写入 job_assets；后两者默认低量采样。
- 辅助源：Remote OK、Arbeitnow、Hacker News、Stack Overflow、GitHub，写入 community_signals；辅助信号不能单独发布岗位或能力。
- 四个招聘源统一限定 12 城：北京、上海、广州、深圳、杭州、南京、苏州、成都、武汉、西安、合肥、长沙。
- 当前共有 24 个岗位搜索词：
  AI Agent 工程师、大模型应用工程师、RAG 工程师、机器学习工程师、算法工程师、多模态工程师、模型评测工程师、AI 平台工程师、
  大数据开发工程师、实时计算工程师、Flink 工程师、数据平台工程师、数据治理工程师、数据仓库工程师、湖仓架构师、
  智能系统工程师、机器人软件工程师、边缘智能工程师、自动驾驶系统工程师、
  物联网平台工程师、物联网嵌入式工程师、IoT 工程师、边缘网关工程师、固件工程师。
- 搜索后仍需经过标题包含/排除词、四领域分类、技术岗位判断、质量分、范围审核和证据发布审核。
- scripts/full_recruitment_crawl.py 默认 --city-scope all 可能扩展到城市目录全集；需要严格跑 12 城时使用 configured 或修改为显式策略。

【三维图谱现状】
- 前端入口 apps/web/src/ThreeGraph.jsx，请求 GET /api/graph/temporal。
- 后端核心 agents/job_graph/knowledge_graph.py 的 build_career_galaxy()。
- 正式岗位只取 active 且来源在统一招聘源白名单中的记录（boss/zhaopin/51job/liepin）。
- 节点：family、job、skill、signal。
- 关系：family_member、requires_skill、evolution、auxiliary_signal、job_similarity、possible_fusion、talent_mobility、skill_cooccurrence。
- Z 轴表示月份；X/Y 表示领域、岗位族、技能和经验年轮。
- 当前代码会构建最近 12 个月，并在真实数据不足时生成 isSimulated=true 的确定性历史推演。模拟节点没有正式证据、canPublishAbility=false，绝不能当成真实历史。

【不可违反的约束】
1. 不绕过验证码、登录、平台授权、速率限制或数据使用条款。
2. 不把社区信号、LLM 推断或模拟历史当作正式招聘证据。
3. 不删除 raw record、source_url、evidenceIds、版本差异、审计原因和模拟标记。
4. 规则负责阈值和准入，LLM 只做受控抽取、摘要或灰区辅助判断。
5. 修改前先确认当前数据库配置、接口 schema 和测试；保护用户已有改动。
6. 新功能必须同时考虑后端契约、前端呈现、数据迁移、权限、审计、性能和测试。

【开发任务】
请完成以下用户指定任务：
<在此填写具体二次开发需求>

【执行方式】
1. 先定位相关文件和调用链，给出当前行为、根因、影响面和最小改动方案。
2. 明确区分“代码默认值、数据库当前配置、接口可选项、运行时覆盖参数”。
3. 实施后运行相关 pytest、前端构建和必要的接口/视觉验证。
4. 若涉及三维图谱，验证全局、单领域、单月份、岗位族下钻、搜索、证据查看以及真实/模拟数据标识。
5. 若涉及采集，验证城市×关键词组合、分页游标、重复/重发/修改判断、失败恢复、限流和审计落库。
6. 最终交付变更文件、验证结果、剩余风险和可回滚说明。

【验收标准】
- 正式结论均能追溯到真实招聘 evidenceIds/source_url。
- 模拟数据和辅助信号在接口、UI、统计、导出中均有明确标识且不能污染正式结论。
- 12 城和 24 搜索词的实际生效范围可查询、可审计、可版本化，不依赖散落常量。
- 图谱在目标节点规模下交互流畅，无明显内存泄漏，筛选和下钻结果一致。
- 后端测试和前端生产构建通过；新增逻辑有针对性测试。
```

## 六、二次开发时建议优先阅读的文件

```text
README.md
apps/api/main.py
core/orchestrator.py
core/store.py
contracts/schemas.py
agents/data/collection.py
agents/data/boss_browser.py
agents/data/zhaopin_browser.py
agents/data/job51_browser.py
agents/data/liepin_browser.py
agents/data/supplemental_recruitment.py
agents/data/source_policy.py
agents/data/city_catalog.py
agents/data/normalization.py
agents/data/governance.py
agents/data/sources.py
scripts/full_recruitment_crawl.py
scripts/isolate_out_of_scope_jobs.py
agents/job_graph/knowledge_graph.py
apps/web/src/ThreeGraph.jsx
apps/web/src/App.jsx
tests/test_data_collection.py
tests/test_boss_crawler_integration.py
tests/test_supplemental_recruitment_sources.py
tests/test_knowledge_graph.py
```

## 七、结论摘要

- 当前常规招聘采集范围：4 个正式招聘源、12 个城市、24 个岗位搜索词、4 个目标技术领域；51job/猎聘采用低量补充策略。
- 岗位准入并非只靠搜索词，还经过标题规则、领域识别、技术角色判断、质量治理和证据发布审核。
- 三维知识图谱以岗位族为中心，把岗位实例、技能、社区信号和月份演化放在同一 Three.js 场景中；Z 轴为月度时间，X/Y 为领域、岗位族和经验年轮。
- 当前三维图同时包含真实月份和补齐的模拟历史月份。模拟数据有后端标记，但前端提示仍需进一步强化，这是当前最重要的可信度改进点。
- 项目总体目标是构建“多源数据治理 + 可追溯岗位能力图谱 + 动态演化 + 人岗决策”的工程化平台，而不是招聘信息聚合页面。
