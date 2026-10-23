# SSR v0.6.2 → v0.6.3 迭代计划

> **目标：** 修复 echo bug + 补齐发布债务
> **版本：** v1.0 | **状态：** ✅ 已完成 | **创建：** 2026-06-14 | **完成：** 2026-06-14 18:08

---

## 当前基线

| 指标 | 值 |
|------|-----|
| GREEN 基准 | 5/5 ✅ |
| A层规则 | 6 条全手动，零噪声 ✅ |
| auto-gen | 已关闭 ✅ |
| B层兜底 | 正常（bge-m3, 370 skill） ✅ |
| 备份 | ~/.hermes/backups/ssr-v062-20260614_180643/ ✅ |

## 版本号债务

| 文件 | 当前 | 目标 |
|------|------|------|
| `__init__.py` 头部 | v0.6.2 ✅ | v0.6.3 |
| `plugin.yaml` | **v0.3.0** ❌ | v0.6.3 |
| `CHANGELOG.md` | v0.6.1 ❌ | 补 v0.6.2 + v0.6.3 |

---

## Task 1: 修复 SSR echo bug (F8) ⭐ P0

### 症状

B 层命中时，用户看到的是：
```
[SSR] 建议加载:\n
```
skill 名完全不显示。`\n` 是字面量反斜杠-n，不是换行。

### 根因

`~/.hermes/plugins/ssr/__init__.py` L1424-1427：

```python
# ❌ 当前（v0.6.2）
body = "\\n".join(lines)           # L1424 — 字面量 \n 拼接
return f"{prefix}\\\\n{body}"        # L1427 — f-string 中 \\\\n = 字面量 \n
```

Python 中 `"\\n"` 是两个字面字符（反斜杠+n），`"\\n"` 才是换行。f-string 中的 `\\\\n` 同理。

### 修复

```python
# ✅ 正确
body = "\n".join(lines)            # 实际换行拼接
return f"{prefix}\n{body}"         # 实际换行分隔
```

L1426 enforce 模式同修：
```python
# ❌ 当前
return f"{prefix} SSR 强制加载:\\\\n{body}\\\\n以上技能..."
# ✅ 
return f"{prefix} SSR 强制加载:\n{body}\n以上技能..."
```

### 影响范围

| 文件 | 行 | 改动 |
|------|-----|------|
| `__init__.py` | L1424 | `"\\n"` → `"\n"` |
| `__init__.py` | L1426 | `\\\\n` → `\n` (×2) |
| `__init__.py` | L1427 | `\\\\n` → `\n` |

### 验证

重启 Hermes → 发消息触发 B 层命中 → 检查 agent.log：
```bash
grep 'SSR.*建议加载' ~/.hermes/logs/agent.log | tail -3
```
应显示完整 skill 名列表，不再出现字面量 `\n`。

---

## Task 2: plugin.yaml 版本号同步

### 症状

`plugin.yaml` version 字段仍为 `0.3.0`，滞后 3 个大版本。

### 修复

```yaml
# ❌ 当前
version: 0.3.0
# ✅ 
version: 0.6.3
```

### 验证

```bash
grep 'version:' ~/.hermes/plugins/ssr/plugin.yaml
# 预期: version: 0.6.3
```

---

## Task 3: CHANGELOG 补齐

### 补 v0.6.2 条目

| 改动 | 说明 |
|------|------|
| 诊断日志 | register() 3 行 logger.info（加载/清理后/净化后规则数） |
| miss 日志 | miss 路径补 logger.info（A层规则数 + B层后端 + 调用次数） |
| 空覆盖保护 | _save_a_rules 检测空覆盖→自动备份到 `.json.bak` |
| 损坏容灾 | _load_a_rules 损坏时备份到 `.json.corrupted` |
| 降噪完成 | a_rules.json 61→6 条全手动，auto-gen 关闭，zero 噪声 |

### 补 v0.6.3 条目

| 改动 | 说明 |
|------|------|
| F8 修复 | echo bug：`\\n` 字面量→实际换行，skill 名正常显示 |
| 版本同步 | plugin.yaml 0.3.0→0.6.3 |

---

## Task 4（延期）: 降噪 Task 2/3/4

> 从 noise-reduction plan 延期。6 条规则时不需要，等规则增长到 20+ 再评估。

| Task | 内容 | 触发条件 |
|------|------|---------|
| Task 2 | Embedding 语义门控 | A层规则 ≥20 时重新评估 |
| Task 3 | 中文扩展域匹配度 | 新增中文域但 B 层兜底频繁时 |
| Task 4 | 提高 similarity_floor | bge-m3 噪音困扰用户时 |

---

## 实施顺序

```
Task 1 (10 min) → echo bug 修复
    ↓ 重启验证
Task 2 (1 min)  → plugin.yaml 版本号
Task 3 (5 min)  → CHANGELOG 补全
    ↓ 全量版本号 grep 验证
备份 → 稳定版标记
```

---

> **记录时间：** 2026-06-14 18:06
> 
> **基线版本：** v0.6.2（功能稳定，发布债务待补）
> 
> **发布版本：** v0.6.3（P0 bugfix + 债务清账）
