# SSR v2.4.0-MoE — MoE 架构升级计划

> 执行: 2026-07-23 | 状态: ✅ 代码完成，待重启验证

## 背景

v2.3.0 A 层扁平全量扫描：26 条正则规则每轮全跑，跨域互相污染。"新疆旅行拍照片"同时命中旅行×3 + 生图×2 = 5 条噪音。

## MoE 架构

仿 Mixture of Experts 门控路由：

```
用户输入 → 路由层（词干检测→激活域） → 域内匹配（仅扫激活域规则） → skills 直推
```

三层改动（集中在 `_match_a_layer_keyword` 一个函数）：

1. **路由层** `_route_domains()`: 6 域 × 词干表，出现即激活；无命中则全开 fallback
2. **域过滤**: 规则含 `domain` 字段时仅激活域内才扫描
3. **skills 直推**: 规则有 `skills` 字段直接返回，不再搜 `_SKILL_INDEX`；无 `skills` 时走旧 `keywords` 路径向后兼容

## 改动清单

| 文件 | 改动 | 
|---|---|
| `__init__.py` | +DOMAIN_STEMS 常量(6域) + `_route_domains()` + `_match_a_layer_keyword` 域过滤+skills直推 |
| `a_rules.json` | 26条规则全加 `domain` 字段 + skill名修正为全路径格式 |

## 域分布

| 域 | 词干 | 规则数 | 覆盖 skill |
|---|---|---|---|
| travel | 玩/游/机票/酒店/吃/天气/自驾/导航... | 8 | travel-plan-request, road-trip-planner, travel-data-search, travel-api, travel-food-guide, find-nearby, maps, trip-website-generator, travel-itinerary-html |
| visual | 电影感/分镜/角色/海报/中国风/徕卡... | 8 | zy-cinematic-realism, cinema-dna-21x9x3, fantasy-life-force-portrait, culture-fragment-poster-engine, fantasy-oriental-editorial-poster, regional-culture-poster, fantasy-photography-simulation |
| writing | 写/文章/论文/润色/文笔... | 4 | khazix-writer, nature-writing, nature-polishing, writing-guidelines |
| storage | 磁盘/清理/洁癖/收尾... | 2 | storage-analyzer, neat-freak |
| map | 画地图/可视化/svg/geo | 1 | svg-geo-map, geographic-visualization |
| shortdrama | 短剧/墨刑/故事板 | (内联在visual中) | 短剧三件套 |
| 通用 | 无域标记 | 3 | arxiv, diagnose, technical-analysis |

## 验证

重启后测试：
```
"想去新疆玩几天拍照片" → 路由: travel+visual → 行程规划+photography (2条，非5条)
"写文章" → 路由: writing → khazix-writer (1条)
"清理磁盘" → 路由: storage → storage-analyzer (1条)
```

## 回滚

```bash
cd ~/.hermes/plugins/ssr
cp __init__.py.bak.0723_moe __init__.py
# 重启 Hermes
```

---

## 附录：A 层规则生成方案选型

> 决策日期: 2026-07-23 | 状态: 暂定方案①

| # | 方案 | 准确度 | 维护成本 | 自动程度 | 
|---|---|---|---|---|
| ① regex 手动 | 当前 | 🟢 最高（人工审核） | 🔴 每次手写 | 0% |
| ② auto_gen 从 SKILL.md 提取 | SSR 已有 | 🟡 依赖作者描述质量 | 🟢 自动 | 100% |
| ③ embedding 语义匹配 | SSR 已有 | 🟡 依赖 embedding 模型 | 🟢 零维护 | 100% |

- ② 根病：用英文 description 匹配中文意图，上限低，曾产 6789 条垃圾
- ③ 终局方案：装新 skill 自动入 embedding 索引，零配置。但当前硅基流动 embedding 不稳定
- **决定：暂手动。等硅基流动 embedding 稳定后切换到③**。届时正则规则退化为缓存加速（embedding 命中 3 次 → 自动写 A 层规则）
