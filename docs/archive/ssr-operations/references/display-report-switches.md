# display + report 双开关（v2.3.5）

两个独立开关控制 SSR 推荐对用户的可见程度：

```yaml
ssr:
  display: true    # false=完全静默, true=注入推荐到 AI 回复开头
  report: true     # false=不汇报, true=AI 每轮汇报用了没（v2.3.5 新增）
```

## 组合效果

| 组合 | 效果 |
|------|------|
| display:false + report:false | 完全静默 |
| display:true  + report:false | 用户看到推荐，AI 不汇报 |
| display:true  + report:true  | 全透明（推荐可见 + AI 汇报使用） |
| display:false + report:true  | ❌ 废组合，禁止 |

## report 行为

`ssr.report: true` 时，pre_llm_call 在推荐后追加 `[SSR-REPORT]` 指令。AI 在回复末尾一行汇报：

```
[SSR 使用] 推荐: plan, skill-creator | 已用: plan | 跳过: skill-creator(小改动不需要)
```

无推荐时：
```
[SSR 使用] 本轮无推荐
```

## 实现位置

| 层 | 位置 | 内容 |
|----|------|------|
| 配置 | `config.yaml` → `ssr.report` | 开关 |
| 插件 | `__init__.py` L205-209 | `_report_enabled()` |
| 插件 | `__init__.py` L2537-2540 | pre_llm_call 注入 `[SSR-REPORT]` |
| CMG | `rules/gap/rule_gap_ssr_report.md` | AI 自觉兜底 |

## 验证

```bash
# 确认配置
grep 'report' ~/.hermes/config.yaml

# 确认代码
grep '_report_enabled\|SSR-REPORT' ~/.hermes/plugins/ssr/__init__.py

# 确认 CMG 规则
ls ~/.hermes/self-reflection/rules/gap/rule_gap_ssr_report.md
```

重启 Hermes 后发消息，看回复末尾是否有 `[SSR 使用]` 行。

## 设计决策

- **为什么 report 走 pre_llm_call 注入而非 hook 拦截？** 汇报是 AI 自觉行为，不是强制拦截。插件注入指令 + CMG 兜底 = 双层保险，不引入新 hook。
- **为什么 display:false + report:true 是废组合？** 用户看不到推荐却要求 AI 汇报使用情况——汇报里列一堆用户没见过的 skill 名毫无意义。
- **与 CMG sentinel task_recommendations 的关系：** 互补。SSR report 汇报功能 skill 推荐，sentinel 推荐质量护栏工具。两个 pre_llm_call 注入并行不冲突。
