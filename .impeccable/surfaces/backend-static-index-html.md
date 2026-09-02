---
version: 1
slug: "backend-static-index-html"
primary_target: "backend/static/index.html"
related_targets: []
---

# Surface Brief — `/` 首页（backend/static/index.html）

## Scope 与访客模式

- 范围：统一入口首页（Persuade），替换原深色导航页（全屏粒子 + 6 服务卡片 + GSAP，旧视觉仅作反参考）。
- 模式：**Persuade**——访客决定并行动：体验系统、查源码、看架构、调 API。

## 受众、任务、行动、证据

- 受众：招聘者/技术面试官/Agent 开发者/源码审阅者（实习作品集评估场景，首次访问无上下文）。
- 任务：15 秒内理解这是什么、Agent 做了什么、为什么不是 LLM 套壳、证据在哪、从哪进入。
- 行动：本地一键体验（/BI/、/ai/）、GitHub、技术架构、API 文档；无公网部署，CTA 不写「在线体验」。
- 证据（全部已核实）：102,287 订单；LangGraph 9 节点真实链路；四层 SQL 防护；100 条路由回归；15 条词法检索回归；GLM 真实评测 14/15（P50 1,508ms）；32 个 API；测试数须 pytest 实收后才上页面；v1.0.3。

## 已确认方向

**单步调试器 Step-Through**（concept-seed 指定，用户 2026-09-02 确认，seed 5f9747fd）：
首屏 = 一次真实 Agent 查询的单步调试会话；左 60% pipeline 断点列表按真实顺序整块浸色点亮、已完成 ghost 化；右 40% inspect 面板展示 intent / SQL / sources / usage 真实值。
捐赠纪律：ghost 化+落位高亮+细节放大框（brick）、路径实线/虚线（sewing）、整块浸色+分段计数（racing）、一句话速读行（wildstyle）、不可用=设计过的 ghost 态+瞬时切换（seven-segment）。

## 难忘时刻

访客点击「单步执行」或滚动进入时，九个真实节点依次点亮，inspect 面板同步切换出真实的 SQL（含 LIMIT 500 与 MAX_EXECUTION_TIME）、来源文件名与 Token 数——证明机制的证据就是页面本身。

## 约束

- 保留服务状态检测（/api/monitor/services-status 轮询）与全部入口路由：/BI/、/ai/、/docs、/demo、/monitor、/health-panel。
- 不引入框架/构建链；原生 HTML/CSS/少量 JS；无全屏粒子、无 GSAP 依赖。
- 动效仅：节点按真实顺序点亮、真实指标视口内计数、区块轻微入场；支持 prefers-reduced-motion、失焦降级、窄屏降级、内容默认可见。
- 中文为主；禁词：99.99% Accuracy / 企业级 / 生产级 / 百万用户 / 大幅提升效率；无隐藏思维链暗示。
- 字体：中文系统栈 + JetBrains Mono（代码/SQL/数据），不阻塞首屏。

## 未决事项

- 测试总数以 pytest 实收为准（README 声明 238；静态函数计数 195）。
- /demo、/monitor、/health-panel 三页仅保留入口与状态检测，本轮不重设计（后续阶段再议）。
