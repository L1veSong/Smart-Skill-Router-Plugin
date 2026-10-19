# SSR 6-rule GREEN Baseline（2026-06-14 降噪后验证）

> 验证时 SSR 版本：v0.6.2 | 规则数：6 全手动 | auto-gen：关闭 | B层：main (DeepSeek) | embedding：bge-m3 1024维 370 skill

## 配置

```yaml
ssr:
  auto_gen_rules: false
  b_layer:
    provider: main
  embedding:
    provider: ollama
    model: bge-m3
```

## A 层 6 规则清单

| # | 正则 | 产出 skill |
|---|------|-----------|
| 1 | `写.*(代码|程序|功能|模块|接口|服务|爬虫)` | brainstorming (DISCOVER), test-driven-development (BUILD), planning-with-files (PLAN) |
| 2 | `ASCII|ascii|字符画|cowsay|figlet|文字艺术` | ascii-art (BUILD) |
| 3 | `股票|均线|MACD|KDJ|RSI|K线|走势|财务|A股|期货` | technical-analysis (DISCOVER), tushare-finance (DISCOVER) |
| 4 | `规划|方案|架构|设计.*系统|技术选型` | brainstorming (DISCOVER), writing-plans (PLAN), idea-foundry (PLAN) |
| 5 | `debug|修复|报.*(错|Error|Exception|异常)|bug|不工作|调试|KeyError|Traceback` | diagnose (DISCOVER), systematic-debugging (DISCOVER) |
| 6 | `UI|界面|设计.*(导航|页面|网页|布局|网站)` | brainstorming (DISCOVER), ui-ux-pro-max (BUILD), popular-web-designs (BUILD) |

## GREEN 5 场景验证

| # | 消息 | 期望 | A层命中 | B层兜底 | 结果 |
|---|------|------|:--:|:--:|:--:|
| 1 | 帮我设计一个响应式导航栏 | brainstorming, ui-ux-pro-max, popular-web-designs | ✅ 3/3 | — | PASS |
| 2 | 这段 Python 代码报 KeyError 帮我看看 | diagnose, systematic-debugging | ✅ 2/2 | — | PASS |
| 3 | 生成一个 ASCII 猫咪图 | ascii-art | ✅ 1/1 | — | PASS |
| 4 | 帮我写论文的 Related Work 部分 | research-paper-writing, paper-spine-research | ❌ 0 | ✅ 兜底 | PASS |
| 5 | 分析贵州茅台的均线走势 | technical-analysis, tushare-finance | ✅ 2/2 | — | PASS |

**结果：5/5 全通过。** A 层关键词覆盖 4/5 场景，学术写作场景由 B 层 embedding 兜底——双路径设计验证通过。

## SSR 注册日志

```
[ssr] 加载 A 层规则: 6 条
[ssr] 清理后 A 层规则: 6 条
[ssr] auto-gen 已关闭（ssr.auto_gen_rules: false）
[ssr] embedding 索引: 370 skill（增量同步）
[ssr] 插件注册完成 | skill: 370 | 残骸: 0 | A层: 6+0 | emb: 370 | B层: main
```

## 降噪前后对比

| 指标 | 降噪前 (v0.6.1) | 降噪后 (v0.6.2) |
|------|:--:|:--:|
| A 层规则数 | 61 | **6** |
| 手动规则 | 5 | **6（全手动）** |
| auto-gen 单字噪声 | 56 | **0** |
| 误报（work→writing-skills） | 有 | **消失** |
| GREEN 基准 | 未测（A层=0恢复后） | **5/5** |
| A 层命中率 | 100%（含大量噪音） | ~80%（精准定向） |

## 回退路径

备份：`~/.hermes/plugins/ssr/a_rules.json.bak` (9.5KB, 61条旧规则)

恢复命令：
```bash
cp ~/.hermes/plugins/ssr/a_rules.json.bak ~/.hermes/plugins/ssr/a_rules.json
# 然后重启 Hermes
```

## GREEN 快速修复（规则缺失时 · 2026-07-22）

当 `test_ssr.py` GREEN 关键词 < 5/5 时，两步修复：

**1. 定位缺失：** 运行 `test_ssr.py`，看哪些场景 ❌（如 UI设计、ASCII艺术）
**2. 补规则：** 确认 GREEN_TESTS 中该场景的 query + expected skills，在 `a_rules.json` 中新增或扩展现有规则

实例（v0.6.2→v0.6.3 13 条规则修复）：
- UI设计查询"帮我设计一个响应式导航栏"→ 旧 pattern 无"响应式""导航栏"→ 扩展 pattern + 补 brainstorming/popular-web-designs 到 skills
- ASCII艺术 → 新增独立规则，skills: ["ascii-art"]
- 结果：3/5 → 5/5 ✅
