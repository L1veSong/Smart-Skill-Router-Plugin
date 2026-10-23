# Reasonix 集成诊断 — 2026-06-14

## F5: Reasonix ACP 可用，CMG ban 关键词误杀子agent输出

**根因：** cmg-guard 的 `_transform_llm_output` 对所有 LLM 输出无差别扫描 ban 关键词。
当 Hermes relay delegate_task 子agent 结果时，Reasonix 输出的自然语言文本含"创建""发布"等中文日常词，
触发 `ban_dashboard_dev_without_skills`（关键词："创建"）和 `ban_packaging_missing_files`（关键词："发布"），
导致子agent返回结果被替换为 `[CMG 拦截]`。

**修复：** `_transform_llm_output` 加 `_is_subagent_relay()` 预检——检测到 delegate_task/Reasonix/子agent
输出时跳过 `_scan_text()` ban 关键词扫描，保留 `_scan_blacklist()`。

**改动文件：** `~/.hermes/plugins/cmg-guard/__init__.py` — 新增 `_is_subagent_relay()` + 修改 `_transform_llm_output`

## F6: Reasonix 三种模式能力矩阵

| 模式 | 命令 | 执行能力 | 适用场景 |
|------|------|:--:|------|
| shell | `reasonix run "task"` | ❌ 只生成代码建议 | 问"怎么写" |
| MCP | `reasonix mcp` | 暴露工具 | 给别人用 |
| ACP | `reasonix acp` | ✅ 自主调工具 | 委托任务 |

`delegate_task(acp_command="reasonix", acp_args=["acp"])` 正确用法。

注意：`acp_args` 是 `["acp"]`（子命令），不是 `["--acp", "--stdio"]`（这是 Hermes 内部 ACP transport 参数，Reasonix 不认识）。

---

# 重启验证 — 2026-06-14 17:26

## F7: T4 重启验证结果

**测1 SSR 诊断日志：**
```
[ssr] 加载 A 层规则: 0 条
[ssr] 清理后 A 层规则: 0 条
```
→ Z=0。`_load_a_rules()` 阶段已归零（文件存在但为空 `{}`）。T3 的备份机制未触发（文件无损坏，是合法空 JSON）。

**测2 GREEN baseline（5条消息）：**

| # | 消息 | SSR | 命中 |
|---|------|-----|------|
| 1 | 响应式导航栏 | 无匹配 | — |
| 2 | Python KeyError | B层 | `investigate`（非真实skill）|
| 3 | ASCII 猫咪图 | 无匹配 | — |
| 4 | 论文 Related Work | 无匹配 | — |
| 5 | 茅台均线走势 | B层 | `technical-analysis`, `short-term-trader-perspective` |

**2/5，不到 3/5 及格线。** 实际有用命中仅 1 条（茅台）。

**测3 Reasonix 集成：** ✅ 通过。`read_file` 读取 `~/.hermes/plugins/ssr/__init__.py` 第 2 行成功，CMG 未拦截。

## F8: SSR echo 格式 bug（2026-06-14 18:06 确认根因+修复方案）

**症状：** 用户看到 `[SSR] 建议加载:\n` —— skill 名不显示，反斜杠 n 是字面量。

**根因（已确认）：** `__init__.py` L1424-1427：

```python
# ❌ L1424: 字面量 \n 拼接（两字符：反斜杠+n）
body = "\\n".join(lines)

# ❌ L1427: f-string 中 \\\\n = 字面量 \n（两字符）
return f"{prefix}\\\\n{body}"
```

Python 中 `"\\n"` 是两个字面字符，`"\n"` 才是换行。f-string 同理——`\\\\n` = 字面量。

**修复：**
```python
# ✅ L1424: 实际换行拼接
body = "\n".join(lines)
# ✅ L1427: 实际换行分隔
return f"{prefix}\n{body}"
```

L1426 enforce 模式同样修复。

**影响文件：** `__init__.py` L1424/1426/1427，3 处改动。

**状态：** 归入 v0.6.3 Task 1（P0）

---

## F9: a_rules.json 空覆盖根因（2026-06-14 17:50）

**症状：** 重启后 A 层归零。文件 2字节 `{}`，备份（16:15）有100条。

**时间线：**
- 16:15: 备份创建（100条规则）
- 16:24: Session 162423 启动，SSR 正常加载100条，A层开始命中
- 16:50:26: a_rules.json mtime → 2字节 `{}`。后台 review agent 显示 A层: 0+0
- 16:54: 主 session 仍在命中 A层（内存副本完好，文件已被覆盖）
- 17:26: 新 session → A层 0条

**根因：** v0.6.1 `_save_a_rules()` 无空覆盖保护。最可能路径：主 session 运行期间 `_flush_a_rules()` 的某次调用时 `_A_RULES` 被重置为空（模块热重载/内存异常）→ `json.dumps({})` → 2字节覆盖 → 100条规则永久丢失。

**v0.6.2 已修复：**
- T3: `_save_a_rules` 检测空覆盖 → 自动备份到 `.json.bak`
- T1: `register()` 三步诊断日志
- 即使复现也有备份可恢复

**恢复操作：** 从 16:15 备份恢复，清洗 39 条噪声规则（paper-spine 全系、huashu-nuwa、design-taste-frontend-v1、perspective 类等），保留 61 条有用规则。

---

## F10: 降噪彻底完成（2026-06-14 17:58）

**状态：** a_rules.json 61→6 条，全手动，零 auto-gen。

**操作：** 用户手动清洗 a_rules.json，删 56 条 auto-gen 单字噪声 + 39 条噪声规则，保留 6 条经实战验证的手动规则。关闭 `ssr.auto_gen_rules`。

**验证：**
```
[ssr] 加载 A 层规则: 6 条
[ssr] 清理后 A 层规则: 6 条
[ssr] auto-gen 已关闭
GREEN 基准: 5/5 全通过
```

**效果：**
- work→writing-skills 误报消失
- 单字噪声（skill/work/only/call/time 等 56 条）清零
- A层命中率从 ~0%（空覆盖恢复后）恢复到 80%（4/5 场景关键词命中）
- 学术写作场景不命中是设计内的——6 条规则未覆盖，B层 embedding 兜底

**备份：** a_rules.json.bak (9.5KB) 安全保留

## F11: 降噪方案变更（代码过滤→手动清洗）

**原计划：** 在 `__init__.py` 新增 `_purge_single_word_rules()` 代码过滤函数

**实际方案：** 直接编辑 a_rules.json 手动清洗

**原因：** 
1. 代码过滤只能删单英文词，手动清洗可同时去除 paper-spine/huashu-nuwa/perspective 等非单字噪声
2. 用户有明确意见——从零开始，只保留验证过的规则
3. 结果更干净：6 条 vs 计划 60 条

**未执行的 Task (2/3/4)：** 延期。6 条精准规则 + bge-m3 兜底 → embedding 门控/中文扩展/similarity_floor 提升不再紧迫。等规则增长到 20+ 条时再评估。

## F12: 版本号债务（2026-06-14 18:06）

| 文件 | 当前版本 | 目标 | 滞后 |
|------|---------|------|:--:|
| `__init__.py` | v0.6.2 | v0.6.3 | 1 |
| `plugin.yaml` | **v0.3.0** | v0.6.3 | 3 大版本 |
| `CHANGELOG.md` | v0.6.1 | v0.6.3 | 缺 2 次 |

**影响：** plugin.yaml 是 Hermes 识别插件版本的权威来源。0.3.0 = 发布系统的版本盲区。

**修复：** 归入 v0.6.3 Task 2（plugin.yaml）+ Task 3（CHANGELOG）

---

# v2.3 基线诊断 — 2026-07-22

## F13: A 层实际覆盖率 12%（非 master-status 声称的 101 条）

**实测：** `a_rules.json` 只有 12 条规则（98 行），覆盖 25 个 skill。master-status.md 声称「101 条 v3 格式」——严重滞后。实际在 F10（6 条）之后又手工加了 6 条，总计 12 条但从未更新 master-status。

**影响：** 12/200+ = 6% skill 覆盖率。A 层基本靠手工维护，增长缓慢。

## F14: B 层 embedding 噪声 — nature-citation + storage-analyzer 盲绑定

**症状：** 7 月 3 日日志中 `nature-citation` + `storage-analyzer` 组合出现 3 次。两个 skill 语义零相关（学术引用格式 vs 磁盘清理），但 Qwen3-Embedding-8B 把它们算出了高余弦相似度。

**影响：** B 层有 false positive 风险。`confidence_threshold: 0.62` 过滤了大部分，但无法根除。

## F15: auto_gen_rules 曾被用户关闭（F10），当前仍为 false

**历史：** 2026-06-14 用户手动清洗 a_rules.json，从 100 条砍到 6 条，关闭 auto_gen_rules。原因是 auto-gen 产生了大量单字噪声（work/skill/only/call/time 等 56 条）。

**现状：** 当时 6 条够用，现在 12 条不够。auto-gen 质量取决于 skill description 的写法——当前 200+ skill 的 description 已大幅改善。

## F16: confidence_threshold 保守但有效

**实测：** B 层 28 次命中，0 次失败超时。0.62 阈值在"不乱推"和"不漏推"之间取了保守侧。用户反馈「推的就是对的」——当前策略方向正确。
