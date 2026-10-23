#!/bin/bash
# SSR 完整性检查脚本 — 每次启动/更新后验证 5 个保护点
set -e

SSR_DIR="$HOME/.hermes/plugins/ssr"
CONFIG="$HOME/.hermes/config.yaml"
RULES="$SSR_DIR/a_rules.json"
INIT="$SSR_DIR/__init__.py"
ISSUES=0

echo "=== SSR Integrity Check ==="
echo ""

# 1. 规则数 ≥ 200
RULES_COUNT=$(python3 -c "import json; print(len(json.load(open('$RULES'))))" 2>/dev/null || echo 0)
if [ "$RULES_COUNT" -ge 200 ]; then
    echo "✅ 规则数: $RULES_COUNT"
else
    echo "❌ 规则数: $RULES_COUNT (预期 ≥200)"
    ISSUES=$((ISSUES + 1))
fi

# 2. 无 non-manual 规则
NON_MANUAL=$(python3 -c "
import json
r=json.load(open('$RULES'))
print(sum(1 for v in r.values() if v.get('source')!='manual'))
" 2>/dev/null || echo -1)
if [ "$NON_MANUAL" -eq 0 ]; then
    echo "✅ 全员 manual"
else
    echo "❌ 非 manual: $NON_MANUAL 条"
    ISSUES=$((ISSUES + 1))
fi

# 3. __init__.py 3 个 FIX 保护
FIX_COUNT=$(grep -c "FIX.*manual" "$INIT" 2>/dev/null || echo 0)
if [ "$FIX_COUNT" -eq 3 ]; then
    echo "✅ __init__.py 保护: 3/3"
else
    echo "❌ __init__.py 保护: $FIX_COUNT/3"
    ISSUES=$((ISSUES + 1))
fi

# 4. config a_rules_max ≥ 300
MAX=$(python3 -c "
import yaml
c=yaml.safe_load(open('$CONFIG'))
print(c.get('ssr',{}).get('a_rules_max',100))
" 2>/dev/null || echo 100)
if [ "$MAX" -ge 300 ]; then
    echo "✅ a_rules_max: $MAX"
else
    echo "❌ a_rules_max: $MAX (预期 ≥300)"
    ISSUES=$((ISSUES + 1))
fi

# 5. golden backup 存在
if [ -f "$RULES.bak.golden" ]; then
    GOLDEN_COUNT=$(python3 -c "import json; print(len(json.load(open('$RULES.bak.golden'))))" 2>/dev/null || echo 0)
    echo "✅ golden备份: ${GOLDEN_COUNT}条"
else
    echo "⚠️  无 golden 备份"
fi

echo ""
if [ "$ISSUES" -eq 0 ]; then
    echo "🎉 全部通过"
    exit 0
else
    echo "🔴 $ISSUES 项失败"
    exit 1
fi
