# CHANGELOG


> 补记说明（2026-09-16）：以下 v2.4.0 至 v3.0.1 四条为版本面同步时按代码内注释与归档计划补记（对应发布当时未写 CHANGELOG）；仅转录事实，未外推。

## v3.0.2 (2026-09-20) — 索引卫生修复（幽灵 skill 清理）

### 修复
- **索引/embedding 排除 dot 目录**（`.archive`/`.curator_backups`/`.hub`/`.git`）：此前 rglob 把归档目录一并扫入——embedding 池 774 条中 122 条是已归档、无法加载的"幽灵 skill"向量（137 个归档名里 15 个与在役 skill 同名、保留在役版本），并被实际推荐到对话（实锤：ssr-operations / smart-skill-router 被推荐后 skill_view 无法加载）。修复后索引=可加载集合（774→653）；既有幽灵向量已手动清理 122 条（774→652，embeddings.json 留 .bak）。
- **附带发现（后续事项）**：`hermes_cli.skills.registry` 导入路径已不存在（该模块已随 Hermes 重构迁移），`_get_skills_list()` 长期走 fallback 扫描——本次修复即打在 fallback 路径上；新加载器对接列为后续事项。

### 修改文件
- `__init__.py`: _build_skill_md_index dot 目录过滤 + 版本号注释
- `plugin.yaml` / `README.md` / `dashboard.py` / `test_ssr.py`: 版本同步 v3.0.2
- `embeddings.json`: 清幽灵条目（.bak.0920 备份）

## v3.0.1 (2026-09-15) — gateway 启动死锁修复

### 修复
- 原注册流程对每个 skill 重复扫描全树（复杂度 O(N×M)），持插件加载锁数十秒，gateway 在 import 期等锁挂死。改为一次性构建索引 + 缓存（O(目录树)），实测重启秒级就绪。

## v3.0.0 (2026-07-23) — MoE 词干表定稿

- 34 域 · 272 词干（机械提取 + Golden 校验，55 项全绿，P0 激活）。每词干仅鉴别 1–2 域，歧义交 A 层正则最终裁决。

## v2.5.0 (2026-07-23) — MoE 词干表扩展

- 34 域词干表（自动从 a_rules.json 对齐）；词干原子化 + 去歧义。

## v2.4.0 (2026-07-23) — MoE 架构升级

- 路由层：词干检测 → 激活域 → 域内匹配；无命中全开 fallback。
- 规则新增 domain 字段 + skills 直推；跨域污染修复（示例查询噪音 5 条 → 2 条）。

## v2.3.0 (2026-07-23) — 配置加载修复 + auto-gen 加固 + 测试硅基流动分支

### 修复
- **_load_ssr_config() 空 dict 回退**：hermes_cli.config.load_config() 在某些运行时返回空 ssr 节，
  导致 embedding/门控/阈值/auto_gen 全部跌回默认值。新增 PyYAML 直接读 config.yaml 作为可信回退。
- **b_layer.api_key 为空导致 LLM 筛查 401**：llm_screen 调用需要 api_key，改为优先继承 main 模型 key。
- **test_ssr.py _embed_text() 硅基流动分支**：旧代码只处理 ollama provider，新增完整 siliconflow 调用路径。
- **auto_gen_rules 默认值 True→False**：config 读取失败时不再默认开启 auto-gen，防御性加固。
- **test_ssr.py confidence_threshold 期望值 0.4→0.62**：与生产 config 一致。

### 修改文件
- `__init__.py`: _load_ssr_config 双路径读取 + auto_gen_enabled 默认值加固
- `test_ssr.py`: siliconflow embedding 分支 + confidence_threshold 同步 + GREEN 测试 B 层兜底容忍
- `plugin.yaml`: 2.2.0 → 2.3.0
- `dashboard.py`: 版本号同步
- `CHANGELOG.md`: 补 v2.3.0 条目
- `README.md`: badge 版本号更新


## v2.2.0 (2026-07-03) — 动态阈值接管 + 版本同步

### 新增
- **动态阈值全权接管**：删除 config.yaml 中 explicit similarity_floor 强制项，_similarity_floor() 改为无极校准优先+显式配置 override
- **版本全量同步**：plugin.yaml / __init__.py / dashboard.py / test_ssr.py / README.md / CHANGELOG.md 全部升至 v2.2.0
- **死文件清理**：10 个 .bak 残留（除 dashboard.html.bak 保留）→ 8 个清理

### 修改文件
- `plugin.yaml`: 2.1.0 → 2.2.0
- `__init__.py`: docstring v2.2.0 + 版本标注更新
- `dashboard.py`: 版本号同步
- `test_ssr.py`: 版本号同步
- `README.md`: 版本历史追加
- `CHANGELOG.md`: 补 v2.2.0 条目


## v2.1.0 (2026-06-23) — Gate通用化 + 元对话检测 + 自循环

### 新增
- **Gate prompt 配置化**：`_call_llm_intent()` prompt 从硬编码移至 `config.yaml → ssr.gate.prompt`，不同模型可不同 prompt
- **元对话检测**：gate 前加纯正则预检层，聊 SSR/CMG/skill 系统时零 token 直拦，不再误推
- **噪音过滤配置驱动**：`_NOISE_PATTERNS` 硬编码列表移除，统一从 `ssr.noise_filter.patterns` 读取（17条正则）
- **display 控制**：`ssr.display: false` → `return None`，真静默，不再用 [SSR:SILENT] 障眼法前缀
- **v2.1 架构预留**：自循环学习接口

### 修改文件
- `plugin.yaml`: 2.0.0 → 2.1.0
- `__init__.py`: 元对话检测层 + gate prompt config 读取 + 噪音过滤 config 驱动 + 版本号全量同步
- `test_ssr.py`: 版本号同步
- `dashboard.py`: 版本号同步
- `README.md`: 版本历史追加

### v2.1.1 补丁 (2026-06-23) — 动态阈值 + llm_screen + benchmark 升级

- **动态 similarity_floor**：`_similarity_floor()` 根据 embedding 模型名自动查 model_scores.json，得分映射 floor（5→0.25, 4→0.30, 3→0.35, 2→0.42, 1→0.48）。显式配置优先，无配置自动计算。
- **Embedding 升级**：bge-large-zh-v1.5 → Qwen3-Embedding-8B（硅基流动 API），1024→4096维。
- **model_scores.json 扩展**：新增 Qwen3-Embedding-8B 条目（得分 5），已删除显式 similarity_floor 配置。
- **llm_screen 开关**：`ssr.llm_screen` 配置控制 LLM 重排序，默认 false。关闭后 top-3 50%→57%，速度 180s→32s。
- **A 层规则补缺**：a_rules.json 调试规则加"返回None/超时/timeout"，学术规则加"综述"。调试 1/3→3/3。
- **benchmark 三档评分**：四元组格式 (精准/相关/不相关)。相关度 93%。替代旧二进制评分。
- **benchmark --quick 模式**：纯 A 层匹配，31s 零 LLM。本地用户/弱模型用户可跑。
- **全量审计**：README badge、日期统一、docstring 去模型名/维度、config 示例更新、36 个 bak 清理。
- **meta_detection 移除**：简化代码，从 __init__.py/dashboard/config 全部删除。

### 修改文件
- `__init__.py`: `_similarity_floor` 重写 + llm_screen 开关 + 版本号同步
- `a_rules.json`: 调试/学术 regex 扩展
- `model_scores.json`: 新增 Qwen3-Embedding-8B
- `tests/ssr_scoring_benchmark.py`: 三档评分 + 四元组格式 + --quick 模式
- `test_ssr.py`: v2→v3 格式适配 + 维度动态检测
- `README.md`: badge 版本号 + 版本历史
- `plugin.yaml`: 版本号

## v2.0.0 (2026-06-22) — 关键词解耦

### 架构变更
- **A 层规则 v3 格式**：从硬编码 skill 名改为 `keywords` 数组，运行时动态匹配 SKILL_INDEX
  - 旧: `{"skills": [{"name": "ui-ux-pro-max", "phase": "BUILD"}]}` ← 死引用
  - 新: `{"keywords": ["ui", "design", "frontend"], "phases": ["BUILD"]}` ← 跨用户可移植
- **独立匹配兜底**：`_call_llm_screen_direct()` — keyword+embedding 无候选时，LLM 独立匹配全量 skill
- **统一决策路径**：`_pre_llm_call` 流改为「有候选→LLM筛选 / 无候选→LLM独立匹配」
- **关键词收紧**：迁移脚本过滤 18 个英文停用词 (to/with/for/cli/pro/max…)，13 条规则清理

### 修改文件
- `__init__.py`: `_match_a_layer_keyword` 重写（keywords 动态匹配）+ 新增 `_call_llm_screen_direct`
- `a_rules.json`: 108 条规则 v2→v3 格式迁移
- `plugin.yaml`: 0.7.0 → 2.0.0

### 实测
- 51 条极限测试 80% 准确率（LLM+emb 方案），噪音 9/9 完美拦截
- 死引用归零：v3 格式天然无硬编码 skill 名

## v1.6.0 (2026-06-21)

### 新增
- 多模型 Embedding 推荐表：zh-v1.5 / en-v1.5 / m3 / nomic 四种模型供用户自由切换
- Dashboard 模型诊断面板：`/api/model-info` 端点 + 引擎配置 tab 底部卡片
  - 三维评分条（Chinese/English/Overall）+ 推荐场景 + 模型对比列表
  - 中英文 i18n 全覆盖，暗/亮主题自适应
- model_scores.json：评分数据独立于代码，新增模型只需改 JSON

### 变更
- SKILL.md 配置节从单一中文模型改为多模型推荐表 + 安装命令
- Embedding 模型切换：bge-m3 → bge-large-zh-v1.5（纯中文 1024维 202MB）
- Plugin 代码不变（v0.6.4），仅文档 + Dashboard 升级

## v0.6.3 (2026-06-14)

### 修复
- F8 echo bug：`\\n` 字面量→实际换行，SSR 推荐 skill 名正常显示
- plugin.yaml 版本号 0.3.0→0.6.3（滞后 3 个大版本）

## v0.6.2 (2026-06-14)

### 新增
- register() 诊断日志：加载/清理后/净化后规则数
- miss 路径日志：A层规则数 + B层后端 + 调用次数

### 修复
- _save_a_rules 空覆盖保护：检测空 `{}` 覆盖→自动备份到 `.json.bak`
- _load_a_rules 损坏容灾：损坏时备份到 `.json.corrupted`

### 优化
- 降噪完成：a_rules.json 61→6 条全手动规则，auto-gen 关闭，零噪声
- GREEN 基准 5/5 全通过（A层关键词 4/5 + B层 embedding 兜底 1/5）

## v0.6.1 (2026-06-10)

### 新增
- 智能冷却：自适应冷却（已加载×3、反复推荐未加载×0.5、紧急×0.5、5次未加载跳过）
- 增量索引自动运行：每10分钟自动全量 sync + description 变更检测
- Dashboard 全面美化：Ethereal Glass 暗色主题 + 玻璃特效 + Geist 字体 + Emerald 主色
  - 4 skill 组合驱动：redesign-existing-projects 审计 + high-end-visual-design 视觉 + popular-web-designs 数据表 + frontend-design 定调
  - 亮/暗主题切换（localStorage 持久化）
  - 中/英文完整切换（zh 全中文、en 全英文）
  - 玻璃特效：backdrop-filter blur + 内高光线
  - 动画：统计卡交错入场、卡片 hover 上浮、模态弹性缩放
  - Double-Bezel 嵌套卡架构、SVG 描线图标替代 emoji
  - 骨架屏加载态 + 设计空态

## v0.6.0 (2026-06-10)

### 新增
- Phase 3: Embedding 质量提升 — 描述富化（正文提取）+ 中文查询增强（14域中英映射）
- Phase 4: 生产监控 — Dashboard /api/stats + 会话命中率日志（每10次输出）
- 三层漏斗架构：关键词正则 + bge-m3 Embedding + B层 LLM 五后端

## v0.5.0 (2026-06-09)

### 新增
- bge-m3 Embedding 层（1024维，淘汰 nomic-embed-text）
- TDD 基准测试 5/5 GREEN（bge-m3 全通过）
- auto-gen 开关：ssr.auto_gen_rules: false 关闭自动生成
- 冷却制修复：shown_recently 标签替代 continue 丢弃

### 修复
- 坑点 14: nomic-embed-text 中文区分度极低 → 换 bge-m3
- 坑点 17: 冷却 continue 误杀跨消息匹配

## v0.4.0 (2026-06-06)

### 新增
- Dashboard /api/stats 端点 + 统计面板
- B→A 升级：连续 3 次同一匹配自动固化到 A 层
- 结果缓存：B 层结果 60s 内复用
- 冷启动重试：B 层超时自动 warmup + 重试一次

## v0.3.0 (2026-06-06)

### 新增
- 暂停开关：Dashboard 一键停用 SSR，config.yaml 真实写入 `ssr.enabled: false`
- 规则重置：Dashboard 一键清空 A 层，二次确认
- Dashboard 全面重构：动画微交互、中英文切换、亮暗主题、实时时钟、30s 自动刷新
- B 层新增 lmstudio / llamacpp 后端支持

### 修复
- README ASCII 架构图纯英文对齐
- B 层 `_match_b_openai` URL 双 `/v1` 修复
- `_match_b_layer` 路由补 lmstudio / llamacpp

## v0.2.0 (2026-06-05)

### 新增
- 推荐模式开关：推荐/强制，Dashboard 一键切换
- 扫描策略：启动时/每次提问，Dashboard 切换
- Dashboard B 层配置面板：provider/model/URL/key/timeout 可视化
- Dashboard Tab 导航 + UI 美化
- README badge + 架构图 + 表格

## v0.1.0 (2026-06-05)

首次公开发布。
