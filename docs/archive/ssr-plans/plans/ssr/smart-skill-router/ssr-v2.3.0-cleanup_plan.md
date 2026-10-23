# SSR v2.3.0 大修计划

> 执行时间: 2026-07-23
> 触发: `a_rules.json` 含 6789 条垃圾规则（B层Ollama超时→自动学习泛滥）
> 状态: ✅ 已完成

---

## 诊断

### 三个测试命令的正确写法

| 测试意图 | 错误命令 | 正确命令 | 原因 |
|---------|---------|---------|------|
| 规则数 (7) | `a_rules.json` | `a_rules.local.json` | a_rules.json 含 auto 规则 6789 条，手工规则在 local.json |
| embedding (438) | ✅ 正确 | `grep 'embedding 索引' agent.log` | 423，差15个可接受 |
| PROMOTE_THRESHOLD (3) | grep agent.log | grep `__init__.py` | 阈值是 Python 常量，不在日志里 |

### 根因链

```
B层 Ollama 超时
  → 每次超时返回垃圾文本
  → PROMOTE_THRESHOLD=3 → 垃圾频繁升级到 A 层
  → 6789 条单英文词规则 ('skill','work','time'...) 堆积
  → 手动拉高 PROMOTE_THRESHOLD=999999 暂停自学习
  → 垃圾已写入磁盘，_cleanup_a_rules 有两个 bug:
    1. 空 phase 规则不删除（"保留作为意图信号"→垃圾保留）
    2. 淘汰按 hits 升序→垃圾 hits 最高反而不被淘汰
```

---

## 改动清单

### A. 清空垃圾规则 — a_rules.json 重建

**前:** 6792 条（manual:3, auto:6789）  
**后:** 10 条（manual:3 + local.json:7 合并）

备份: `a_rules.json.bak.07230006` (1,017,013 bytes)  
新文件: 3,818 bytes

### B. PROMOTE_THRESHOLD: 999999 → 3

**文件:** `__init__.py` L64-67

```python
# 前
PROMOTE_THRESHOLD = 999999

# 后
PROMOTE_THRESHOLD = 3
```

自学习恢复。配合垃圾检测（改动C），新规则不会被污染。

### C. _cleanup_a_rules 新增垃圾检测

**文件:** `__init__.py` L801-878 → 重构为 3 阶段

**阶段 1 — 垃圾检测（新增）:**
- 单英文词 + stop words → 删除
- 太短模式 (< 4 chars) → 删除
- 空 phase 且无 skills 且无 keywords → 删除
- manual 规则不参与垃圾检测

**阶段 2 — 原有清理:**
- 死引用清理（指向已卸载 skill）
- TTL 过期清理
- v2.3.0 改动: 空规则不再保留，直接删除

**阶段 3 — 上限淘汰（修复方向）:**
- 前: `sorted(hits, 升序)` → 删最低 hits → 垃圾 hits 最高 → 不被淘汰 ❌
- 后: `sorted(质量评分, 升序)` → 删最低质量 → manual 保护 → 垃圾先被删 ✅

质量评分公式:
```
manual?         +1000
有 phase?       +100 × N
有 skills?      +10 × N
有关键词?       +5 × N
pattern 长度    +min(len, 50)
hits            +min(hits, 100) × 0.01
```

### D. 版本号 v2.2.0 → v2.3.0

`__init__.py` 文件头 CHANGELOG 更新。

---

## 验证清单

重启 Hermes 后检查：

```bash
# 1. a_rules.json 干净（10条，不是6792）
python3 -c "import json; r=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json')); print(len(r))"
# → 10

# 2. PROMOTE_THRESHOLD 已恢复
grep 'PROMOTE_THRESHOLD = ' ~/.hermes/plugins/ssr/__init__.py
# → PROMOTE_THRESHOLD = 3

# 3. 启动日志无异常
grep 'ssr.*垃圾\|ssr.*注册完成' ~/.hermes/logs/agent.log | tail -3
# → 应显示垃圾清理 0 条 + 注册完成

# 4. embedding 索引正常
grep 'embedding 索引' ~/.hermes/logs/agent.log | tail -1
# → 应接近 438

# 5. 不再生成垃圾规则（观察 3-5 轮对话后）
grep 'B→A 升级触发' ~/.hermes/logs/agent.log | tail -5
# → 新升级的规则应有实际 phase，不是空 phase
```

---

## 回滚方案

如需回滚：

```bash
cd ~/.hermes/plugins/ssr
cp __init__.py.bak.07230006 __init__.py
cp a_rules.json.bak.07230006 a_rules.json
# 重启 Hermes
```

---

## 相关

- CMG 规则: ban_act_before_verify, ban_075 (写前备份)
- 备份时间戳: 07230006 = 7月23日 00:06
- 上一版本: v2.2.0 (embedding 阈值无极校准)
