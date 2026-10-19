# SSR Auto-Gen 基准测试 (2026-06-09)

## 测试环境

- SSR 版本：v0.3.0 + auto-gen patch
- A 层规则：2073 条（从 294 skill description 自动生成）
- 测试消息：10 条中文自然语言用户消息
- B 层：未参与（纯 A 层测试）

## 结果：准确率 10%（1/10）

| # | 消息 | 期望命中 | A 层匹配 | 结果 |
|---|------|---------|---------|------|
| 1 | "写一个React登录页面" | frontend-design, ui-ux-pro-max, vercel-react-best-practices | 匹配 2 个（非目标） | 🔴 |
| 2 | "帮我分析贵州茅台股票" | technical-analysis, tushare-finance | 无匹配 | 🔴 |
| 3 | "压缩一下终端输出节省token" | caveman | 匹配 1 个（非目标） | 🔴 |
| 4 | "这个bug修了但不知道是不是真的好" | diagnose, verification-before-completion | 命中 diagnose，漏 verification | 🟡 |
| 5 | "设计一个旅行网站给女朋友" | popular-web-designs, trip-website-generator | 匹配 1 个（非目标） | 🔴 |
| 6 | "写一篇学术论文" | academic-paper, paper-spine | 匹配 1 个（非目标） | 🔴 |
| 7 | "生成ASCII艺术画" | ascii-art | 命中 | 🟢 |
| 8 | "部署到Vercel" | deploy-to-vercel | 匹配 1 个（非目标） | 🔴 |
| 9 | "帮我生成短视频" | ai-short-film-production | 无匹配 | 🔴 |
| 10 | "review这个PR" | github-code-review | 匹配 2 个（非目标） | 🔴 |

**🟢1 🟡1 🔴8**

## 根因分析

### 1. description 语言与用户自然语言不匹配
- 用户说"茅台股票"，skill description 里是 `tushare-finance`（纯英文函数库名）
- 用户说"旅行网站"，description 是 `trip-website-generator` 和 `popular-web-designs`
- A 层只知道在 description 中搜索关键词，不知道在语义层匹配

### 2. 高频词噪音
- `use`, `file`, `data`, `create` 等词出现在 50+ skill 的 description 中
- `_auto_gen_a_rules` 的停用词表不够全面

### 3. 中文词提取粗糙
- 中文词只取 2-4 字固定窗口（如"旅行网站"），无法捕捉"旅游网站""出行规划"等变体

## 修正方向

**短期：B 层兜底。** A 层 accuracy 10% 但 B 层（LLM 语义匹配）应该能救回来。B 层 prompt 已改为"不限数量"，让 DeepSeek 理解用户意图后匹配。

**中期：Embedding 替代 auto-gen。** 用 `nomic-embed-text` 向量化 294 skill description → 用户消息向量化 → 余弦相似度 Top-N。成本：274MB 模型 + 一次索引构建。

## 教训

- auto-gen 关键词不能独立工作——10% 准确率证明它只能做冷启动种子
- 核心依赖是 B 层（LLM 语义）→ A 层（升级后的精确规则）的循环
- 删除旧的 B 层升级规则（a_rules.json）是本次低准确率的部分原因——高质量规则丢失
