# SSR 全量审计 (2026-06-23) — 经验总结

## 审计触发条件
- 大版本升级后 (如 v2.0→v2.1)
- 对外发布前
- 用户说"审计"/"检查"/"全量grep"

## 必检项

### 1. 版本号一致性
```bash
grep -rn 'v[0-9]\.[0-9]\.[0-9]' __init__.py plugin.yaml CHANGELOG.md README.md dashboard.py test_ssr.py
```
所有文件版本号必须一致。含 init.py 中的 JSON 字符串格式（可能不带 v 前缀）。

### 2. 硬编码模型名/端点
```bash
grep -rnIE 'bge|qwen|siliconflow|api\.siliconflow|1024维|4096维' . --exclude=CHANGELOG.md --exclude=model_scores.json --exclude=embeddings.json
```
对外文件零残留。CHANGELOG 和 model_scores.json 中的历史/配置引用除外。

### 3. benchmark 数据格式同步
格式变更时 (如 skills→keywords)，grep 所有读取方确认字段名一致：
```bash
grep -rn 'rule.get.*skills\|rule\.get.*keywords' tests/
```

### 4. 死文件清理
```bash
find . -name '*.bak*' | wc -l          # 应为0
find . -name '*_v3*' -o -name '*.old'  # 代码不使用即删
```
⚠️ 异常: dashboard.html 无 git 版本控制，改前必须 `cp dashboard.html dashboard.html.bak.$(date +%m%d%H%M)`

### 5. CHANGELOG 声称 vs 代码实际
逐条核对 CHANGELOG 中声明的功能在 __init__.py 中实际存在：
```bash
grep 'gate_prompt\|gate prompt' __init__.py          # Gate prompt 配置化？
grep 'llm_screen\|_llm_screen' __init__.py           # llm_screen 开关？
grep 'word_not_found\|word_not' a_rules.json          # regex 覆盖？
```
三条全空 → 不能发布。正确顺序：代码 → 验证 → CHANGELOG → 版本号 → 打包。

## 本次审计结果摘要

| 类别 | 发现 | 修复 |
|------|------|------|
| 版本号 | README badge 2.0.0 vs plugin.yaml 2.1.0 | 统一 2.1.0 |
| 日期 | __init__.py 06-22 vs CHANGELOG 06-23 | 统一 06-23 |
| 硬编码 | docstring 写 bge-m3/1024维 | 改为通用描述 |
| benchmark | skills→keywords 格式不同步 | 全量 grep 同步 |
| dead refs | a_rules_v3.json 代码不使用 | 删除 |
| bak files | 36 个 | 全删（⚠️ 含 dashboard.html 备份） |
| config 示例 | 缺 v2.1 新 key | 补 intent_gate/meta_detection/noise_filter/display |
