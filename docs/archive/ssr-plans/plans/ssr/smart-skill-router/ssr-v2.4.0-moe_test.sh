#!/bin/bash
# SSR v2.4.0-MoE 重启后验证脚本
# 用法：重启 Hermes 后，对着它说这些话，看 SSR 推什么

echo "=== SSR v2.4.0-MoE 重启验证 ==="
echo ""

# 1. 确认规则加载
echo "① 确认 36 条规则已加载："
grep '加载 A 层规则' ~/.hermes/logs/agent.log | tail -1
echo ""

# 2. 确认版本
echo "② 确认 MoE 版本："
grep 'v2.4.0-MoE' ~/.hermes/logs/agent.log | tail -1 || echo "  未出现 → 代码可能未生效"
echo ""

# 3. 确认备份存在
echo "③ 备份文件："
ls -la ~/.hermes/plugins/ssr/__init__.py.bak.0723_moe 2>/dev/null && echo "  ✅" || echo "  ❌ 缺失"
ls -la ~/.hermes/plugins/ssr/a_rules.json.bak.0723_full 2>/dev/null && echo "  ✅" || echo "  ❌ 缺失"
echo ""

echo "========================================="
echo "  对着 Hermes 说以下话，观察推荐结果："
echo "========================================="
echo ""
echo "  旅行域："
echo "    '想出去转转'          → 行程规划"
echo "    '飞过去多少钱'        → 机票搜索"  
echo "    '那边吃啥'            → 美食攻略"
echo "    '冷不冷'              → 天气"
echo ""
echo "  生图域："
echo "    '电影那种感觉的画面'  → zy-cinematic-realism"
echo "    '帮我做个海报'        → culture-fragment"
echo "    '中国风的设计'        → oriental-editorial"
echo ""
echo "  写作域："
echo "    '帮我写一篇文章'      → khazix-writer"
echo "    '帮我写代码'          → 不推（正确排除）"
echo ""
echo "  存储域："
echo "    '清理磁盘'            → storage-analyzer"
echo ""
echo "  跨域："
echo "    '新疆玩几天拍照片'    → 旅行+生图 各1个（非5个）"
