# 路由方案 A/B 评测报告

> 生成时间：2026-09-04 15:32:57  
> 路由器 A：确定性规则路由 `agent_core.routing.classify_intent`（生产在用）  
> 路由器 B：LLM 路由 `agent_core.llm_router.classify_intent_llm`（对照方案）  
> LLM 侧状态：**未运行（未配置 LLM_API_KEY，未伪造数据）**

## 方法论

两套路由器共享同一 5 类意图标签（`data / knowledge / hybrid / clarification / blocked`），在相同用例集上对比 **准确率 / macro-F1 / 单条延迟 / 成本**。规则侧为生产代码、结果真实；LLM 侧仅在配置密钥后运行，否则明确标注跳过，绝不编造数字。

## 数据集

| 数据集 | 规模 | 说明 |
|--------|------|------|
| curated | 100 | 贴合规则标记词的规范表述（与规则标记同期构造，存在表述偏好） |
| robustness | 25 | 口语化改写 / 同义替换 / 隐私与注入的变体表述，用于检验规则泛化性 |

## 路由器 A（规则）结果

| 数据集 | 样本 | 准确率 | macro-F1 | 单条延迟(ms) | 成本(¥) |
|--------|------|--------|----------|---------------|---------|
| curated | 100 | 100.0% | 100.0% | 0.007 | 0.0000 |
| robustness | 25 | 24.0% | 16.9% | 0.003 | 0.0000 |

## 路由器 B（LLM）结果

**未运行。** 本环境未配置 `LLM_API_KEY`，故不生成 LLM 侧数字（避免伪造）。

在具备密钥的环境中运行以下命令即可补齐 B 侧：

```bash
LLM_API_KEY=xxx LLM_BASE_URL=https://api.deepseek.com LLM_MODEL=deepseek-chat \
  python agent_core/eval/ab_routing_eval.py
```

可选环境变量：`LLM_PRICE_IN_PER_1K` / `LLM_PRICE_OUT_PER_1K`（默认 0.001 / 0.002 元每 1K token）用于成本估算。

## 关键发现

1. **规则路由在 curated 集上达到 100.0% 准确率、0.007 ms/条、成本 ¥0**——确定性、零成本、可解释，契合 v2 对'封闭意图分类法 + 零额外延迟'的诉求。

2. **规则路由在 robustness 集上骤降至 24.0%**——对同义替换（'咋算' vs '怎么算'）、隐私变体（'电话' vs '手机号'）、注入改写（'忽略上面的要求' vs '忽略之前指令'）缺乏泛化，存在真实误路由与安全风险。

3. **LLM 路由的对照价值在此显现**：对自然语言的泛化正是 LLM 的强项，预期在 robustness 集上明显优于规则。是否切换取决于生产流量中'改写/变体'占比——若日志显示误路由率超过阈值，即可用本仓库已实现的 `llm_router` 与混合策略补齐。

4. 结论：v2 选规则路由是'在已观测流量分布下的最优解'，而非'只会规则路由'；本 A/B 框架使该决策可被数据复盘与迭代。

## 复现命令

```bash
python agent_core/eval/ab_routing_eval.py            # 规则侧
LLM_API_KEY=xxx python agent_core/eval/ab_routing_eval.py  # 含 LLM 侧
```
