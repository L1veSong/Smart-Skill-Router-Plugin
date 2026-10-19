# SSR Dashboard 设计参考

> 2026-06-10: Linear 暗色主题美化完成。本文档记录设计决策和 token 映射。

## 设计源

采用 Linear.app 设计系统（来自 `popular-web-designs` skill 的 `templates/linear.app.md`）。

## 设计 Token 映射

### 背景层

| Linear Token | CSS 变量 | 值 |
|-------------|---------|-----|
| Marketing Black | `--bg-deepest` | `#0a0a0c` |
| Panel Dark | `--bg-panel` | `#121316` |
| Level 3 Surface | `--bg-elevated` | `#1a1b1f` |

### 文本层

| Linear Token | CSS 变量 | 值 |
|-------------|---------|-----|
| Primary White | `--text-primary` | `#f7f8f8` |
| Silver Gray | `--text-secondary` | `#d0d6e0` |
| Tertiary Gray | `--text-tertiary` | `#8a8f98` |
| Quaternary Gray | `--text-quaternary` | `#62666d` |

### 强调色

| Linear Token | CSS 变量 | 值 |
|-------------|---------|-----|
| Brand Indigo | `--brand` | `#5e6ad2` |
| Accent Violet | `--brand-bright` | `#7170ff` |
| Accent Hover | `--brand-hover` | `#828fff` |

### 边框

| CSS 变量 | 值 | 用途 |
|---------|-----|------|
| `--border-subtle` | `rgba(255,255,255,0.06)` | 表格行、卡片 |
| `--border-standard` | `rgba(255,255,255,0.09)` | 输入框、按钮 |

### 字体

- **正文/UI**: Inter (Google Fonts), `font-feature-settings: 'cv01','ss03'`
- **代码/数字**: JetBrains Mono (Google Fonts)
- **CDN**: `https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap`

## 设计决策

### 为什么只有暗色模式

Linear 的设计哲学是暗色优先——移除亮色切换保持视觉一致性。原 dashboard 有亮/暗切换，美化后统一为暗色。

### 标签页激活态

不使用填充色，改用底部 2px 靛紫下划线（`::after` 伪元素）。保持 Linear 的克制风格。

### 按钮

- 默认：`rgba(255,255,255,0.03)` 背景 + 半透明白边框
- 主操作（accent）：`#5e6ad2` 实色
- 危险操作：`rgba(239,68,68,0.12)` 半透明红
- 表格内操作：透明 ghost 按钮

### 输入焦点

`box-shadow: 0 0 0 3px rgba(113,112,255,0.12)` 靛紫光环，替代默认蓝色 outline。

### 模态框

`backdrop-filter: blur(4px)` 模糊背景 + `box-shadow: 0 20px 60px rgba(0,0,0,0.5)` 深度阴影。

## 美化流程（可复用）

```
1. 加载设计 skills: ui-ux-pro-max + popular-web-designs + design-taste-frontend-v1
2. 从 popular-web-designs 选设计模板（Linear/Vercel/Stripe...）
3. cp 备份原文件
4. 替换 CSS 变量为设计 token（保持 HTML 结构和 JS 逻辑不变）
5. browser_vision 视觉校验
```

## 文件位置

- 源码：`~/.hermes/plugins/ssr/dashboard.html`
- 备份：`~/.hermes/plugins/ssr/dashboard.html.bak.YYYYMMDD_HHMMSS`
- 服务：`~/.hermes/plugins/ssr/dashboard.py` (端口 8766)
