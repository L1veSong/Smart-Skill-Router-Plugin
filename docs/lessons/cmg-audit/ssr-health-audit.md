# SSR 健康审计 — 命令与脚本模式

审计对象: `~/.hermes/plugins/ssr/`(插件本体)、`config.yaml` 的 `ssr:` 节、`agent.log / errors.log`。

## 1. 静态面
- `ls -la ~/.hermes/plugins/ssr/` — 版本、mtime、.bak 留存情况(a_rules.json / embeddings.json / model_scores.json 都在此)。
- `head -40 ~/.hermes/plugins/ssr/plugin.yaml` — name/version/hooks(pre_llm_call、post_llm_call)。
- `grep -A 45 "^ssr:" ~/.hermes/config.yaml` — b_layer.provider(main=复用主模型)、embedding(provider/model/timeout)、confidence_threshold、auto_gen_rules。
- Dashboard: `python3 ~/.hermes/plugins/ssr/dashboard.py` → 8768。

## 2. 运行态
- `grep "\[ssr\]" ~/.hermes/logs/agent.log | tail -45` — 注册行每回合重打(字段: skill 数 / 残骸 / A层 / emb / B层);另有 A 层命中、B 层命中、后台增量同步行。
- `grep -i ssr ~/.hermes/logs/errors.log | tail` — embedding 批失败/超时属网络抖动,重试机制已覆盖;连着多批才升级排查。
- 存活三态: A层规则>0=正常;仅 B 层命中=兜底;A层 0 且 B 层持续超时=形同虚设(立即降级手动匹配)。

## 3. 幽灵索引(核心检查,必做)
症状: 推荐出的 skill 名 `skill_view` 报 not found。判定与量化脚本要点(直跑 python3):
- 归档名集 = 逐个读 `~/.hermes/skills/.archive/*/SKILL.md` 的 frontmatter `name:`。
- embeddings.json 是 70MB 级 JSON——别猜结构,写 `find_map()` 递归找「值里含 embedding/desc 字段的字典」再取键。
- 集合运算用 `.intersection()/.difference()`,别在命令里写裸 ` & `(会被终端工具判成后台符而拒跑)。
- 差额 = 白名单外幽灵规模。

修复面: `_build_skill_md_index()` 的 rglob 循环内加 dot 段过滤——`skill_md.relative_to(base).parts[:-1]` 任一目录段以 `.` 开头即跳过(镜像 Hermes 加载器不加载隐藏目录的行为)。它是唯一的污染源函数: `_SKILL_MD_INDEX`、`_SKILL_INDEX`、`_get_skills_list()`、同步与匹配全部由它供给。

清理既有幽灵(流程模式):
1. 让插件模块能 import —— 用 `~/.hermes/hermes-agent/venv/bin/python3`(venv 里有全部依赖)。
2. 新进程重建「白名单索引」→ 剔除集 = embeddings 键集 − 白名单键集。
3. 防线: 白名单规模异常(低于存量 60%)或剔除量异常 → 中止人工复核。
4. `.bak.MMDDHHMM` 备份 embeddings.json → 原地删除剔除项 → 写回 → 重新加载复验。
5. 同名碰撞: 归档名与在役 skill 同名时白名单含该名,天然保留在役版本,别计入剔除量。

注: 修好扫描后,增量同步 `_sync_embeddings` 也会把幽灵自动清掉(current=`_SKILL_INDEX` 键 − indexed=embeddings 键),手动清理只是抢先落袋。

## 4. 修复配套(版本纪律)
版本链逐个 grep 同步: `__init__.py` docstring / `plugin.yaml`(version+description) / `README.md`(badge+版本表) / `dashboard.py` 头 / `test_ssr.py` 标题 / `CHANGELOG.md` 条目。改动前 `cp X X.bak.$(date +%m%d%H%M)`。
生效: 插件每回合随 Hermes 重载——下一回合自动生效;同回合内推荐仍跑旧模块。

## 5. 结构备注
- 双索引: `_SKILL_MD_INDEX`(名→路径,回退解析)与 `_SKILL_INDEX`(名→描述,同步/匹配),都经 `_get_skills_list()`;该函数首选 `hermes_cli.skills.registry`,但该导入路径已失效 → 实际永远走 fallback(`_build_skill_md_index()`)。修扫描规则=修这个函数;对接新加载器=待办。
- B 层日志「置信度不足 (x < 0.62),跳过 pre 注入,post 仍会展示」=正常门控行为,不是故障。
