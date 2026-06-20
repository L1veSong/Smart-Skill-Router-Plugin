# Smart Skill Router — Changelog

## v1.5.0 (2026-06-20)

### 修复：推荐位置硬编码 prepend

- **根因：** append 模式结构性无解——Hermes 回复截断从尾部来，SSR 推荐也在尾部，截断必中。
- **处理：** 删除 `_ssr_position()` 函数（不再读取配置），`post_llm_call` 条件检查一并删除。推荐固定前置到回复开头。
- **影响：** SSR 推荐永远可见，不再因长回复截断而丢失。SKILL.md 配置节移除 `position` 字段。`post_llm_call` 必须开启。
- **测试：** TDD 基线 12/12 全通过（RED 0/5 + GREEN bge-m3 5/5 + GREEN nomic 5/5 + REFACTOR N/A）。

### 坑点新增

- **坑点 28:** 手动改 `__init__.py` 函数误入模块 docstring → SyntaxError。
- **坑点 29:** 全角标点触发 Python 3.12 SyntaxError。
- **坑点 30:** append 模式结构性无解——截断从尾部来=推荐在尾部，物理互斥。
- **坑点 31:** 改代码后必须测试再声称完成。

## v0.6.3 (2026-06-14)

- 修复 echo 输出格式截断：`[SSR] 建议加载:\n` 字面量反斜杠-n 导致 skill 名不显示。
- 根因：Python 字符串转义过度（`"\\n"` 是两个字面字符，`"\n"` 才是换行）。

## v0.6.2 (2026-06-14)

- 修复 miss 路径无日志 → 假性沉默（A 层空 + B 层 miss → zero output → 看起来像 hook 未触发）。
- 修复 a_rules.json 空覆盖导致规则永久丢失（内存异常重置 → `json.dumps({})` → 2 字节 `{}` → 所有规则消失）。
- 新增：写前备份 + 损坏备份 + 诊断日志。

## v0.6.1 (2026-06-10)

- 智能冷却（Phase 5a）：自适应冷却替代分阶段冷却，含已加载检测/反复推荐未加载/明确不需要/紧急消息/任务切换 5 条规则。
- 增量索引自动运行（Phase 5b）：10 分钟自动 sync + description 变更检测。
- 6 Phase 全部闭环。TDD 5/5 GREEN（bge-m3），nomic 5/5（排名差）。

## v0.6.0 (2026-06-10)

- 三层漏斗架构：中文查询增强（14 域中英映射）→ A 层关键词精确匹配 → A 层 Embedding 语义匹配 → 合并去重 → B 层 LLM 兜底。
- 描述富化：SKILL.md 正文提取（前 3 段散文段落）追加到 YAML description，bge-m3 匹配质量提升。
- Dashboard 统计面板：`/api/stats` 端点 + 6 格统计卡。
- 会话命中日志：每 10 次调用输出命中率统计。

## v0.5.1 (2026-06-09)

- auto-gen 开关：`ssr.auto_gen_rules: false` 关闭 auto-gen（准确率仅 10%），仅保留手动规则 + embedding。
- 冷却制修复：冷却不删除匹配结果，改为 `shown_recently` 标记，展示加 `(刚才)`。

## v0.5.0 (2026-06-09)

- Embedding 层上线：bge-m3（1024 维，q4_k_m 438MB）替代 nomic-embed-text（768 维，中文区分度极低）。
- TDD 基准测试框架：RED→GREEN→REFACTOR 三阶段。
- B 层预过滤：关键词粗筛 296→~20 候选，prompt 从 ~3000→200 token。
- B→A 升级：连续 3 次同一匹配自动固化到 A 层。

## v0.3.0 — v0.4.0 (2026-06-05 — 2026-06-09)

- A 层规则回退修复：延迟写盘系统（dirty 标记 + 批量 flush）。
- B 层三后端：main / ollama / openai。
- 会话去重 → 冷却制（60s 非永久）。
- B 层 `main` 模式 401 修复 + key 截断修复。
- SSR 存活验证流程（6 步）。

## v0.1.0 — v0.2.0 (2026-06-04)

- 初始实现：A 层关键词精确匹配 + B 层 LLM 语义匹配。
- 11 条种子规则（设计/调试/写代码/论文/ASCII/金融/旅行）。
- 预热机制：register() 时 ping Ollama 避免首次 B 层冷启动。
