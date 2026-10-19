# SSR 回归测试指南

> 配套工具: `~/.hermes/plugins/ssr/test_ssr.py` (v1.0)

## 何时测试

- 修改 SSR `__init__.py` 后
- 调整 `similarity_floor` / `confidence_threshold` 后
- 新增/删除 skill 后（验证 embedding 索引完整性）
- Hermes 大版本升级后
- 用户说「SSR 不准」时

## 测试套件

```bash
cd ~/.hermes/plugins/ssr
python3 test_ssr.py          # 全量（含 bge-m3 embedding，需 Ollama）
python3 test_ssr.py --quick   # 快速（文件+规则+GREEN+配置，5秒）
```

### 覆盖范围 (8 大类 34 项)

> **当前环境 (2026-06-14):** embedding: bge-large-chinese (1024维, 纯中文) | skill 索引: 370 | B 层 provider: main (DeepSeek) | A 层: 重启清零需预热

| 类别 | 验证内容 |
|------|---------|
| 文件完整性 | __init__.py / a_rules.json / embeddings.json 存在且含关键函数 |
| 规则有效性 | 100 条正则均可编译、含 skills 字段、引用的 skill 在 embedding 索引中 |
| Embedding 索引 | 246 条全部 1024 维 |
| 配置验证 | config.yaml 含 ssr:节 + floor/conf 值正确 |
| GREEN 关键词 | 5 场景全部命中（UI/调试/ASCII/论文/金融） |
| GREEN Embedding | 5 场景 top-10 检查（2 个已知弱项标记兜底） |
| 阈值过滤 | 噪音 floor 过滤 + 强意图通过 |
| Dashboard | HTTP 200 |

## GREEN 基准场景

| # | 消息 | 期望命中 |
|---|------|---------|
| 1 | 帮我设计一个响应式导航栏 | brainstorming, ui-ux-pro-max, popular-web-designs |
| 2 | 这段 Python 代码报 KeyError 帮我看看 | diagnose, systematic-debugging |
| 3 | 生成一个 ASCII 猫咪图 | ascii-art |
| 4 | 帮我写论文的 Related Work 部分 | research-paper-writing, paper-spine-research |
| 5 | 分析贵州茅台的均线走势 | technical-analysis, tushare-finance |

通过标准: ≥3/5 关键词命中, 目标 ≥5/5。

## 阈值调整验证

调整 `similarity_floor` 或 `confidence_threshold` 后必须验证：

1. **GREEN 不受影响**: 5 场景关键词路径置信度恒为 1.0，不受阈值影响
2. **噪音被过滤**: 发送「嗯嗯好的」「今天天气」→ 期望不推荐或推荐少
3. **强意图通过**: 「帮我设计一个登录页面」→ 期望有推荐

## 已知限制

### bge-m3 噪音基线偏高 (0.35-0.50)

短文本（闲聊、单字回复）的 embedding 相似度分布在 0.35-0.50，floor=0.35 无法有效过滤。
**实际防护**: 噪音不命中关键词规则 → A 层 keyword_hits 为空 → embedding 兜底但不精准。

### bge-m3 中文术语弱

「均线走势」→ bge-m3 匹配 `baoyu-article-illustrator`(0.45) > `technical-analysis`(不在 top-30)。
「Python KeyError」→ bge-m3 匹配 `debugging-hermes-tui-commands`(0.58) > `diagnose`(不在 top-10)。
**实际防护**: 关键词规则 `分析.*(股票|走势|均线|K线)` / `(debug|调试|报错|bug|error).*(代码|程序|python)` 精准兜底。

### YAML block scalar 空描述

`description: |` 后无内容的 skill 不会被索引。影响 `idea-foundry` / `tushare-finance` / `technical-analysis`。
`_get_skill_info()` 已修复（增加 block scalar 解析 + 正文 fallback），重启 Hermes 后自动重建索引。

## 重启验证清单（每次 Hermes 重启后必做）

```bash
# 测1：A 层存活
grep '加载 A 层规则\|清理后 A 层\|无匹配' ~/.hermes/logs/agent.log | tail -5
# 期望：[ssr] 加载 A 层规则: N 条（N > 0）
# 如果 N=0 → A 层清零，确认 embeddings.json 是否完好（B 层兜底可用但首条消息走慢路径）

# 测2：GREEN baseline（依次发5条消息，≥3/5 通过）
# 1. 帮我设计一个响应式导航栏
# 2. 这段 Python 代码报 KeyError 帮我看看
# 3. 生成一个 ASCII 猫咪图
# 4. 帮我写论文的 Related Work 部分
# 5. 分析贵州茅台的均线走势

# 测3：Reasonix 集成（如已配置）
```

### A 层重启清零

**症状（2026-06-14 确认）：** 重启后 A 层规则归零（加载 0 条 + 清理后 0 条），embeddings.json（370 skill, 8MB）完好。A 层规则文件不持久化——重启必清零。B 层向量匹配仍可用，但前几条消息走 B 层慢路径。

**根因：** A 层关键词规则表存储在内存中（从 B 层命中 ≥3 次动态升级），未落盘到持久文件。重启后重建需重新积累。

**缓解：** 启动后先跑 GREEN baseline 5 条，让 B 层预热 → 命中积累 → 自动升级到 A 层。

### B 层命中不存在的 skill

**症状（2026-06-14）：** SSR echo 显示 `[SSR] 建议加载:` 但冒号后为空。日志显示 `B 层命中: ['investigate']`，但 `investigate` 不是真实 skill 名。

**根因：** B 层向量匹配返回的是语义标签/内部标识符，未验证是否对应可用 skill。匹配到的标签不在 skill 注册表中 → echo 过滤后为空输出。

**检查方法：**
```bash
grep 'B 层命中' ~/.hermes/logs/agent.log | tail -5
# 对照 skills_list 验证命中名称是否为真实 skill
```

### SSR echo 格式异常

**症状（2026-06-14）：** 用户看到 `[SSR] 建议加载:\n` —— 字面量反斜杠 n 而非换行。

**根因：** echo 消息中的换行符未正确转义，`\\n` 被当作两个字符而非换行。需检查 `__init__.py` 中 echo 消息的构造逻辑（字符串拼接 vs 正确处理换行）。

## 常见故障排查

| 症状 | 检查 | 修复 |
|------|------|------|
| A 层 0 命中 | `grep 'A 层' agent.log` | 检查 a_rules.json 是否存在、规则是否损坏 |
| A 层重启清零 | `grep '加载 A 层规则: 0 条' agent.log` | B 层兜底可用，跑 GREEN baseline 预热重积累 |
| B 层命中不存在 skill | `grep 'B 层命中' agent.log` → 对比 skills_list | 向量匹配返回标签→需验证 skill 注册表；短期在 echo 中过滤无效命中 |
| B 层超时 | `grep 'B 层' agent.log` | 检查 B 层 provider（main/ollama）是否可用 |
| embedding 索引缺失 skill | `python3 test_ssr.py` 规则有效性项 | 重启 Hermes 触发 _sync_embeddings() |
| Dashboard 不可达 | `curl localhost:8768` | 检查端口是否被占用、是否启动 |
| GREEN 失败 | 对比期望命中 vs 实际 | 关键词路径失效→检查 a_rules.json；embedding 弱→关键词兜底可接受 |
| SSR echo 为空或格式错 | 对比日志中的命中 vs 用户看到的输出 | 检查 echo 过滤逻辑 + 换行转义 |
