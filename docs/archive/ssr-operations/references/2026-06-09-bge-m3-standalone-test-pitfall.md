# 2026-06-09 bge-m3 独立脚本测试误报

## 背景

用户将 SSR embedding 模型从 nomic-embed-text (768维) 切换到 bge-m3 (1024维)，要求测试 SSR。

## 测试过程

1. **存活验证** ✅ — agent.log 显示 `插件注册完成 | emb: 246 | B层: main`
2. **Embedding 直调** ✅ — `curl Ollama API` 返回 bge-m3 1024维
3. **独立 Python 基准测试** ❌ — 0/5 通过，结果随机
   - "设计响应式导航栏" → 命中 ssr-operations, webhook-subscriptions（而非 ui-ux-pro-max）
   - "茅台均线" → 命中 songwriting-and-ai-music（而非 technical-analysis）
4. **根因定位** — `_embed()` 返回 768维，而索引是 1024维。`_load_ssr_config()` 因 hermes_cli 不可导入而降级为空 dict，embedding model 默认 nomic-embed-text (768维)

## 根因链

```
独立 Python 脚本
  → import hermes_cli 失败
    → _load_ssr_config() 返回 {}
      → _embed_model() 默认 "nomic-embed-text" (768维)
        → _embed() 调 Ollama 拿 768维向量
          → 索引是 bge-m3 1024维
            → 余弦相似度跨维度无意义
              → 匹配随机 ❌
```

## 正确测试方式

在 Hermes 会话中发测试消息：
- "帮我设计一个响应式导航栏"
- "这段 Python 代码报 KeyError 帮我看看"
- "生成一个 ASCII 猫咪图"
- "帮我写论文的 Related Work 部分"
- "分析贵州茅台的均线走势"

每条后 `grep 'ssr' agent.log | tail -3` 验证命中。

## 其他发现

- **49 个 skill 不在索引中**（含 technical-analysis），原因是 description < 5 字符被 `_build_embedding_index` line 616-617 过滤
- **keyword 规则被绕过**：`_match_a_layer` 在 embedding 索引可用时完全跳过关键词规则
- **a_rules.json 有 2110 条规则**，但 cleanup 淘汰到 100 条（max_rules），后重建到 2110
