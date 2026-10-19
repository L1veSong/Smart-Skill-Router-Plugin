# v2.4.0-MoE 升级：域名规则丢失与恢复

> 日期: 2026-07-23
> 触发: SSR 重启验证发现生图域 10 条规则完全丢失

## 症状

v2.4.0-MoE 重构后，A 层规则从 26 条（全量备份）降至 19 条（当前），生图域（生图/摄影/海报/电影）10 条规则全部缺失。

测试用例验证：
- "电影那种感觉" → ✗ 无匹配（预期 zy-cinematic-realism）
- "新疆玩几天拍照片" → 仅旅行命中，缺摄影部分

## 根因

v2.4.0-MoE 新增了 `domain` 字段机制和 `_route_domains()` 路由层。重构时只重写了 4 个域（travel/writing/storage/map），旧版 a_rules.json 中的生图/金融/debug 域规则未迁移——这些旧规则没有 `domain` 字段，在 MoE 路由中无法被正确激活。

## 升级后必检清单

每次 SSR 大版本升级后，必须执行：

```bash
# 1. 运行验证脚本
bash ~/.hermes/plans/ssr/smart-skill-router/ssr-v2.4.0-moe_test.sh

# 2. 检查域名覆盖
python3 -c "
import json
with open('~/.hermes/plugins/ssr/a_rules.json') as f:
    rules = json.load(f)
domains = set(r.get('domain','') for r in rules.values())
print(f'域覆盖: {sorted(domains)}')
print(f'预期: [生图, map, storage, travel, writing]')
"

# 3. 测试核心用例
#   "电影那种感觉" → 应有 zy-cinematic-realism
#   "想出去转转"   → 应有 travel-plan-request
#   "帮我写代码"   → 应无匹配（正确排除）
#   "新疆玩几天拍照片" → 应有 travel + 摄影各 1 个
```

## 恢复步骤

从全量备份恢复缺失域规则：

```python
import json

# 加载当前规则和全量备份
with open('a_rules.json') as f:
    current = json.load(f)
with open('a_rules.json.bak.0723_full') as f:
    full = json.load(f)

# 找出备份中有但当前缺失的规则
missing = {k: v for k, v in full.items() if k not in current}

# 为缺失规则补 domain 字段
DOMAIN_MAP = {
    "生图": ["电影", "cinematic", "海报", "poster", "写真", "摄影", "徕卡", "哈苏",
             "理光", "leica", "故事板", "storyboard", "关键帧", "keyframe",
             "中国风", "国风", "oriental", "分镜", "人像", "肖像"],
    "金融": ["股票", "均线", "MACD", "KDJ", "RSI", "期货", "A股"],
    "debug": ["debug", "报错", "bug", "调试"],
}

for pattern, rule in missing.items():
    for domain, keywords in DOMAIN_MAP.items():
        if any(kw in pattern for kw in keywords):
            rule["domain"] = domain
            break

# 合并写入（先备份！）
import shutil, time
shutil.copy('a_rules.json', f'a_rules.json.bak.{time.strftime("%m%d%H%M")}')
merged = {**current, **missing}
with open('a_rules.json', 'w') as f:
    json.dump(merged, f, ensure_ascii=False, indent=2)

print(f"恢复完成: {len(current)} → {len(merged)} 条规则")
```

**注意：** 恢复后必须重启 Hermes 使 SSR 重新加载规则。

## 预防

- SSR 升级时保留旧版 a_rules.json 全量备份（已有）
- 升级脚本应自动对比旧版规则列表，标记缺失域
- MoE `_route_domains()` 的 `DOMAIN_STEMS` 需同步维护——新增域时两端都要更新
