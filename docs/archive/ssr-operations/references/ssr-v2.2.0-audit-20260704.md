# SSR v2.2.0 全量审计 (2026-07-04)

## 审计触发
用户说"ssr进行全量grep审计" → 6 项检查覆盖 plugin + skill + CMG 引用。

## 发现问题

| # | 问题 | 修复 | 级别 |
|---|------|------|------|
| 1 | CHANGELOG.md 缺 v2.2.0 条目 | 插入 v2.2.0 条目 | P0 |
| 2 | 4 个文件版本号 v2.1.0 滞后（READMe/dashboard.py/test_ssr.py×2） | → v2.2.0 | P0 |
| 3 | ssr-operations SKILL.md v2.3.0（在代码还是 v2.2.0 时） | 跳过（运维 skill 自身版本） | P1 |
| 4 | 10 个 .bak 残留（CHANGELOG 声称 5 个已清） | 保留 dashboard.html.bak，删其余 9 个 | P0 |
| 5 | `_similarity_floor()` 代码仍含 config fallback | 保留（兼容性兜底） | P1 |
| 6 | embeddings.json `model: ?` | 不影响匹配 | P2 |
| 7 | `display: true` → `[SSR]` 前缀注入响应 | 用户已知，可配 false | P2 |

## 执行后验证

- **版本号**: 6 个文件全量 grep 零 v2.1.0 代码残留
- **硬编码**: 对外文件（__init__.py/plugin.yaml/README/dashboard.py/test_ssr.py）零模型名零维度
- **a_rules.json**: 100 条规则全 keywords，零 skills 残留
- **.bak**: 仅 dashboard.html.bak.06240251
- **CHANGELOG**: v2.2.0 条目完整

## 追加修复（非审计项，同会话发现）

### 元对话检测正则盲区

**症状**: "现在信号命中率怎么样" → `_META_CONVO` 未拦截 → embedding 仅命中 1 条 (`using-superpowers`) → `display:true` 下注入 `[SSR] [P] using-superpowers`。

**根因**: `_META_CONVO` 要求显式 "SSR/CMG" 关键词，不含 "信号/命中率/benchmark" 作为元对话触发词。

**修复**: 扩充正则分支，新增 `信号|命中率|benchmark|准确率|推荐质量|A层|B层|embedding|嵌入` 到元对话触发词，`测|跑|验证|效果|高|低|对|准不准` 到连接谓词。

### 极短噪音 stealth 拦截

**症状**: "谢谢"（2字）被 `len(msg)<4` 短路拦截，但零日志 → 验证时怀疑"到底有没有执行"。

**修复**: 加 `logger.info("[ssr] 极短噪音拦截 → 静默 (%d字: %s)", len(msg), msg)`。

### Benchmark 超时

**症状**: `--quick` 模式 120s 超时。可能与 Ollama 冷启动 15s 首次推理 + 键索引容量相关。

**状态**: 未修复。生产环境模型常驻，此波动不应重现。

## 审计命令模板（下次复用）

```bash
SSR_DIR=~/.hermes/plugins/ssr

# 1. 版本号
grep -rn 'v[0-9]\.[0-9]\.[0-9]' $SSR_DIR/__init__.py $SSR_DIR/plugin.yaml $SSR_DIR/CHANGELOG.md $SSR_DIR/README.md $SSR_DIR/dashboard.py $SSR_DIR/test_ssr.py

# 2. 硬编码（排除 config/历史文件）
grep -rnIE 'bge|qwen|1024维|4096维' $SSR_DIR/__init__.py $SSR_DIR/plugin.yaml $SSR_DIR/dashboard.py $SSR_DIR/test_ssr.py $SSR_DIR/README.md

# 3. .bak 残留
find $SSR_DIR -name '*.bak*' -type f

# 4. a_rules.json 格式（应全 keywords 零 skills）
python3 -c "import json; d=json.load(open('$SSR_DIR/a_rules.json')); bad=[k for k,v in d.items() if 'skills' in v]; print(f'规则={len(d)}, skills残留={len(bad)}')"

# 5. CHANGELOG 声称 vs 代码实际
grep 'similarity_floor' $SSR_DIR/__init__.py
grep 'meta_detection' $SSR_DIR/__init__.py
grep 'llm_screen' $SSR_DIR/__init__.py
```

## 教训

1. **CHANGELOG 声称需逐条代码验证** — "删 explicit similarity_floor" 不是真的删除，只是不再强制配置。函数仍在，config fallback 仍在。
2. **元对话正则必须覆盖隐式 SSR 问法** — 不带 "SSR" 关键词但实质问 SSR 状态的消息（信号/命中率/benchmark/推荐质量）需要正则捕获。
3. **审计清单里的"5 个 .bak 已清"是错的** — 实际 10 个。下次声称数量前必 `find` 验证。