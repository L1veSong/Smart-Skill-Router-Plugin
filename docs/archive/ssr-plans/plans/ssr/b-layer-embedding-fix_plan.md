# SSR B层+Embedding 修复计划

**创建时间**: 2026-06-21
**状态**: ✅ 已完成

## 问题

信号命中率 40%（4/10），噪音静默率 100%（5/5）。

根因：B 层从未产出匹配——`B 层判断: 不需要 skill`。

## 根因分析

两个问题叠加导致信号漏推：

| # | 位置 | 问题 | 影响 |
|---|------|------|------|
| 1 | line 626 | `if keyword_result and _EMBEDDING_INDEX` — embedding 被 A 层关键词锁死，关键词没命中就不跑 | A 层空时 embedding 零贡献 |
| 2 | line 1345 | B 层 prompt `"先判断是否需要工具。不需要→NO"` — 二元门控过于保守 | DeepSeek 对大部分消息回 NO |

两个问题独立存在，叠加后：A 层关键词缺口 → embedding 不跑 → B 层说 NO → 三层全失效。

## 方案：两处改动，零硬编码

### 改动 1: 放开 embedding 触发条件

**文件**: `~/.hermes/plugins/ssr/__init__.py`  
**位置**: line 626  

```python
# 旧：embedding 只在关键词命中时激活
if keyword_result and _EMBEDDING_INDEX:

# 新：embedding 永远跑
if _EMBEDDING_INDEX:
```

**为什么不需要噪声门禁**：

噪声消息在 bge-large-zh-v1.5 1024 维空间里与所有 skill 的余弦相似度自然低于阈值——不是规则过滤，是向量空间自带属性。

```
"嗯嗯"        → embedding → 所有 cos_sim < 0.15   → `_similarity_floor()` 自然拦截
"谢谢你的帮助" → embedding → 所有 cos_sim < 0.20   → 自然拦截
"写ppt"       → embedding → pptx cos_sim 0.55+     → 命中
"部署到Vercel" → embedding → deploy-to-vercel 0.60+ → 命中
```

`_similarity_floor()` 是已有的动态阈值，低于它自动跳过。

### 改动 2: B 层 prompt 去二元门控

**文件**: `~/.hermes/plugins/ssr/__init__.py`  
**位置**: line 1345  

```python
# 旧
{"role": "system", "content": f"先判断用户消息是否需要工具。不需要→只回答NO。需要→回答YES并列出最多3个最匹配的技能名。可用技能：\n{skill_list}"}

# 新  
{"role": "system", "content": f"列出与此消息最相关的至多3个技能名（JSON格式：{{\"skills\":[\"name1\",\"name2\"],\"phases\":[\"BUILD\",\"DISCOVER\"]}}）。如确实无关，返回{{\"skills\":[]}}。可用技能：\n{skill_list}"}
```

同时改 line 1359 的 NO 判定：
```python
# 旧
if content.strip().upper().startswith("NO"):
    logger.info("[ssr] B 层判断: 不需要 skill")
    return None

# 新：空 skills 列表 = 无匹配
parsed = json.loads(content)  # 移到此处
if not parsed.get("skills"):
    logger.info("[ssr] B 层判断: 无相关技能")
    return None
```

## 不改的地方

- A 层关键词 — 让 B→A 自学习去填
- 冷却制/缓存/会话统计 — 与本次修复无关
- 相似度门槛 `_similarity_floor()` — 已有，生效中
- B→A 升级 `_promote_to_a()` — 已完备，等 B 层喂数据

## 预期效果

```
改动后：
  新用户 → A 层 miss → embedding 语义匹配 → 命中 → 推荐
              └→ embedding 也 miss → B 层兜底 → 命中 → 推荐
                                            └→ B 层返回空 → 静默

B→A 自学习闭环：
  B 层命中 → 连续 3 次相同 → _promote_to_a() → A 层永久记住
```

信号命中率预期：40% → 80%+  
噪音静默率预期：保持 100%（embedding 相似度天然低）

## 执行步骤

1. `cp ~/.hermes/plugins/ssr/__init__.py ~/.hermes/plugins/ssr/__init__.py.bak.$(date +%m%d%H%M)`
2. `patch` 改动 1（line 626）
3. `patch` 改动 2（line 1345 + 1359）
4. `python3 -c "compile(open('$HOME/.hermes/plugins/ssr/__init__.py').read(), '__init__.py', 'exec')"` 验证语法
5. 重启 Hermes（完全退出再启动，非 /new）
6. 重新跑 10 信号 + 5 噪音测试验证
