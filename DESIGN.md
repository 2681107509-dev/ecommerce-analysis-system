---
name: AI Commerce Intelligence Platform — 门面首页
description: 克制版 AI Runtime + 数据工作台；把 Agent 执行过程当作可单步调试的程序，只在证据可复核处着色。
colors:
  bg: "#0B0D10"
  surface: "#13171D"
  surface-2: "#1A2029"
  line: "rgba(148, 163, 184, 0.12)"
  line-strong: "rgba(148, 163, 184, 0.22)"
  ink: "#F8FAFC"
  ink-2: "#94A3B8"
  ink-3: "#64748B"
  blue: "#3B82F6"
  purple: "#8B5CF6"
  teal: "#14B8A6"
  orange: "#F97316"
  green: "#22C55E"
typography:
  display:
    fontFamily: "Manrope, Noto Sans SC, -apple-system, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "clamp(30px, 4.6vw, 52px)"
    fontWeight: 800
    lineHeight: 1.18
    letterSpacing: "-1.2px"
  title:
    fontFamily: "Manrope, Noto Sans SC, -apple-system, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "28px"
    fontWeight: 800
    lineHeight: 1.3
    letterSpacing: "-0.5px"
  body:
    fontFamily: "Manrope, Noto Sans SC, -apple-system, Segoe UI, Microsoft YaHei, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.6
  label:
    fontFamily: "JetBrains Mono, Cascadia Code, Consolas, monospace"
    fontSize: "10.5px"
    fontWeight: 400
    letterSpacing: "1px"
    fontFeature: "tabular-nums"
rounded:
  xs: "2px"
  sm: "4px"
  md: "8px"
  lg: "10px"
  xl: "14px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
  section: "72px"
components:
  button-primary:
    backgroundColor: "{colors.blue}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: "11px 20px"
  button-ghost:
    backgroundColor: "transparent"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "11px 20px"
  card-surface:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "20px"
---

# Design System: AI Commerce Intelligence Platform — 门面首页

## Overview

**Creative North Star: "The Step-Through Debugger"**

把 Agent 的执行过程当作一个可被单步调试的程序：访问者逐节点观察 `input_safety → load_history → route → … → finalize`，每一步的意图、SQL、来源与耗时都可检查。视觉语言是「克制版 AI Runtime + 企业级数据工作台」——深色技术底，单一等宽字体承载所有机器证据，五个语义色只用来标注子系统而非装饰。密度偏高但不拥挤：章节用 72px 竖向节奏拉开，卡片在 1180px 容器内以 `auto-fit minmax` 自适应排布。所有的数字都带可复核来源；无法在仓库或 CI 中核对的指标一律不出现。动效只服务于「说明真实机制」——节点点亮、指标计数、入场渐显——且全部在 `prefers-reduced-motion` 下降级为终态。

**Key Characteristics:**
- 深色 runtime 底色 `#0B0D10`，三级表面（bg / surface / surface-2）靠色调分层，而非阴影堆叠。
- 五个语义色严格映射子系统：blue=路由/数据，purple=RAG，teal=SQL，orange=安全，green=完成/在线。
- 等宽 JetBrains Mono 专用于「机器与证据」文本（节点名、SQL、指标标签、状态栏）；UI 文案用 Manrope + Noto Sans SC。
- 数值读数一律 `tabular-nums`，克制尺寸（指标 30px），即 seven-segment 式读数纪律。
- 顶栏为不透明实底，无玻璃模糊；动效经 IntersectionObserver 门控，且尊重 `prefers-reduced-motion`。

## Colors

深色技术底 + 五级语义强调色 + 三级中性表面。强调色克制使用：只出现在芯片、节点 tag、数值、状态点与 2px 防护条上，不铺大面积。

### Primary
- **Route Blue** (#3B82F6)：主行动色（主按钮、CTA、导航高亮、路由节点 tag、意图芯片底色）。也是「数据查询」语义色。
- **SQL Teal** (#14B8A6)：SQL 生成与执行语义色；用于节点 tag、`.sql-box` 关键字、来源分数、入口卡片路径、运行步骤序号。
- **RAG Purple** (#8B5CF6)：知识检索语义色；用于节点 tag、SQL 函数名、来源相似度分数、知识类问题帧。
- **Safety Orange** (#F97316)：安全防护语义色；用于安全拦截节点、SQL 字面量、四层防护卡的 2px 顶条与 `LAYER n` 标号、pending 徽章。
- **Online Green** (#22C55E)：完成/在线语义色；用于已执行节点勾选、服务在线点、pass 徽章。

### Neutral
- **Runtime Black** (#0B0D10)：页面底色 `--bg`，调试器左侧管线与检查面板的底色。
- **Panel Surface** (#13171D)：卡片、调试器窗、指标/帧/防护/入口/架构块的表面 `--surface`。
- **Raised Surface** (#1A2029)：层级更高的表面 `--surface-2`，用于标题栏、状态栏、节点当前态、按钮 hover 底。
- **Primary Ink** (#F8FAFC)：主文字 `--ink`。
- **Muted Ink** (#94A3B8)：次级文字 `--ink-2`、导航默认态、数据单元。
- **Faint Ink** (#64748B)：弱化文字 `--ink-3`、等宽标签、脚注、卡片说明。
- **Hairline** (rgba(148,163,184,0.12))：默认描边 `--line`，分隔所有卡片与表格行。
- **Strong Hairline** (rgba(148,163,184,0.22))：较强描边 `--line-strong`，用于调试器外框、当前节点边框、ghost 按钮边框。

### Named Rules
**The Semantic-Five Rule.** 全局只有五个强调色，且各自绑定一个子系统（blue/data、purple/RAG、teal/SQL、orange/safety、green/done）。它们只作芯片、tag、数值、状态点与 2px 顶条出现，绝不作为大色块或渐变背景（品牌点 `brand-dot` 的 blue→teal 渐变是唯一例外，且尺寸仅 8px）。

**The Token-on-Readout Rule.** 任何数字读数（指标值、状态栏 `elapsed`、计数动画、来源分数）必须 `font-variant-numeric: tabular-nums`，保证逐位对齐、像七段数码管一样克制。

## Typography

**Display Font:** Manrope（含 Noto Sans SC 回退）
**Body Font:** Manrope + Noto Sans SC（中文走 Noto Sans SC，英文/数字走 Manrope）
**Label/Mono Font:** JetBrains Mono（含 Cascadia Code / Consolas 回退）

**Character:** 标题用 Manrope 800 的紧字距大字，硬朗、工程感；正文与中文用 Noto Sans SC 保持清晰；所有「机器产出」文本（节点名、SQL、指标标签、状态、来源、架构图）统一 JetBrains Mono，形成「人话 vs 机读」的双层阅读节奏。

### Hierarchy
- **Display** (800, clamp(30px, 4.6vw, 52px), line-height 1.18, letter-spacing -1.2px)：Hero 主标题，仅首屏一处。
- **Title** (800, 28px, line-height 1.3, letter-spacing -0.5px)：各章节 `.section-title`，全站一致。
- **Body** (400, 16px, line-height 1.6)：正文基准；副文案 `.sub`(16.5px) / `.section-sub`(15px) 在此基础上微调。
- **Label** (Mono, 10.5px, letter-spacing 1px, 多数 uppercase)：机器/证据文本——`.m-label`、`.q-label`、`.k`、`.f-kind`、`.g-no`、状态栏；承载子系统类别与字段名。

### Named Rules
**The Mono-For-Evidence Rule.** 凡是源自系统/代码/评测的文本——节点名、SQL、指标标签、意图芯片、来源分数、状态栏、架构图——一律 JetBrains Mono；纯 UI 引导文案才用 Manrope/Noto Sans SC。

**The Seven-Segment Restraint Rule.** 数值读数尺寸克制（指标值 30px，非巨号），全部 `tabular-nums`，单位用 14px 弱化（`m-value .unit`）；不放大字号、不加彩色发光来制造「庞大」的错觉。

## Layout

容器 `.wrap` 最大宽 1180px、左右内边距 24px 居中；章节用 72px 上下竖向节奏（`section` 内边距），Hero 顶部 84px。`auto-fit minmax` 网格驱动所有卡片阵列：指标 `minmax(200px,1fr)`、问题帧 `minmax(260px,1fr)`、防护 `minmax(240px,1fr)`、入口 `minmax(250px,1fr)`，窄屏自然回流成单列。调试器窗内部为 `grid-template-columns: 3fr 2fr`（管线 3 : 检查面板 2），min-height 460px。间距节律以 8px 为基：卡片内边距 20px、网格 gap 14–16px、CTA gap 12px、章节下间距 26–34px。

响应式断点：≤900px 调试器改单列（管线去右边框、改底边框），服务状态次要文案隐藏；≤560px 顶栏导航隐藏、章节节奏收到 52px、Hero 收到 56px。窄屏（390px）无横向溢出——所有可滚区（`sql-box`、`.arch-box`、`.run-step code`）均 `overflow-x: auto`。

## Elevation & Depth

本系统默认扁平：深度靠三级中性表面（bg / surface / surface-2）的色调分层表达，而非阴影堆叠。唯一真实投影是调试器窗 `box-shadow: 0 24px 80px rgba(0,0,0,0.5)`，用于把「程序窗口」从页面抬起；其余卡片零阴影，hover 仅做背景/边框位移（`entry-card` 上升 2px、`button` 按下 1px）。

### Shadow Vocabulary
- **Debugger Lift** (`box-shadow: 0 24px 80px rgba(0, 0, 0, 0.5)`)：仅 `.debugger` 窗口使用，制造「被调试的程序」悬浮感。

### Named Rules
**The Flat-By-Tonal-Layer Rule.** 表面在静止态一律扁平；层级用 bg / surface / surface-2 三档色差区分，状态变化（hover / current / done）只改背景与边框，不改投影。阴影只服务于调试器窗这一个「窗口」隐喻。

## Shapes

圆角按组件尺度层级递进：2px（品牌点、RFM 色块、焦点环）、4px（徽章、tag、SQL 内框）、6px（导航项、RFM 芯片、运行步骤代码块）、7px（控制按钮）、8px（主按钮、速读框、节点、SQL 框）、10px（绝大多数卡片/架构块/指标卡/防护卡）、14px（调试器窗）。无全圆药丸形；除品牌点与色块为方角（2px）外，文本容器统一 ≥4px 的轻圆角。描边统一用 `--line` / `--line-strong` 的细发丝线，四层防护卡以顶部 2px 橙条点明语义。

## Components

### Buttons
- **Shape:** 轻圆角 8px（`button-primary` / `button-ghost`），控制按钮 7px（`ctrl-btn`）。
- **Primary:** 蓝底 `#3B82F6`、白字，内边距 11px 20px；hover 转深 `#2F6FE0`。
- **Ghost:** 透明底、主文字色、强发丝边框；hover 升到 `--surface-2` 底。
- **Hover / Focus:** 按钮 hover 0.15s 过渡背景；`:active` 下沉 1px；焦点环 `outline: 2px solid var(--blue); outline-offset: 2px`。
- **控件按钮（调试器）:** `ctrl-btn` 等宽字体、表面底、强发丝边框；`.primary` 变蓝底白字，hover `#2F6FE0`。

### Chips (意图 / 状态)
- **Style:** 等宽字体、4px 圆角；意图芯片蓝底 `rgba(59,130,246,0.12)` + 蓝字 + 蓝边 `rgba(59,130,246,0.3)`；pass 徽章绿底绿边、pending 徽章橙底橙边，均为 4px 圆角。
- **State:** 节点 tag 按分组换色（safety=橙、rag=紫、sql=青、route=蓝、sys=灰），底色为该色 0.1 透明。

### Cards / Containers
- **Corner Style:** 10px 圆角（调试器窗 14px）。
- **Background:** `--surface`，发丝边框 `--line`；防护卡多一条 2px 橙顶条。
- **Shadow Strategy:** 见 Elevation；仅调试器窗有投影。
- **Border:** 1px `--line`，调试器外框与当前节点用 `--line-strong`。
- **Internal Padding:** 卡片 20px，调试器内分栏 22px 20px，架构块 22px。

### Inputs / Fields
本页无表单输入控件；运行步骤的命令以 `<code>` 等宽块呈现（表面底、发丝边框、6px 圆角、可横向滚动）。

### Navigation
- **Style:** 顶栏 sticky、高 52px、不透明实底 `rgba(11,13,16,0.96)`、底部 1px 发丝线；导航项 12.5px、次级文字色、6px 圆角内边距 5px 10px。
- **State:** hover 转主文字色 + `--surface-2` 底；窄屏（≤560px）整组隐藏。

### Signature Component — Step-Through Debugger（单步调试器）
把 Agent 执行链渲染成可单步推进的程序窗口：标题栏（含三色灯 + 路径）、左管线（`pipe-question` + 10 个 `node`）、右检查面板（`inspect` 展示当前节点意图/SQL/来源/用量）、底部状态栏（request_id / thread_id / steps / elapsed）、控制条（单步 / 自动播放 / 重置）。节点态：`.done`（绿勾、灰名）、`.current`（surface-2 底 + 强边框 + 蓝序号 + 分组色 tag）。自动播放 900ms/步，计数与渐显经 IntersectionObserver 门控，`prefers-reduced-motion` 下直接停终态。

## Do's and Don'ts

### Do:
- **Do** 用五个语义色标注子系统：blue=路由/数据、purple=RAG、teal=SQL、orange=安全、green=完成/在线。
- **Do** 给所有数值读数加 `font-variant-numeric: tabular-nums`，并保持克制尺寸（指标值 30px，单位 14px 弱化）。
- **Do** 让所有「机器/证据」文本走 JetBrains Mono（节点名、SQL、指标标签、状态栏、来源分数、架构图）。
- **Do** 让每个指标/证据卡标注可复核来源（仓库路径、CI、评测快照）；无法核实的数字不出现。
- **Do** 保持顶栏为不透明实底 `rgba(11,13,16,0.96)`，无玻璃模糊。
- **Do** 把动效门控在 IntersectionObserver 之后，并对 `prefers-reduced-motion`、页面失焦、窄屏全部降级。

### Don't:
- **Don't** 用大色块或渐变背景铺陈五个语义色；它们只作芯片、tag、数值、状态点与 2px 顶条。
- **Don't** 在章节标题上方加 kicker / eyebrow 小标（finish-review 已移除）。
- **Don't** 用 unicode 字形项目符号（• 等）做列表；用 CSS `::before` 方点（hero-points 用 5px teal 方块）或真实元素。
- **Don't** 让标题回退到系统显示字体——保留 `Manrope, Noto Sans SC` 栈，缺失时走系统中文栈而非纯 serif/sans 兜底。
- **Don't** 给卡片加投影或玻璃模糊；深度只用 bg/surface/surface-2 三档色差，阴影只留给调试器窗。
- **Don't** 写未核实的宣传指标；失败项（端到端 14/15）要保留在证据中，不要粉饰为 100%。
