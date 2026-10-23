# SSR 精准匹配 — 调研发现

## 2026-06-10 01:30：Dashboard 全面美化 + v0.6.1 发包验证

### 美化设计决策
- 方向：Ethereal Glass（暗色玻璃）× Industrial Data Density（数据密度）
- 4 skill 驱动：redesign-existing-projects(审计) + high-end-visual-design(视觉token) + popular-web-designs(Linear数据表) + frontend-design(定调)
- 关键取舍：弃 Inter → Geist · 弃靛紫 → Emerald · 弃 emoji → SVG · 弃纯平黑 → 径向微光
- tasty / gpt-taste / minimalist-ui / claude-design 加载但未使用或冲突

### v0.6.1 验证数据

| 项目 | 结果 |
|------|:--:|
| API /api/rules | 100 rules ✅ |
| API /api/stats | healthy · rules=6 · emb=370 · hits=14232 ✅ |
| API /api/config | provider=main · timeout=30 ✅ |
| JS console errors | 0 ✅ |
| 中文 i18n | 35 data-lang 全中文 ✅ |
| 英文 i18n | 全英文 ✅ |
| 亮色主题 | bg=#f4f4f5 ✅ |
| 玻璃特效 | backdrop-filter blur(8~20px) ✅ |
| Geist 字体 | Geist + Geist Mono ✅ |

### 四文件同步
- ✅ CHANGELOG.md: v0.1.0 → v0.6.1 全量补全
- ✅ README.md: version badge 0.6.1 + 架构图更新 + Dashboard 说明
- ✅ SKILL.md: v0.6.1 状态更新 + Dashboard 美化标注
- ✅ progress.md: Phase 3-6 标记完成 + 美化进度

## 2026-06-10 00:06：重启验证 + 4 task 全量测试

### 测试数据

| Task | 测试项 | 结果 |
|------|-------|:--:|
| 3.1 | `_get_skill_info("canon-mnemonic-guard")` → 301 chars, 无表格 | ✅ |
| 3.1 | `_get_skill_info("road-trip-planner")` → 620 chars | ✅ |
| 3.2 | `_expand_chinese_query()` 14/14 域命中 | ✅ |
| 3.2 | 无匹配查询（「今天天气」）不扩展 | ✅ |
| 4.2 | `_SESSION_STATS` 5字段完整 | ✅ |
| 4.2 | `_STATS_LOG_INTERVAL = 10`；模拟10次触发 `calls % 10 == 0` | ✅ |
| 4.1 | Dashboard `/api/stats` 4字段 (intercept=11, errors=90, sessions=0, last_solidify=None) | ✅ |
| 4.1 | `curl localhost:8765` HTTP 200 | ✅ |

### 运行时验证
- embedding 全量重建：296 skill（00:00:00→00:00:46）
- SSR A+B 累计命中：14212 条
- Dashboard 双端存活：8765 (CMG) + 8766 (SSR)

### 备份
`~/.hermes/backups/ssr-v020-20260610_000640/` — 3 文件 + MANIFEST

## 2026-06-09 23:55：GREEN v2 + 回归测试套件（已完成代码）

### 回归测试套件 v1.0

`test_ssr.py` — 8 大类 34 项测试，全量通过。

| 类别 | 项数 | 内容 |
|------|:--:|------|
| 1. 文件完整性 | 7 | __init__.py/a_rules.json/embeddings.json 存在+关键函数 |
| 2. 规则有效性 | 3 | JSON 解析/正则有效/skills 字段+A层↔embedding 交叉验证 |
| 3. Embedding 索引 | 2 | JSON 解析/1024 维度一致性 |
| 4. 配置验证 | 5 | ssr:节/floor/conf 值匹配 |
| 5. GREEN 关键词 | 6 | 5 场景 + 覆盖率统计 |
| 6. GREEN Embedding | 6 | 5 场景 (含 2 个已知弱项) + 覆盖率 |
| 7. 阈值过滤 | 3 | 噪音 floor 过滤/噪音基线/强意图通过 |
| 8. Dashboard | 1 | HTTP 200 |

用法：`python3 test_ssr.py` (全量) / `--quick` (跳过 embedding)

### 测试中修复的代码问题

- `_get_skill_info()` 不支持 YAML block scalar (`description: |` → 空值)
- 3 个 skill (idea-foundry/tushare-finance/technical-analysis) 因此未入 embedding 索引
- 修复：增加 YAML block scalar 解析 + 正文首段 fallback（需重启生效）

### GREEN v2 验证 (similarity_floor=0.35, confidence_threshold=0.40)

5/5 全通过。**每个场景的命中源都是关键词规则，不是 embedding。**

| 场景 | 关键词命中 | Embedding top-1 | 关键词兜底？ |
|------|-----------|----------------|:--:|
| UI设计 | brainstorming/ui-ux/popular-web | claude-design(0.58) | ✅ |
| 代码调试 | diagnose/sys-debug | tui-commands(0.58) | ✅ |
| ASCII | ascii-art | ascii-art(0.52) | 🟢 embedding 也对了 |
| 学术写作 | r-p-w/paper-spine/survey | writing-plans(0.56) | ✅ |
| 金融分析 | tech-analysis/tushare | **baoyu-illustrator(0.45)** | ✅ 关键词救场 |

金融场景 embedding 完全误匹配：`baoyu-article-illustrator` sim=0.45 排在 `technical-analysis` 前面。
如果没有关键词规则 `分析.*(股票|走势|均线|K线)`，用户说"分析均线"就推荐插画工具了。

### 结论
- 双阈值收紧（0.25→0.35/0.40）不是负优化——关键词路径置信度恒为 1.0，不受影响
- Embedding 对中文领域术语（均线、导航栏）仍然弱，但关键词规则兜底
- 当前 SSR 架构：关键词是骨架（覆盖常见场景），embedding 是肌肉（覆盖长尾场景）

## 2026-06-09 23:06：bge-m3 Embedding 主导噪声

### 关键发现：29 条推荐全来自 embedding，非关键词

消息 "分析现有情况，怎么解决？"：
- 关键词匹配：**0 条规则命中**
- bge-m3 embedding：**30 条全量输出**（相似度 0.528-0.628，跨度仅 0.1）

**结论：** 关键词规则没有问题——当用户消息不命中任何关键词规则时，embedding 兜底路径吐出了 30 条低区分度的结果。bge-m3 对这种"元分析/反思"类消息的语义区分能力极弱。

### 30 条 embedding 相似度分布

| 排名 | Skill | 相似度 | 是否相关 |
|:--:|------|------|:--:|
| 1 | systematic-debugging | 0.628 | 🟡 勉强 |
| 2 | handoff | 0.578 | 🔴 不相关 |
| 3 | to-prd | 0.573 | 🔴 不相关 |
| 8 | writing-plans | 0.556 | 🟢 相关 |
| 11 | paper-spine-research | 0.552 | 🟡 勉强 |
| 15 | diagnose | 0.549 | 🟡 勉强 |
| 30 | writing-skills | 0.528 | 🟡 勉强 |

**特征：**
1. Top-1 最高仅 0.628——bge-m3 对这个查询没有强信号
2. 0.528-0.628 跨度仅 0.1——区分度极低，头尾几乎一样
3. Phase 全部为空——embeddings.json 未存储 phase 信息

### 解决方案评估

| 方案 | 原理 | 预期效果 |
|------|------|---------|
| P0 截断(已实现) | max_total=12 | 30→12，保 top |
| A. 相似度地板 | <0.55 丢弃 | 砍掉尾部噪声(~15条) |
| B. 最小置信度 | top-1<0.65 整批丢弃 | 防整批低质量输出 |
| A+B 组合 | 地板+置信度 | 低质量查询不回退到 embedding |

---

## 2026-06-09 22:50：bge-m3 精度 ~60%

4 条零命中消息测试，精度 2.5/4。根因：skill description 过短。

## 2026-06-09：Phase 2 可行性验证

nomic-embed-text→bge-m3 切换，246 skill 索引构建。

## 2026-06-05：市场调研

GitHub #4589 确认痛点，现有方案全不适用→自建 SSR。
