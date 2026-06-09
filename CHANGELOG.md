# CHANGELOG

## v0.6.1 (2026-06-10)

### 新增
- 智能冷却：自适应冷却（已加载×3、反复推荐未加载×0.5、紧急×0.5、5次未加载跳过）
- 增量索引自动运行：每10分钟自动全量 sync + description 变更检测
- Dashboard 全面美化：Ethereal Glass 暗色主题 + 玻璃特效 + Geist 字体 + Emerald 主色
  - 4 skill 组合驱动：redesign-existing-projects 审计 + high-end-visual-design 视觉 + popular-web-designs 数据表 + frontend-design 定调
  - 亮/暗主题切换（localStorage 持久化）
  - 中/英文完整切换（zh 全中文、en 全英文）
  - 玻璃特效：backdrop-filter blur + 内高光线
  - 动画：统计卡交错入场、卡片 hover 上浮、模态弹性缩放
  - Double-Bezel 嵌套卡架构、SVG 描线图标替代 emoji
  - 骨架屏加载态 + 设计空态

## v0.6.0 (2026-06-10)

### 新增
- Phase 3: Embedding 质量提升 — 描述富化（正文提取）+ 中文查询增强（14域中英映射）
- Phase 4: 生产监控 — Dashboard /api/stats + 会话命中率日志（每10次输出）
- 三层漏斗架构：关键词正则 + bge-m3 Embedding + B层 LLM 五后端

## v0.5.0 (2026-06-09)

### 新增
- bge-m3 Embedding 层（1024维，淘汰 nomic-embed-text）
- TDD 基准测试 5/5 GREEN（bge-m3 全通过）
- auto-gen 开关：ssr.auto_gen_rules: false 关闭自动生成
- 冷却制修复：shown_recently 标签替代 continue 丢弃

### 修复
- 坑点 14: nomic-embed-text 中文区分度极低 → 换 bge-m3
- 坑点 17: 冷却 continue 误杀跨消息匹配

## v0.4.0 (2026-06-06)

### 新增
- Dashboard /api/stats 端点 + 统计面板
- B→A 升级：连续 3 次同一匹配自动固化到 A 层
- 结果缓存：B 层结果 60s 内复用
- 冷启动重试：B 层超时自动 warmup + 重试一次

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
