# Surface Brief — `/BI/` BI 数据看板（streamlit_app.py）

## Scope 与访客模式

- 范围：Streamlit BI 看板的浅色视觉精修，覆盖「销售总览」与「RFM 客户分层」两个页面。
- 模式：**Analyze**——业务审阅者进入后筛选数据、比较趋势、定位客户分层，并导出客户明细。
- 非目标：不改 RFM 计算公式、不改分层阈值语义、不改数据加载与缓存策略、不重构页面信息架构。

## 受众、任务、证据

- 受众：技术面试官、业务分析审阅者、源码审阅者。
- 核心任务：快速判断数据规模、销售趋势、平台结构、TOP 商品/用户，以及 RFM 分层后的高价值与流失风险群体。
- 证据：102,287 条订单、RFM 八分层、F×M 价值矩阵、R 评分分布、月度趋势、客户明细与 CSV 导出。
- 必须保留：AGENTS.md 规定的 RFM 八分层配色与评分语义（R≤阈值为高，F/M≥阈值为高）。

## 设计方向

**Light Enterprise Workbench**：把 BI 看板收敛为浅色、低噪声、可扫读的数据工作台。视觉系统从门面首页的深色 Runtime 反相为浅色工作台，但保留同一套纪律：语义色克制、证据文本等宽、数值 tabular-nums、表面靠色调分层而非阴影堆叠。

## 视觉约束

- 色彩：页面只使用少量企业语义色；RFM 分层继续使用 `ENTERPRISE_COLORS_FULL` 的既有八色，不重命名、不改 hex。
- 字体：界面/标题使用 Manrope + Noto Sans SC + 中文系统栈；指标数值、表格数字、代码/版本信息使用 JetBrains Mono 或等宽回退。
- 深度：卡片扁平化，主要靠 `#FFFFFF` / `#F8FAFC` / `#EEF2F7` 三档表面和发丝边框分层；取消常规卡片阴影。
- 图表：Plotly 默认模板保持浅色；非 RFM 图表从 Set3 / Reds / Viridis / 暗色热力图收敛为蓝—青—橙的受控色板。RFM 堆叠图、气泡图和环形图继续走既有分层色。
- 图标：不使用 emoji 作为视觉图标或项目符号；保留必要的方向符号（↑/↓）表达指标变化。
- 布局：桌面端维持宽屏密度；窄屏不得出现横向页面级溢出，图表与表格由组件自身滚动。

## AGENTS.md 硬边界

- 禁止 `st.metric(delta_delta_color=...)`。
- 禁止对含字符串列的 DataFrame 使用 `reindex(..., fill_value=0)`；继续分列 `fillna(0)` / `fillna('其他')`。
- `go.Pie` 继续使用 `labels=`，不得改为 `names=`。
- 分组众数继续保留 `len(x.mode()) > 0` 保护。
- 不改 `assign_segment`、`quantile_scores`、阈值比较方向与缓存键。

## 验收标准

1. `python -m py_compile streamlit_app.py` 通过。
2. 本地 Streamlit 可启动，销售总览与 RFM 页面均能渲染。
3. 桌面与窄屏截图无页面级横向滚动条，核心指标、图表标题、表格文字可读。
4. RFM 八分层色值与 AGENTS.md 完全一致；RFM 计算相关 diff 为空。
5. detect/review 不出现新增 kicker、玻璃模糊、硬偏移阴影、系统显示字体兜底或夸张宣传文案。
