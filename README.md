# 🛒 电商订单数据分析项目

![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-BI看板-red?logo=streamlit)
![LangChain](https://img.shields.io/badge/LangChain-AI助手-green?logo=langchain)
![MySQL](https://img.shields.io/badge/MySQL-8.0-orange?logo=mysql)
![License](https://img.shields.io/badge/License-MIT-green)

## 🌐 在线演示

| 应用 | 链接 | 说明 |
|------|------|------|
| **BI 数据看板** | [点击体验](https://ecommerce-analysis-system-cqd8tpywoxneg8n3wqexfm.streamlit.app) | 交互式数据分析大屏 |
| **AI 分析助手** | 本地部署 `streamlit run ai-ecommerce-assistant/app.py` | 自然语言查数，自动 SQL + 图表 |

---

## 📌 项目简介

基于 **10万+ 条电商真实订单数据**，完成从数据清洗、特征工程到多维分析与可视化的完整链路。项目包含三大核心模块：

| 模块 | 技术栈 | 功能 |
|------|--------|------|
| **📊 BI 数据看板** | Streamlit + Plotly | 交互式数据大屏，多维度交叉筛选 |
| **🤖 AI 分析助手** | LangChain + Qwen + MySQL | 自然语言提问，自动生成 SQL 并绘图 |
| **📓 数据分析 Notebook** | Jupyter + Pandas | 数据清洗、销售/时间/用户多维分析 |

---

## 🤖 AI 电商分析助手（新增）

**告别手写 SQL**，直接用自然语言与数据对话：

```
用户：销售额最高的 3 个商品编号和金额
 AI：自动生成 SQL → 执行查询 → 数据表格 + 柱状图 → 导出 CSV
```

### 🎯 核心功能

| 功能 | 说明 |
|------|------|
| **Text-to-SQL** | 自然语言自动生成 SQL，无需手写查询 |
| **自动绘图** | 智能识别图表类型：折线图 / 柱状图 / 饼图 / 横向柱状图 |
| **智能重查询** | 检测"时间段最多"类问题，自动去除 LIMIT 重查完整24小时数据 |
| **数据解析** | SQL 失败时自动从 AI 回答中解析数据绘制图表 |
| **查询缓存** | 重复问题即时返回，减少 API 调用 |
| **敏感过滤** | 拦截手机号、身份证等隐私查询 |
| **异常预警** | 自动检测异常指标（如退款率异常）并给出业务建议 |
| **数据导出** | 支持 CSV 下载查询结果 |
| **流式进度** | 4步进度动画：连接数据库 → 分析中 → 生成SQL → 分析完成 |

### 🏗️ 技术架构

```
用户提问（自然语言）
    ↓
┌──────────────────────────────┐
│  LangChain SQL Agent         │
│  ├── 查看表结构 (schema)      │
│  ├── 生成 SQL (Qwen LLM)     │
│  └── 执行查询 (MySQL)         │
├──────────────────────────────┤
│  SQL 提取 + 数据解析          │
│  ├── intermediate_steps 提取  │
│  ├── output Markdown 提取     │
│  ├── ast.literal_eval 解析    │
│  └── 正则 fallback 解析       │
├──────────────────────────────┤
│  图表渲染 (Plotly)            │
│  ├── 时间序列 → 折线图        │
│  ├── 排名/TopN → 横向柱状图   │
│  ├── 占比/分布 → 饼图         │
│  └── 默认 → 柱状图            │
└──────────────────────────────┘
    ↓
流式输出：数据表格 + 图表 + SQL代码 + CSV导出
```

---

## 🛠️ 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 语言 | Python, SQL | Python 3.11, MySQL 8.0 |
| 数据处理 | pandas, numpy | pandas 2.0+ |
| 可视化 | matplotlib, plotly | 静态图 + 交互式图表 |
| BI 看板 | Streamlit | 交互式数据大屏 |
| AI 框架 | LangChain, LangChain-OpenAI | SQL Agent + LLM 调用 |
| 开发环境 | Jupyter Notebook, VS Code | 模块化 Notebook 开发 |
| 版本控制 | Git, GitHub | 规范 commit 信息 |

**AI 助手依赖**：
```
langchain>=0.1.0
langchain-community>=0.0.20
langchain-openai>=0.0.5
langchain-experimental>=0.0.50
streamlit>=1.28.0
pandas>=2.0.0
plotly>=5.15.0
python-dotenv>=1.0.0
pymysql>=1.1.0
sqlalchemy>=2.0.0
```

---

## 📊 数据分析内容

### 1. 数据清洗 (`01_data_cleaning.ipynb`)
- 读取原始数据，处理缺失值、异常值
- 生成清洗后数据集 `cleaned_orders.csv`
- 📌 **结论**：原始数据中仅 2.0% 为异常记录，清洗后 100,286 条数据可支撑后续多维分析

### 2. 销售额分析 (`02_sales_analysis.ipynb`)
- 总销售额统计、各平台销售额对比
- 📌 **结论**：移动端（APP+公众号）贡献超九成销售额

### 3. 时间维度分析 (`03_time_analysis.ipynb`)
- 每日销售趋势、每小时订单分布、星期几订单分布
- 📌 **结论**：销售额集中在特定时段和周末

### 4. 商品与用户分析 (`04_product_user_analysis.ipynb`)
- 商品销售额 TOP10、用户消费 TOP10
- 📌 **结论**：TOP10 商品贡献 35% 销售额，验证"二八定律"

### 5. 可视化看板 (`05_visualization.ipynb`)
- 输出 6 张业务图表，整合为四合一管理看板

### 6. SQL 高级分析 (`sql/`)
- **留存分析**：次日/7日/30日留存率
- **RFM 用户分层**：重要价值/发展/保持/流失/一般用户
- 📌 **结论**：22.98% 用户已进入流失状态

### 7. 交互式 BI 看板 (`app/bi_dashboard.py`)
- 核心指标卡：总销售额、订单数、活跃用户、客单价、复购率、退款率
- 每日销售趋势、平台销售占比、24小时下单分布
- RFM 用户分层、商品/用户 TOP10
- 交互筛选：平台多选、日期范围选择

### 8. AI 智能分析助手 (`ai-ecommerce-assistant/app.py`)
- Text-to-SQL 自然语言查数
- 自动 SQL 生成 + 图表渲染 + CSV 导出
- 智能重查询、异常预警、敏感过滤

---

## 📊 关键指标速览

| 指标 | 数值 | 说明 |
|------|------|------|
| 原始数据量 | 102,318 条 | 电商订单记录 |
| 清洗后数据 | 100,286 条 | 删除 2,032 条异常数据 |
| 分析用户数 | 78,060 名 | 去重后独立用户 |
| 时间跨度 | 2025.01-2026.01 | 全年销售数据 |
| 产出图表 | 6 张 | 4 张独立图 + 1 张总览 + 1 张 RFM |
| BI 看板 | 1 个 | Streamlit 交互式大屏 |
| AI 助手 | 1 个 | LangChain Text-to-SQL |
| SQL 脚本 | 3 个模块 | 建表/导入/高级分析 |

---

## 📁 项目结构

```
ecommerce_analysis/
├── ai-ecommerce-assistant/          # AI 自然语言分析助手
│   ├── app.py                       # Streamlit 主程序
│   ├── .env                         # API Key + 数据库配置
│   └── requirements.txt             # Python 依赖
├── app/
│   └── bi_dashboard.py              # Streamlit BI 看板
├── data/
│   └── cleaned_orders.csv           # 清洗后数据 (100,286 条)
├── notebook/
│   ├── 01_data_cleaning.ipynb       # 数据清洗
│   ├── 02_sales_analysis.ipynb      # 销售额分析
│   ├── 03_time_analysis.ipynb       # 时间维度分析
│   ├── 04_product_user_analysis.ipynb # 商品用户分析
│   └── 05_visualization.ipynb       # 可视化看板
├── sql/
│   ├── 01_create_table.sql          # 建库建表语句
│   ├── 02_import_data.sql           # CSV 数据导入
│   └── 03_analysis.sql              # 留存分析 + RFM 分层
├── output/                          # 可视化输出文件
│   ├── 05_01_商品销售额TOP10.png
│   ├── 05_02_平台销售额占比.png
│   ├── 05_03_每日销售趋势.png
│   ├── 05_04_用户消费TOP10.png
│   ├── 05_核心业务分析图_四合一.png
│   └── rfm_user_segmentation.png
├── .gitignore
├── README.md
└── requirements.txt
```

---

## 📈 可视化成果

| 商品销售额 TOP10 | 平台销售占比 |
|:---------------:|:-----------:|
| ![商品销售额TOP10](output/05_01_商品销售额TOP10.png) | ![平台占比](output/05_02_平台销售额占比.png) |

| 每日销售趋势 | 用户消费 TOP10 |
|:-----------:|:-------------:|
| ![日销趋势](output/05_03_每日销售趋势.png) | ![用户消费](output/05_04_用户消费TOP10.png) |

### 业务看板总览

![四合一总览](output/05_核心业务分析图_四合一.png)

### RFM 用户分层

![RFM用户分层](output/rfm_user_segmentation.png)

---

## 💰 业务价值量化

| 分析维度 | 发现结论 | 可落地动作 | 预期业务收益 |
|----------|----------|------------|--------------|
| 渠道效率 | APP+公众号占 91.6% | 收缩 Web 端投放预算 | 营销 ROI 提升 15%+ |
| 商品结构 | TOP10 贡献 35% 销售额 | 建立爆款安全库存机制 | 缺货率降低 20% |
| 用户分层 | 0.46% 头部用户客单价 3 倍于均值 | VIP 专属客服 + 优先发货 | 高价值用户留存率提升 10% |
| 时间规律 | 13:00/20:00 为下单高峰 | 推送/客服排班向高峰倾斜 | 转化率提升 8%~12% |

---

## 🎯 核心业务洞察

### 1️⃣ 头部商品效应显著
- TOP10 商品单款销售额均超 **30 万元**，最高达 **48 万元**
- 前 10 商品贡献了约 **35%** 的总销售额（二八定律明显）
- 💡 建议：建立爆款库存预警机制，对 TOP10 商品设置安全库存阈值

### 2️⃣ 渠道双极化格局
| 渠道 | 销售额占比 | 订单量占比 | 客单价 |
|------|-----------|-----------|--------|
| APP | 45.3% | 44.1% | 1,320元 |
| 微信公众号 | 46.3% | 47.2% | 1,285元 |
| Web网站 | 6.6% | 7.1% | 1,190元 |
| 其他 | 1.9% | 1.6% | 1,450元 |

- 📌 移动端（APP+公众号）贡献 **91.6%** 销售额

### 3️⃣ RFM 用户分层（78,060 名用户）
| 用户分层 | 人数 | 占比 | 平均消费 | 运营策略 |
|---------|------|------|---------|---------|
| 重要价值用户 | 356 | 0.46% | 4,584元 | VIP专属服务 |
| 重要发展用户 | 2,191 | 2.81% | 733元 | 凑单推荐提客单 |
| 重要保持用户 | 25 | 0.03% | 4,142元 | 大额券定向召回 |
| 流失用户 | 17,941 | 22.98% | 486元 | 低成本短信激活 |
| 一般用户 | 57,547 | 73.72% | 1,559元 | 首单复购券引导 |

---

## 🚀 运行方式

### 方式一：在线体验
直接访问 [BI 数据看板](https://ecommerce-analysis-system-cqd8tpywoxneg8n3wqexfm.streamlit.app)，无需本地部署。

### 方式二：本地运行

```bash
# 1. 克隆项目
git clone https://github.com/2681107509-dev/ecommerce-analysis-system.git
cd ecommerce_analysis

# 2. 创建虚拟环境
python -m venv .venv
.venv\Scripts\activate     # Windows
# source .venv/bin/activate  # Mac/Linux

# 3. 安装依赖
pip install -r requirements.txt
pip install -r ai-ecommerce-assistant/requirements.txt  # AI 助手依赖

# 4. 启动 BI 看板
streamlit run app/bi_dashboard.py

# 5. 启动 AI 分析助手（需配置 MySQL）
# 配置 ai-ecommerce-assistant/.env 文件
streamlit run ai-ecommerce-assistant/app.py

# 6. 运行 Jupyter Notebook（可选）
jupyter notebook
```

### AI 助手配置（`.env` 文件）

在 `ai-ecommerce-assistant/` 目录下创建 `.env`：

```env
# LLM 配置
LLM_API_KEY=your_api_key_here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=qwen-plus

# MySQL 配置
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=ecommerce_analysis
```

### MySQL 数据初始化

```bash
# 1. 执行建库建表
mysql -u root -p < sql/01_create_table.sql

# 2. 导入数据
# 修改 sql/02_import_data.sql 中的 CSV 路径后执行
mysql -u root -p < sql/02_import_data.sql
```

---

## 📝 依赖清单

**基础依赖**：
```
pandas>=2.0.0
numpy>=1.24.0
matplotlib>=3.7.0
plotly>=5.15.0
streamlit>=1.28.0
jupyter>=1.0.0
openpyxl>=3.1.0
pymysql>=1.1.0
```

**AI 助手扩展**：
```
langchain>=0.1.0
langchain-community>=0.0.20
langchain-openai>=0.0.5
langchain-experimental>=0.0.50
sqlalchemy>=2.0.0
python-dotenv>=1.0.0
```

---

## 🗺️ 迭代规划

- ✅ **已完成**：数据清洗 → 多维分析 → SQL 留存/RFM → BI 看板
- ✅ **已完成**：AI 自然语言查数助手（Text-to-SQL + 自动图表）
- 🔄 **进行中**：接入 FastAPI 数据接口，支持外部系统实时调用
- 📋 **规划中**：接入 Airflow 定时调度，实现日/周/月自动化数据报告推送
