# Resume Gold 100 Benchmark

## 数据集说明

本数据集包含100份高拟真虚构中文技术简历，所有候选人均为合成匿名角色，不含电话、邮箱、身份证号或真实联系地址。每人提供DOCX、可复制中文PDF、TXT和增强gold JSON。

覆盖人工智能、大数据、智能系统、物联网四个领域，各25人；包含16种细分岗位、初级/中级/高级三级、易/中/难三级，以及calibration/regression/blind三类切分（20/30/50）。每份gold保留旧字段，并补充候选人画像、分组技能、技能证据、教育与工作时间线、STAR项目、优势弱点和质量场景。

## 质量与局限

简历内容由确定性模板、岗位词表和量化情境组合生成，重点模拟可解析的职责边界、技术动作与结果证据，不代表真实招聘市场分布，也不能替代经授权的真实简历标注集。唯一性门禁只保证样本文本与关键事实不重复；格式可读性、时间线和字段覆盖通过本地自动化检查，语义真实性、岗位胜任度和跨模型泛化仍需独立人工抽检。

## 生成质量门禁

本次生成门禁结果：100/100 条记录、四领域各25条、16种岗位、8种排版样式、100份唯一正文；初级正文均不少于700字，中高级正文均不少于900字，并逐条校验章节、STAR项目、量化结果、时间线、技能证据、文件存在性和hash。

## Run Status

### local

- Status: `completed`
- Count: `100`
- Processing success rate: `100.0%`
- Usable parse rate: `100.0%`
- Macro-F1: `0.9022`
- Timing: mean `236.2ms`, P50 `217.1ms`, P95 `352.9ms`, max `674.9ms`
- Provider: remote_success `0` (text LLM only), text fallback `0`, vision fallback `0`

本次接管仅运行本地解析评估；未配置远程模型，因此没有启动远程评估。 Image-only empty results are never counted as usable parses.
