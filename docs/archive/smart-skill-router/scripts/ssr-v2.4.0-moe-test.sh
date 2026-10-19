#!/bin/bash
# SSR v2.4.0-MoE 重启后验证脚本
# 用法：重启 Hermes 后运行此脚本
# 更新: 2026-07-23 — 79条规则·16域（全功能域补完）

echo "=== SSR v2.4.0-MoE 重启验证 ==="
echo ""

# 1. 确认规则加载
echo "① 确认 A 层规则已加载（预期 79 条）："
grep '加载 A 层规则' ~/.hermes/logs/agent.log | tail -1
echo ""

# 2. 确认 auto-gen 状态
echo "② auto-gen 状态："
grep 'auto-gen' ~/.hermes/logs/agent.log | tail -1
echo ""

# 3. 确认备份存在
echo "③ 备份文件："
ls -la ~/.hermes/plugins/ssr/__init__.py.bak.0723_moe 2>/dev/null && echo "  ✅ __init__.py 备份" || echo "  ❌ 缺失"
ls -la ~/.hermes/plugins/ssr/a_rules.json.bak.0723_full 2>/dev/null && echo "  ✅ a_rules.json 全量备份" || echo "  ❌ 缺失"
echo ""

# 4. 域覆盖检查
echo "④ 域覆盖检查："
python3 -c "
import json
with open('$HOME/.hermes/plugins/ssr/a_rules.json') as f:
    rules = json.load(f)
from collections import Counter
domains = Counter(r.get('domain','(无)') for r in rules.values())
print(f'  总规则: {len(rules)} | 域: {len(domains)}')
for d, c in domains.most_common():
    print(f'    {d}: {c}')
expected = ['生图','视频','travel','学术','金融','github','agent','部署','writing','设计','音乐','通讯','storage','social','map','search']
missing = [d for d in expected if d not in domains]
if missing:
    print(f'  ❌ 缺失域: {missing}')
else:
    print(f'  ✅ 16 域全部覆盖')
"
echo ""

echo "========================================="
echo "  对着 Hermes 说，观察推荐结果："
echo "========================================="
echo ""
echo "  核心四测试："
echo "    '想出去转转'              → 行程规划"
echo "    '电影那种感觉'            → zy-cinematic-realism"
echo "    '帮我写代码'              → 不推"
echo "    '新疆玩几天拍照片'        → 旅行+生图 各1个（非5个）"
echo ""
echo "  跨域防污染："
echo "    '清理磁盘'                → 存储"
echo "    '做个短视频'              → 视频"
echo "    '股票行情分析'            → 金融"
echo "    '文献综述'                → 学术"
echo "    '部署到Vercel'            → 部署"
echo "    'Claude写代码'            → Agent"
echo "    '提交PR'                  → GitHub"
echo "    '发微信消息'              → 通讯"
echo ""
echo "  79条规则 · 16域 · 92 skill"
