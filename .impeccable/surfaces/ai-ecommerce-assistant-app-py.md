---
version: 1
slug: "ai-ecommerce-assistant-app-py"
primary_target: "ai-ecommerce-assistant/app.py"
related_targets: []
---

# Surface Brief — `/ai/` AI 智能商业分析助手（ai-ecommerce-assistant/app.py）

## Scope 与访客模式

- 范围：AI 助手 Streamlit 界面的浅色视觉精修与状态加固，覆盖聊天主体、侧栏配置、RAG 状态、执行轨迹、SQL/图表/表格证据区、无 Key 与降级提示。
- 模式：**Operate**——访问者配置模型连接，提出业务问题，观察 Agent 路由、检索、SQL 与结果证据，并在失败时知道如何恢复。
- 非目标：不改 Agent Runtime、LangGraph 节点、Text-to-SQL 生成逻辑、SQL 安全拦截、RAG 检索逻辑、缓存键、会话存储、数据库连接策略或反馈落盘格式。

## 受众、任务、证据

- 受众：技术面试官、Agent/LLM 开发者、源码审阅者，以及首次本地运行项目的评估者。
- 核心任务：在 15 秒内判断 AI 助手是否真实可见地执行「路由 → 检索 → SQL → 结果」；配置模型后开始查询；在无 Key、RAG 失败、SQL 失败或无结果时理解当前状态与下一步。
- 证据：模型连接状态、RAG chunk/命中率/延迟、执行轨迹步数与耗时、参考知识来源、只读 SQL、查询耗时、结果表格、图表与 CSV 导出。
- 必须保留：API Key 仅存在当前浏览器会话，不写入 Git、日志、URL 或磁盘；执行轨迹只展示节点动作、耗时与脱敏摘要，不暴露隐藏思维链；Token 无数据时不得伪造为 0。

## 设计方向

**Light Enterprise Workbench — Observability Rail**：聊天主区域延续 BI 的浅色、低噪声、可扫读工作台；执行轨迹、SQL、来源与状态作为「可检查证据栏」呈现。视觉纪律沿用首页 Runtime 的五个语义色，但在浅色界面中降低饱和度：blue=模型/路由，purple=RAG，teal=SQL，orange=安全/警告，green=成功/完成。表面用 `#FFFFFF` / `#F8FAFC` / `#EEF2F7` 三档与发丝边框分层，不用常规卡片阴影。

## 视觉约束

- 色彩：主色收敛为蓝 `#1565C0`，辅助语义色为 teal `#14B8A6`、purple `#8B5CF6`、orange `#F97316`、green `#22C55E`；不得新增高饱和红色渐变图表色板。
- 字体：界面/标题使用 Manrope + Noto Sans SC + 中文系统栈；SQL、节点名、状态标签、耗时、来源分数与表格数字使用 JetBrains Mono 或等宽回退，数值 `tabular-nums`。
- 深度：默认扁平，仅 hover/focus 改背景与边框；聊天消息、输入框、侧栏区块不得使用厚阴影或玻璃模糊。
- 图表：Plotly 全部从暗色模板转为浅色模板，颜色走受控蓝—青—橙—紫序列；坐标网格、hoverlabel 与标题颜色与 BI 看板一致。
- 图标：不使用 emoji 作为视觉图标或项目符号；必要状态用文字徽章、CSS 圆点或短标签表达。业务回答内容本身不主动改写。
- 布局：桌面端保持宽屏密度；侧栏 300–340px；窄屏无页面级横向滚动，SQL/表格/图表由组件自身横向滚动。

## 状态与降级要求

- 无 API Key：聊天输入保持可见但提交前出现明确、可恢复的配置引导；主区域显示降级说明卡，包含「配置模型」「查看示例」「检查数据库/RAG 状态」三个下一步，不只依赖侧栏提示。
- 数据库失败：页面其余部分继续渲染；状态区显示数据库不可用的脱敏原因与恢复建议，不阻塞侧栏和历史。
- RAG 失败：明确显示「RAG 未启用，已降级为纯 SQL 查询模式」，不得伪装为知识检索成功。
- 查询中：步骤指示器显示当前阶段，不得用无意义旋转遮罩阻断整页。
- 查询失败：错误文案说明失败点与恢复动作（检查 Key/Base URL/数据库/稍后重试），并保留用户问题。
- 空结果：区分「SQL 执行无结果」与「无法从回答解析图表数据」，避免误导为系统崩溃。

## AGENTS.md 与产品硬边界

- LLM SQL 必须只读；不得改动 `ensure_read_only_sql`、`guard_read_only_engine`、`AgentRuntime` 或 SQL 方言判断。
- 禁止 `st.metric(delta_delta_color=...)`。
- 不引入 React/Vue/新构建链；仅 Streamlit + Plotly + 原生 HTML/CSS。
- 不新增公网 Demo 暗示、不虚构测试数/性能数/准确率，不使用「企业级」等无证据宣传词。
- 中文为主；技术名词、模型名、API、SQL 保留英文。

## 验收标准

1. `.venv\Scripts\python.exe -m py_compile ai-ecommerce-assistant/app.py` 通过。
2. 本地 Streamlit 可启动，桌面 1440px 与移动 390px 均无页面级横向溢出。
3. 无 API Key 首次打开时，主区域能看到明确降级说明与下一步；侧栏模型连接默认展开。
4. RAG 失败/未启用状态可读且不误报；数据库、模型、RAG 三类状态在侧栏可区分。
5. SQL 块、执行轨迹、参考知识、结果表格、图表与 CSV 导出仍在原有流程中出现；AgentRuntime/SQL 安全相关 diff 为空。
6. `detect.mjs --json ai-ecommerce-assistant/app.py` 不出现新增 kicker、玻璃模糊、硬偏移阴影、系统显示字体兜底、emoji 图标系统或夸张宣传文案。
