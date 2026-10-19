# Dashboard 门控配置 (2026-06-22)

## 位置

SSR Dashboard: `http://localhost:8766` → 引擎配置 → 门控模型卡片

⚠️ 不是 CMG Dashboard (`localhost:8765`)。两个不同。

## 功能

- **激活提供者**: 下拉选 `ollama` 或 `main`，显示当前模型名
- **启用门控**: 开关，关闭后门控不生效，所有消息放行
- **保存**: 写入 `config.yaml → ssr.intent_gate.active` 和 `enabled`，需重启 Hermes 生效

## API

- `GET /api/config` → `gate_active`, `gate_enabled`, `gate_providers`
- `POST /api/config` → `{"gate_active": "main", "gate_enabled": true}`

## 修改涉及文件

| 文件 | 改动 |
|------|------|
| `~/.hermes/plugins/ssr/dashboard.py` | `load_config()` 加 gate 字段, `save_config()` 加 gate 写入 |
| `~/.hermes/plugins/ssr/dashboard.html` | 门控模型卡片 HTML + `markGateDirty()`/`saveGate()` JS |
