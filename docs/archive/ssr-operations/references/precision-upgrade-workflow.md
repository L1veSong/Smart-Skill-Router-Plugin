# Phase 3 精准升级工作流（2026-06-09）

> SSR v0.5.x → 四任务零风险升级路径

## 背景

precision-upgrade/task_plan.md 定义了 Phase 3-6 共 10 个 task。经评估，4 个零风险可推，4 个缺数据/高风险暂缓，2 个需回归测试已跳过。

## 升级任务（本次完成）

| Task | 文件 | 改动 | 风险 |
|------|------|------|:--:|
| 3.1 描述富化 | `__init__.py:_get_skill_info()` | 正文3段散文提取，跳过表格/代码块/标题 | ✅ 零 |
| 3.2 中文扩展 | `__init__.py:_expand_chinese_query()` | 14域中英映射，embedding路径前调用 | ✅ 零 |
| 4.2 命中日志 | `__init__.py:_SESSION_STATS` | 会话统计，每10次调用输出 | ✅ 零 |
| 4.1 Dashboard | `dashboard.py` + `.html` | `/api/stats` + 4格统计面板 | ✅ 零 |

## 标准工作流

### 1. 备份

```bash
cp __init__.py __init__.py.bak.$(date +%Y%m%d_%H%M)
cp a_rules.json a_rules.json.bak.$(date +%Y%m%d_%H%M)
cp plugin.yaml plugin.yaml.bak.$(date +%Y%m%d_%H%M)
```

### 2. 改代码

- 用 `patch` 做定点修改（不用 `replace_all` 对 Python 源码）
- 改后立即 `python3 -m py_compile __init__.py` 语法检查
- Dashboard HTML 大改用 `write_file`（不用 `patch`，压缩单行易碎）

### 3. 删旧索引 + 重启

```bash
rm embeddings.json          # 强制全量重建
# 然后重启 Hermes
```

### 4. 验证

```bash
# ① 注册日志
grep '插件注册完成' agent.log | tail -1
# 期望: skill: ~296 | emb: ~296 | A层: 100

# ② 命中率统计
grep '会话统计' agent.log | tail -3

# ③ Dashboard
curl -s http://localhost:8766/api/stats | python3 -m json.tool

# ④ 测试消息（在 Hermes 中发送后查日志）
grep 'A 层命中\|B 层命中' agent.log | tail -5
```

## 跳过的任务及理由

| Task | 理由 |
|------|------|
| 3.3 混合权重 | keyword-first 已实现，显式加权收益极小 |
| 4.3 误报降权 | 需要大量使用数据，当前样本不足 |
| 5.1 任务切换冷却 | 60s 固定冷却可用，锦上添花 |
| 5.2 分阶段冷却 | 复杂，当前够用 |
| 6.1 文件监听 | macOS fsevents 坑多 |
| 6.2 热更新索引 | 索引损坏风险，启动时 18s 重建可接受 |

## 关键教训

### 描述富化必须过滤非散文内容

v1 将 markdown 表格行当段落收集 → bge-m3 收到无用信号。必须跳过 `|`（表格）、` ``` `（代码块）、`#`（标题）、`>`（引用）。

### 中文扩展域覆盖要完整

v1 调试域只有「报错/异常」→ "KeyError" 不匹配。Python 用户常用错误名（KeyError, Traceback, TypeError）必须显式加入。

### Dashboard HTML 大改用 write_file

`dashboard.html` 压缩单行，用 `patch` 改单处可行但两次以上累积风险高。涉及新增函数 → 用 `read_file` + 外部编辑 + `write_file` 一次性写入。
