# DOMAIN_STEMS Dead-Lock Pitfall (2026-07-23)

## Root Cause

SSR v2.4.0-MoE shipped with `DOMAIN_STEMS` containing only 6 domain names
(`travel`, `visual`, `writing`, `storage`, `map`, `shortdrama`) — but
`a_rules.json` had 34 domains. The domain names didn't match:

| DOMAIN_STEMS key | a_rules.json domain | Match? |
|---|---|---|
| `visual` | `生图` | No |
| `shortdrama` | `视频` | No |
| `writing` | `writing` | Yes (only one) |

The function `_route_domains()` returned `ALL_DOMAINS` as fallback when
no stem matched — which was **every single message**. This meant the MoE
routing layer never actually gated anything. All 183 rules were scanned
for every request, brute-force.

The `ALL_DOMAINS = set(DOMAIN_STEMS.keys())` line silently masked the
bug — if no domain was activated (always true with only 6 domains),
the entire rule set was scanned.

## Fix (v2.5.0-MoE)

1. Rebuilt `DOMAIN_STEMS` with 34 domains matching `a_rules.json`
2. Each domain gets 5-15 atomised, disambiguated stems
3. Dangerous stems removed: no bare `写`, no bare `服务器`, no bare `Spotify`
4. `ALL_DOMAINS` fallback kept as safety net (recommendation: remove in v3)

## Prevention

When adding a new domain to `a_rules.json`:
1. Add a corresponding entry to `DOMAIN_STEMS` in `__init__.py`
2. Add at least 5 representative stems
3. Run `_route_domains()` unit test with the new domain's test phrases
4. Verify domain count matches between `a_rules.json` and `DOMAIN_STEMS`

## Diagnostic Command

```python
# Verify stem routing is working
import json, re
rules = json.load(open("a_rules.json"))
rule_domains = set(d.get("domain") for d in rules.values() if d.get("domain"))
# Then grep DOMAIN_STEMS keys from __init__.py and compare
```
