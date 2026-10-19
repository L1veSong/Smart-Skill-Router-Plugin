# SSR 规则丢失：_cleanup_a_rules() 根因分析

> 日期：2026-07-24 | 耗时：3+ 小时反复排查 | 最终确认

## 一句话

**不是 golden 备份自动恢复。不是 auto_gen 垃圾泛滥。** 根因只有一个：`__init__.py` 的 `_cleanup_a_rules()` 函数在每次 Hermes 启动时静默删除"不合格"规则，然后覆盖 `a_rules.json`。

## 三条清理路径（`__init__.py`）

| 路径 | 代码行 | 触发条件 | 效果 |
|------|------|------|------|
| 死引用清理 | L954-968 | skills 数组中任一 name 不在磁盘 `_SKILL_INDEX` 中 | 整条规则删除 |
| keywords 死引用 | L973-987 | keywords 数组全部不匹配任何已安装 skill | 整条规则删除 |
| 空规则删除 | L997-1000 | skills 和 keywords 都为空 | 整条规则删除 |
| 上限淘汰 | L1006-1040 | 规则数超过 `a_rules_max`（默认100） | 按质量评分砍最低分 |

## config.yaml 上限淘汰（真凶）

本机配置 `ssr.a_rules_max: 60`。加到 202 条后重启 → 自动砍回 60 条。**这是 200+→142 的直接原因，不是清理逻辑 bug。**

## 五个代码补丁（已应用 2026-07-24）

**Hermes 升级或插件重装会覆盖，需重新验证。**

| 补丁 | 位置 | 内容 |
|------|------|------|
| 死引用清理跳过 manual | L955 后 | `if rule.get("source") == "manual": continue` |
| keywords 死引用跳过 manual | L975 后 | 同上 |
| 空规则删除跳过 manual | L999 | `if p in _A_RULES and _A_RULES[p].get("source") != "manual"` |
| 热删除跳过 manual | L1379 | `if rule.get("source") == "manual": continue` |
| config.yaml 上限 | `ssr.a_rules_max` | 60 → 300 |

## 免疫机制

规则必须带 `"source": "manual"`——三条清理路径都跳过。没有这个标记的规则在无人知晓的情况下被删除。

```json
{
  "(?i)(关键词|关键词)": {
    "source": "manual",
    "skills": [{"name": "skill-name", "phase": "CREATE"}]
  }
}
```

## 排查命令

```bash
# 检查上限
grep a_rules_max ~/.hermes/config.yaml

# 当前规则数
python3 -c "import json; print(len(json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json'))))"

# manual 占比
python3 -c "
import json
r=json.load(open('$HOME/.hermes/plugins/ssr/a_rules.json'))
m=sum(1 for v in r.values() if v.get('source')=='manual')
print(f'{m}/{len(r)} manual')
"

# 检查 4 个补丁存活（期望：4）
grep -c "if rule.get.*source.*manual.*continue" ~/.hermes/plugins/ssr/__init__.py

# 检查空规则补丁（期望：1）
grep -c "source.*!=.*manual" ~/.hermes/plugins/ssr/__init__.py
```

## 实战案例

1. **改 skill 名**：`fantasy-oriental-editorial-poster` → `oriental-editorial-poster`。旧名规则 skills 引用失效 → 死引用清理 → 整条删除。
2. **a_rules_max: 60**：加 40 条后重启 → 砍回 60 条。

## 已知坑点

- `execute_code` 中的 Python 字符串转义会导致补丁写入失败——用 `patch` 工具而非 `execute_code`
- 不要为每次规则修改创建备份文件（会累积 10+ 个互踩的备份）
- 不要在全量读 `__init__.py` 之前写——2622 行读完再确定修改点
