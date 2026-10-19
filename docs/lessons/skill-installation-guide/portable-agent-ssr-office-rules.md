# U盘便携版 — SSR 办公预设规则

> 用于 hermes-usb-portable 项目。U盘预装时替换默认 SSR 规则为办公场景优先。

## 为什么需要

当前 SSR 规则偏向开发/调试场景（diagnose、tushare-finance、technical-analysis），办公用户说的"做PPT""润色""做表"匹配不到正确 skill。

U盘版需要一套独立的办公优先规则。

## 推荐规则集

```json
{
  "做.*(ppt|演示|幻灯片|slides)": {"skills": ["pptx"], "phase": "BUILD"},
  "做.*(表|excel|表格|数据)": {"skills": ["xlsx"], "phase": "BUILD"},
  "润色|改改.*措辞|翻译|改写|polish": {"skills": ["nature-polishing"], "phase": "BUILD"},
  "写.*(论文|文章|稿子)": {"skills": ["nature-writing"], "phase": "BUILD"},
  "论文.*大纲|提纲": {"skills": ["nature-writing"], "phase": "PLAN"},
  "合同|文档|word|报告": {"skills": ["docx"], "phase": "BUILD"},
  "pdf|合并.*pdf|拆分.*pdf": {"skills": ["pdf"], "phase": "BUILD"},
  "计划|规划|安排|日程|行程": {"skills": ["plan"], "phase": "PLAN"},
  "思路|点子|想法|脑暴|头脑风暴": {"skills": ["brainstorming"], "phase": "DISCOVER"},
  "周报|日报|月报|工作.*总结": {"skills": ["docx", "nature-writing"], "phase": "BUILD"},
  "报销|发票": {"skills": ["xlsx"], "phase": "BUILD"},
  "填表|填.*表格|录入": {"skills": ["xlsx"], "phase": "BUILD"},
  "检查.*稿子|审查|校对": {"skills": ["writing-guidelines", "nature-reviewer"], "phase": "BUILD"}
}
```

## 与 SSR 自我进化的关系

SSR 自我进化（ssr-self-evolution 项目）完成后，这些手动规则会被自动学习替代。当前作为 MVP 阶段的起点规则。

## 使用方式

U盘制作时，将上述规则写入 `U盘/.system/hermes/ssr/a_rules.json`，替换原有规则。首次启动后 SSR 会从这些规则开始匹配，并随使用不断学习优化。
