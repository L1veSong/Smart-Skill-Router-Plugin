# Dashboard 优化模式参考

> 2026-06-21 实战 — SSR Dashboard 从基础到 polished 的完整优化路径

## Taste Checklist 对 Dashboard 的适配

`design-taste-frontend` 的 Pre-Flight Checklist 面向营销落地页，但大部分检查项适用于 dashboard：

**直接适用（必须过）**：
- ❌ em-dash `—` 滥用 → Dashboard 中文注释中 `——` 允许，代码中禁止
- ✅ 无 `!important` → dashboard.css 零使用
- ✅ 无 `h-screen` → 用 `min-h-[100dvh]` 或普通布局
- ✅ 暗/亮双模 → `[data-theme="light"]` + CSS 变量切换
- ✅ 零 scroll listener → 不用 `addEventListener('scroll',...)`
- ✅ 单色调统一 → green accent 贯穿全站
- ✅ 纯黑 `#000` 检查 → 用 off-black（`#0c0c0f`）

**正则误报（需人工判定）**：
- "Inter" 字体 → 可能是 JS `setInterval` 匹配，不是 Inter 字体
- "slate/zinc" 色 → 可能是 CSS `translate` 属性匹配，不是 tailwind 色
- 判断方法：`grep -o` 看上下文，不要只看 regex count

**Dashboard 豁免项**：
- "No 3-column equal cards" → Dashboard 用 `grid-template-columns: repeat(auto-fit, minmax(170px, 1fr))` 自适应，不同等固定 3 列
- "Centered hero" → Dashboard 无 hero
- "Serif discipline" → Dashboard 全用 Geist sans

## CSS 增强清单

按优先级排列，不改功能只改视觉：

### 背景
```css
body::before {
  /* 三层渐变 + 8s 呼吸动画，GPU 安全（fixed + pointer-events:none）*/
  background:
    radial-gradient(ellipse 60% 50% at 50% 40%, rgba(16,185,129,0.04) 0%, transparent 70%),
    radial-gradient(ellipse 80% 60% at 80% 20%, rgba(16,185,129,0.02) 0%, transparent 60%),
    radial-gradient(ellipse 50% 70% at 20% 80%, rgba(5,150,105,0.02) 0%, transparent 50%);
  animation: bgPulse 8s ease-in-out infinite alternate;
}
```

### 统计卡片
- 入场动画：`cardIn 0.6s var(--ease-spring)` — 比默认 cubic-bezier 更有弹性
- hover 效果：`translateY(-3px) scale(1.01)` + `box-shadow` 绿光
- 玻璃态：`backdrop-filter: blur(16px)` + `inset 0 1px 1px highlight`

### 按钮
- `transition: all 0.25s var(--ease-spring)` — 弹簧反馈
- `:active` → `scale(0.96)` — 按下反馈
- accent 按钮 → `box-shadow: 0 2px 8px accent-glow` — 发光提示

### Toggle 开关
- 宽度 42px 高度 24px — 比默认 40x22 更显眼
- 球体 `box-shadow: 0 1px 3px rgba(0,0,0,0.3)` — 立体感
- 选中态 `box-shadow: 0 0 12px accent-glow` — 绿光

### Toast
- `translateY(16px)` 初始位置 → 弹起入场
- `backdrop-filter: blur(20px)` — 更深模糊
- `box-shadow: 0 16px 48px rgba(0,0,0,0.5)` — 悬浮感

### 状态点
- 6px 圆点 + `animation: pulse 2s ease-in-out infinite` — 呼吸动画

### Keyframes
```css
@keyframes cardIn { from { opacity:0; transform:translateY(20px) scale(0.95); } to { opacity:1; transform:translateY(0) scale(1); } }
@keyframes scaleIn { from { opacity:0; transform:scale(0.92); } to { opacity:1; transform:scale(1); } }
@keyframes pulse { 0%,100% { opacity:1; } 50% { opacity:0.4; } }
@keyframes bgPulse { 0% { opacity:0.8; } 100% { opacity:1; } }
```

## JS 优化

### 统计数字跳动
```javascript
// 首次加载：0→target 动画计数
// 后续刷新：直接更新数值，不再重建 DOM（避免闪烁）
var _statsBuilt = false;
function loadStats() {
  if (!_statsBuilt) {
    // build HTML with data-target attributes
    _statsBuilt = true;
    animateCounters();
  } else {
    // direct textContent update, no DOM rebuild
    document.querySelectorAll('#stats .stat-value').forEach(function(el, i) {
      if (vals[i] != null) el.textContent = vals[i];
    });
  }
}
```

### 搜索防抖
```javascript
var _renderTimer;
function debounceRender() {
  clearTimeout(_renderTimer);
  _renderTimer = setTimeout(render, 150);
}
```

## 设计 Skill 选择指南

| 场景 | 用哪个 skill | 为什么 |
|------|-------------|--------|
| Dashboard / 数据面板 | `dashboard` | 8pt grid、dark theme、glass panels、数据层级 |
| 营销落地页 | `design-taste-frontend` | 完整 Pre-Flight、色彩/排版/布局约束 |
| 高端代理商页 | `high-end-visual-design` | Double-Bezel、玻璃丸、Z轴层叠 |
| 通用 UI 设计 | `ui-ux-pro-max` | 161 调色板、57 字体配对、99 UX 指南 |
| 前端组件实现 | `frontend-design` | 生产级代码、反 AI 模板化 |

**不要混用**：Dashboard 面板不要用 `high-end-visual-design` 的 Double-Bezel/Z轴层叠——那是营销页语言。不要用 `design-taste-frontend` 的 em-dash 禁令来要求中文 dashboard 的 `——`。

## 已应用的效果总览

| 效果 | 实现 | 性能 |
|------|------|:--:|
| 背景渐变呼吸 | CSS `@keyframes bgPulse` + fixed pseudo | ✅ GPU |
| 统计卡片弹簧入场 | `cardIn 0.6s spring` + staggered delay | ✅ CSS |
| 数字跳动计数 | `setInterval` 16ms + `data-target` | ✅ JS |
| 按钮弹簧反馈 | `transition spring` + `scale(0.96)` | ✅ CSS |
| 开关弹性球 | `transition spring 0.35s` + glow | ✅ CSS |
| 状态点脉冲 | `animation pulse 2s infinite` | ✅ CSS |
| Toast 弹入 | `translateY + spring + blur(20px)` | ✅ CSS |
