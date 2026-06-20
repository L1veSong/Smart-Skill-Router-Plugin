# SSR auto-gen 基准测试 — 2026-06-09

## 背景
SSR v0.4 新增 `_auto_gen_a_rules()` 函数，从 294 skill description 提取关键词自动生成 A 层规则。本次测试验证其匹配质量。

## 方法
10 条典型用户消息，验证 A 层 auto-gen 规则匹配到期望 skill 的比例。

## 结果

**准确率: 1/10 = 10%**

```
🔴 "写一个React登录页面"     → 命中 2 个，期望 3 个 (ui-ux-pro-max/vercel-react/frontend-design) — 全漏
🔴 "帮我分析贵州茅台股票"     → 无匹配
🔴 "压缩终端输出节省token"   → 命中 1 个，漏 caveman
🟡 "bug修了不知道是不是真的好"→ 命中 diagnose，漏 verification-before-completion
🔴 "设计旅行网站给女朋友"     → 命中 1 个，漏 popular-web-designs/trip-website-generator
🔴 "写学术论文"              → 命中 1 个，漏 academic-paper/paper-spine
🟢 "生成ASCII艺术画"         → 命中 ascii-art ✅
🔴 "部署到Vercel"            → 命中 1 个，漏 deploy-to-vercel
🔴 "生成短视频"              → 无匹配
🔴 "review这个PR"            → 命中 2 个，漏 github-code-review
```

## 根因
- 从 description 提取的英文关键词如 "use"、"any" 匹配 50+ skill，大量噪音
- 中文关键词如"茅台""股票"在英文为主的 description 中不存在
- 用户自然语言和 skill description 的术语差距大

## 结论
auto-gen 只能做冷启动种子，不能做主力。B 层语义匹配是核心。B 层升级的规则质量远超 auto-gen。
