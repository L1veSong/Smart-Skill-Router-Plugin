# SSR GREEN 验证 v2 — 新阈值 (2026-06-09)

> similarity_floor: 0.35 | confidence_threshold: 0.40 | auto-gen: off
> A层: 100手动规则 | Embedding: Ollama bge-m3 1024维 | 索引: 246 skill

## 原始结果: 3/5 🟡

| # | 场景 | 期望 | Top-1 embedding | 命中率 | 置信度 | |
|---|------|------|-----------------|--------|--------|:--:|
| 1 | UI设计 | brainstorming, ui-ux-pro-max, popular-web-designs | claude-design (0.58) | 33% | 0.56 | ❌ |
| 2 | 代码调试 | diagnose, systematic-debugging | debugging-hermes-tui (0.58) | 50% | 0.55 | ✅ |
| 3 | ASCII艺术 | ascii-art | **ascii-art (0.52)** | 100% | 0.50 | ✅ |
| 4 | 学术写作 | research-paper-writing, paper-spine-research | writing-plans (0.56) | 50% | 0.55 | ✅ |
| 5 | 金融分析 | technical-analysis, tushare-finance | baoyu-article-illustrator (0.45) | **0%** | 0.43 | ❌ |

通过: 3/5 | 及格线≥3 ✓ | 目标线≥4 ✗

---

# SSR GREEN 验证 v3 — 脚本 Bug 修复后 (2026-06-14)

> a_rules.json: 100→61条（降噪后）| Embedding: 370 skill
> **修复**: benchmark 脚本关键词匹配逻辑（`patterns`→regex key + str/dict 兼容）

## 修正结果: 4/5 🟢

| # | 场景 | 期望 | 关键词命中 | Embedding top-1 | 命中率 | 置信度 | |
|---|------|------|-----------|-----------------|--------|--------|:--:|
| 1 | UI设计 | brainstorming, ui-ux-pro-max, popular-web-designs | ❌ 无 | vibrant (0.56) | 33% | 0.55 | ❌ |
| 2 | 代码调试 | diagnose, systematic-debugging | ✅ 全部命中 | hermes-config-yaml-fix (0.54) | 100% | 0.53 | ✅ |
| 3 | ASCII艺术 | ascii-art | ✅ ascii-art | paper-spine-humanize (0.42) | 100% | 0.41 | ✅ |
| 4 | 学术写作 | research-paper-writing, paper-spine-research | ⚠️ writing-skills | llm-wiki (0.50) | 50% | 0.50 | ✅ |
| 5 | 金融分析 | technical-analysis, tushare-finance | ✅ 全部命中 | technical-analysis (0.47) | 100% | 0.42 | ✅ |

通过: 4/5 | 及格线≥3 ✓ | 目标线≥4 ✓

## 脚本 Bug 修复（2 处）

**Bug 1: 关键词匹配找错字段**
```python
# ❌ 旧 — 找不存在的 patterns 字段
for p in rule_data.get("patterns", []):
    if p.lower() in msg.lower():
        kw_hits.add(rule_name)

# ✅ 新 — a_rules 的 key 本身就是 regex 模式
for rule_key, rule_data in a_rules.items():
    if re.search(rule_key, msg, re.IGNORECASE):
        for s in rule_data.get("skills", []):
            name = s["name"] if isinstance(s, dict) else s
            kw_hits.add(name)
```

**Bug 2: skills 格式不兼容**
- 人工规则: `skills: [{"name": "xxx", "phase": "BUILD"}]` — dict
- 自动生成: `skills: ["skill-name"]` — str
- 硬编码 `s["name"]` 在 str 格式上 TypeError

## 与 GREEN v1/v2 对比

| 指标 | v1 (floor=0.25) | v2 (floor=0.35) | v3 (修复后, 0.35) |
|------|-----------------|-----------------|-------------------|
| 结果 | 5/5 | 3/5 | **4/5** |
| 代码调试 | diagnose A层命中 | embedding 50% | **关键词 100%** ✅ |
| ASCII艺术 | ascii-art A层命中 | embedding 100% | **关键词 100%** ✅ |
| 金融分析 | technical-analysis A层命中 | 0% embedding完全漏 | **关键词 100%** ✅ |
| UI设计 | brainstorming A层命中 | 33% | 33% (同v2) |
| 学术写作 | research-paper-writing A层命中 | 50% | 50% (同v2) |

## 唯一缺口: UI设计

降噪后 a_rules.json 只剩 `设计.*系统` 规则，缺少 UI/界面/前端关键词。
需补: `UI|界面|设计.*(导航|页面|网页|布局|组件)` → ui-ux-pro-max + popular-web-designs

## 关键发现

- **A层关键词是中文场景的命脉** — bge-m3 在金融/调试/ASCII 领域无法通过 embedding 召回期望 skill
- **降噪有代价** — 100→61 去掉了 paper-spine/huashu-nuwa/design-taste 等噪声，但也丢了 UI 设计关键词
- **benchmark 脚本必须与实际数据结构同步** — 人工规则和自动生成规则的字段格式不同
