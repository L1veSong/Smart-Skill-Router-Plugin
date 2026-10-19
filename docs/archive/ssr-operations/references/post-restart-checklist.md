# SSR 重启后快速诊断

> 每次 Hermes 重启后执行，确认 SSR 存活且功能正常。
> 最后更新: 2026-07-22，基于 v2.3.x 实际诊断流程。

## 快速诊断（30 秒三板斧）

### 板斧 1：确认注册

```bash
grep -i 'ssr' ~/.hermes/logs/agent.log | tail -5
```

有 `hermes_plugins.ssr` 行 → 已注册。
若无任何 SSR 日志 → 检查 `grep ssr ~/.hermes/config.yaml`（enabled）、`ls ~/.hermes/plugins/ssr/__init__.py`（文件存在）。

### 板斧 2：确认功能

```bash
grep -i 'ssr' ~/.hermes/logs/agent.log | grep -v '元对话检测' | tail -5
```

**正常：** A 层命中、B 层命中、增量同步、embedding 相关日志。
**只有「元对话检测 → 静默」：** ⚠️ 这是 SSR 的正常行为——你问「SSR 状态如何」时，SSR 识别为元对话并主动静默。**不是挂了。** 换一条真实任务（如「帮我写个脚本」）再测。
**完全无日志：** ❌ SSR 未加载或未注册。

### 板斧 3：确认配置

```bash
grep -A 20 '^ssr:' ~/.hermes/config.yaml
```

验证 `enabled: true`、`display: true/false`、`b_layer.provider`、`embedding.provider`。

## 元对话误判排查

SSR v2.1+ 内置元对话检测（`_META_CONVO` 正则）。以下问句会被静默：

- 「SSR 状态如何」「SSR 加载了吗」「插件工作正常吗」
- 「A 层命中率怎么样」「推荐准确吗」
- 「benchmark 测过吗」「信号质量如何」

**验证方法：** 说一条真实任务（如「帮我写个 Python 脚本」），若 SSR 正常推荐 → 之前的静默是元对话检测，不是故障。

> 详细正则见 `references/ssr-meta-convo-regex-audit.md`

## 三板斧全过但用户说「没推荐」？

1. 让用户发一条真实任务（非问 SSR 本身），再查日志
2. 检查 `display: true`（false 则匹配但不输出推荐）
3. 跑 GREEN baseline（见 `../software-development/canon-mnemonic-guard/references/ssr-green-benchmark-v2.md`）
