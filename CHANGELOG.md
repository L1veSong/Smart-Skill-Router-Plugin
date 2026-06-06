# CHANGELOG

## v0.3.0 (2026-06-06)

### 新增
- 暂停开关：Dashboard 一键停用 SSR，config.yaml 真实写入 `ssr.enabled: false`
- 规则重置：Dashboard 一键清空 A 层，二次确认
- Dashboard 全面重构：动画微交互、中英文切换、亮暗主题、实时时钟、30s 自动刷新
- B 层新增 lmstudio / llamacpp 后端支持

### 修复
- README ASCII 架构图纯英文对齐
- B 层 `_match_b_openai` URL 双 `/v1` 修复
- `_match_b_layer` 路由补 lmstudio / llamacpp

## v0.2.0 (2026-06-05)

### 新增
- 推荐模式开关：推荐/强制，Dashboard 一键切换
- 扫描策略：启动时/每次提问，Dashboard 切换
- Dashboard B 层配置面板：provider/model/URL/key/timeout 可视化
- Dashboard Tab 导航 + UI 美化
- README badge + 架构图 + 表格

## v0.1.0 (2026-06-05)

首次公开发布。
