# Dashboard Benchmark 修复记录

## 日期
2026-06-21

## 问题
Dashboard 模型面板 "Run Benchmark" 按钮始终显示「索引未建」。

## 根因：三重 bug

### Bug 1 — 测试文件路径写死

```python
# ❌ 旧
test_path = Path(__file__).resolve().parent / "test_ssr.py"
# 解析: ~/.hermes/plugins/ssr/test_ssr.py — 不存在

# ✅ 新
test_path = Path.home() / ".hermes/skills/software-development/smart-skill-router/tests/ssr_tdd_baseline_test.py"
```

### Bug 2 — 解析正则匹配旧格式

旧测试输出包含:
```
GREEN 关键词覆盖率 5/5
Embedding GREEN 覆盖率 5/5
✅ GREEN·场景名 命中 [skill1, skill2]
```

当前测试输出格式:
```
📊 bge-large-zh-v1.5:  5/5 | nomic: 5/5 | A层: 5/5
📊 Embedding 贡献: bge-large-zh-v1.5 +0 | nomic +0
场景 1: 帮我设计一个响应式导航栏
A层命中: ['brainstorming', 'popular-web-designs', 'ui-ux-pro-max'] ✅
```

新旧格式完全不同，旧正则零匹配。

### Bug 3 — Embedding 分数被 RED 行污染

```python
# ❌ 通用正则匹配到 RED 行
m = re.search(r"\S+:\s+(\d+)/5", output)
# output 中第一处匹配: "🔴 RED:    0/5" → emb_score = "0/5"

# ✅ 专属正则
m = re.search(r"bge-[\w.-]+:\s+(\d+)/5", output)
# 只匹配 bge-large-zh-v1.5: 5/5 → emb_score = "5/5"
```

## 修复后的解析正则

```python
# A 层分数
m = re.search(r"A层:\s*(\d+)/5", output)

# Embedding 分数（专属）
m = re.search(r"bge-[\w.-]+:\s+(\d+)/5", output)

# 场景解析（DOTALL 跨行）
scene_re = re.compile(
    r"场景 (\d+): (.+?)\n.*?A层命中: \[(.+?)\] (✅|❌)",
    re.DOTALL
)
```

## 危险操作教训

修复时用 `py = py[:start_idx] + new_func + py[end_idx:]` 替换整个函数体，误删了紧跟其后的 `class SSRHandler` 和 `if __name__` 块。

**改前必须 `cp` 备份。** Dashboard 有 3 个 `.bak` 文件作为救命稻草。

## 当前状态

- 测试脚本: 已改为读 config.yaml，不再硬编码模型名
- Dashboard benchmark API: 已修复，返回正确数据
- 测试验证: TDD 5/5 GREEN，benchmark 返回 5 场景全部命中
