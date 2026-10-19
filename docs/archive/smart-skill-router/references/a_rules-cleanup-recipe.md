# a_rules.json 手动清理菜谱

> 实战于 2026-06-14: 61→6 条, 56 条 auto-gen 单字噪声清空, GREEN 5/5

## 何时需要

- a_rules.json 超过 20 条且大部分是 `source: "auto-gen"` 的单字匹配
- 日志频繁出现与当前话题无关的 [SSR] 推荐
- 想从头开始积累高质量手动规则

## 完整菜谱

### Step 1: 备份

```bash
cp ~/.hermes/plugins/ssr/a_rules.json ~/.hermes/plugins/ssr/a_rules.json.bak.$(date +%Y%m%d_%H%M%S)
```

### Step 2: 决定保留什么

标准：
- ✅ 保留: `source: "manual"` 且 keywords 是完整中文/英文短语
- ✅ 保留: auto-gen 中高频命中（hits > 50）且与目标领域精准匹配的
- ❌ 删除: `source: "auto-gen"` 且 keywords 是单个英文单词（work, run, test...）
- ❌ 删除: 命中 = 0 且 30 天以上的冷规则

### Step 3: 编辑 a_rules.json

手动编辑，或 Python 脚本辅助:

```python
import json

with open('a_rules.json') as f:
    rules = json.load(f)

# 只保留 manual 来源
clean = {k: v for k, v in rules.items() if v.get('source') == 'manual'}
print(f'保留: {len(clean)} / 原: {len(rules)}')

with open('a_rules.json', 'w') as f:
    json.dump(clean, f, indent=2, ensure_ascii=False)
```

### Step 4: 关闭 auto-gen

```bash
hermes config set ssr.auto_gen_rules false
```

### Step 5: 重启 Hermes

完全退出再开。`/new` 不够——SSR plugin 在 `register()` 时读取 a_rules.json。

### Step 6: 验证

```bash
# 6a. 检查日志
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# 预期: A层: 6+0（即6条手动 + 0条auto-gen）

# 6b. GREEN 基准
python3 ~/.hermes/skills/software-development/canon-mnemonic-guard/scripts/ssr-green-benchmark.py
# 预期: 5/5 或 4/5（学术写作场景可能纯靠 B 层兜底）

# 6c. 生产验证
# 发几条消息，看 [SSR] 推荐是否与当前话题相关
```

## 恢复流程

如果清错了:

```bash
cp ~/.hermes/plugins/ssr/a_rules.json.bak ~/.hermes/plugins/ssr/a_rules.json
# 重启 Hermes
```

## 附: 本案例保留的 6 条规则

| 正则 | 推荐 Skill | 命中 | 
|------|-----------|:--:|
| 写.*代码|模块|接口|服务 | brainstorming, TDD, planning-with-files | 4 |
| ASCII\|字符画\|cowsay\|figlet | ascii-art | 12 |
| 股票\|均线\|MACD\|KDJ\|走势\|A股\|期货 | technical-analysis, tushare-finance | 135 |
| 规划\|方案\|架构\|设计.*系统\|技术选型 | brainstorming, writing-plans, idea-foundry | 8 |
| debug\|修复\|报.*错\|bug\|KeyError\|Traceback | diagnose, systematic-debugging | 143 |
| UI\|界面\|设计.*(导航|页面|网页|布局|网站) | brainstorming, ui-ux-pro-max, popular-web-designs | 0 |
