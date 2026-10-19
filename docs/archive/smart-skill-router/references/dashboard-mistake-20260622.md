# CMG vs SSR Dashboard 混淆

> 2026-06-22: AI 将 SSR 门控卡片误加到 CMG Dashboard

## 两个独立 Dashboard

| | SSR | CMG (三省引擎) |
|--|-----|---------------|
| 路径 | `~/.hermes/plugins/ssr/dashboard.py` | `~/.hermes/dashboard/server.py` |
| 端口 | `8766` | `8765` |
| 配置文件 | `~/.hermes/plugins/ssr/dashboard.html` | 内置在 server.py |

## 预防

修改前: `lsof -iTCP -sTCP:LISTEN | grep Python` 确认端口归属。
CMG Dashboard 有 `.bak` ~ `.bak5` 备份链，改前 cp。
