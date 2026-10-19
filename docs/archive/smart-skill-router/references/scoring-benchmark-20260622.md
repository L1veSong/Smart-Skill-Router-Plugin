# SSR 三维评分基准 · 设计与实测

> 2026-06-22 | 脚本: `~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py`

## 设计原则

1. **零硬编码** — 模型名从 `config.yaml` 读，embedding/gate 模型各自独立
2. **total 调真实 plugin** — `import` + `_match_a_layer()` + `_llm_screen()`，不复制逻辑
3. **动态 applicable** — 期望 skill 不存在的测试自动跳过，不扣分
4. **分类明细** — 按场景类型分组显示，用户只看常用类别
5. **50 条零隐私基准** — 30 信号 + 20 噪音，GitHub-safe

## 实测数据 (qwen3.5:4b + bge-large-zh-v1.5 + DeepSeek gate)

```
总评分:     72.8 (可用)   | 信号 23/28 82%  | LLM调用 28  | 延迟 177s
embedding:  45.5 (勉强)   | 信号 19/28 68%  | 噪音 1/20    | 延迟 4.7s
门控:       71.0 (可用)   | 噪声 18/20      | 信号 12/30   | 延迟 47s

分类: ✅ 调试 3/3  ✅ 金融 2/2  ✅ 旅行 2/2  ✅ 学术 2/2
      ✅ 部署 2/2  ✅ PPT 2/2  ✅ 地图 2/2  ✅ 微信 1/1
      ⚠️ 通用 5/8  ⚠️ 设计 2/4
噪音: 寒暄 5 | 反问 4 | 闲聊 4 | 极短 3 | 无意义 3
跳过(未安装): ASCII:['ascii-art'], 通用:['understand-explain']
```

total 模式跑完整 SSR 管线（噪音白名单 + DeepSeek 门控 + _match_a_layer + _llm_screen），噪音从1/20→19/20，信号82%。延迟高因30次API调用。

## 分数解读

- **总分低≠SSR 差** — 127s LLM 延迟拉低总分（30次 API 调用）
- **看分类不看总分** — 金融旅行满分，设计差无所谓
- **embedding 48** — bge-large-zh-v1.5 在中文场景的分，换 qwen3-embedding 会更高
- **gate 71** — qwen3.5:4b 噪音过滤 90%，信号识别偏保守（12/30 YES）

## 换模型对比流程

```bash
# 1. 拉新模型
ollama pull qwen3-embedding
# 2. 改 config
hermes config set ssr.embedding.model qwen3-embedding
# 3. 重建索引
rm ~/.hermes/plugins/ssr/embeddings.json && 重启 Hermes
# 4. 跑分对比
python3 ~/.hermes/plugins/ssr/tests/ssr_scoring_benchmark.py --mode embedding
```

## 已知局限

- **total 延迟高** — 30 次 LLM API 调用不可避免
- **分类权重固定** — 所有类别等权，不考虑用户使用频率
- **gate 模型依赖** — 换模型分数跟着变，分数 = 模型能力 × prompt 质量
- **50 条 ≠ 全覆盖** — 是基准不是真理，日常体验可能不同
