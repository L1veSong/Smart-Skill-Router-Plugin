# Dashboard 美化 · 四 Skill 组合工作流

> 2026-06-10 SSR Dashboard 实战验证

## 适用场景

仪表盘、管理后台、数据面板、配置页面的视觉升级——不改 JS 逻辑，只翻新 CSS/HTML。

## 四 Skill 分工

| Skill | 角色 | 产出 |
|-------|------|------|
| `redesign-existing-projects` | 审计官 | 遍历审计清单 → 列出全部 AI slop |
| `frontend-design` | 定调人 | 选一个大胆美学方向并贯彻到底 |
| `high-end-visual-design` | 视觉引擎 | 出设计 token：颜色/字体/阴影/圆角/动效 |
| `popular-web-designs` | 数据表 DNA | Linear/Vercel/Stripe 表结构规范 |

## 工作流（5 步）

### Step 1: 审计 → 定方向

```
1. 读取当前 HTML/CSS 全量
2. 逐项对照 redesign-existing-projects 审计清单
3. 列出命中项（Inter 字体 / 靛紫主色 / emoji 图标 / 纯平背景 / 无加载态...）
4. frontend-design 选方向：Ethereal Glass × Industrial Data Density
```

关键决策点：
- 暗色还是亮色？数据面板 → 暗色，减少眼疲劳
- 主色选什么？避开 AI 套路紫/蓝 → Emerald/Terra cotta/Amber
- 字体选什么？所有 design skill 禁 Inter → Geist/Outfit/Satoshi

### Step 2: 提取视觉 token（high-end-visual-design）

从 high-end-visual-design 选 Vibe：
- **Ethereal Glass**：OLED 黑 + 径向微光 + 玻璃模糊 + 内高光线 — 暗色仪表盘首选
- Editorial Luxury：暖米色 + Serif 标题 — 不适合数据面板
- Soft Structuralism：银灰 + 巨字 Grotesk — 浅色适用

Double-Bezel 卡片架构：
```css
.stat-outer { /* 外壳 */ padding:1.5px; border:1px solid var(--border-subtle); }
.stat { /* 内芯 */ box-shadow: inset 0 1px 1px rgba(255,255,255,0.06); }
```

### Step 3: 提取数据表 token（popular-web-designs）

从 Linear 模板提取：表头 uppercase · 分割线 hairline · 悬停半透明 · 等宽数字 Geist Mono。

### Step 4: 逐组件翻新（不改 JS）

优先级：字体 → 主色 → 按钮态 → 嵌套卡 → SVG 图标 → 骨架屏 → 动画

### Step 5: 验证

API 存活 + 浏览器零 JS 错误 + 视觉截图对比。

## 踩过的坑

- 背景太黑（#050505 OLED）→ #0c0c0f
- 主题切换被误删 → 补回
- i18n 中文版混英文 → 全量重写
- 加载了 tasty/gpt-taste/minimalist-ui 但未使用 → 浪费

## 关键取舍

- tasty 禁 Inter+禁紫+禁emoji → 和 high-end 一致 → 弃 tasty 用 high-end 做主引擎
- gpt-taste GSAP 太重 → 仪表盘杀鸡用牛刀
- minimalist-ui 暖色浅色 → 反方向
- claude-design 只给流程不给 token → 被 redesign-existing-projects 替代
