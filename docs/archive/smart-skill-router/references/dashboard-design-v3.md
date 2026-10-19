# SSR Dashboard v3 设计决策

> 2026-06-10 · Ethereal Glass + Industrial Data Density

## 设计流程（四 skill 组合）

```
redesign-existing-projects → 审计当前 dashboard AI slop
frontend-design → 定美学方向：Ethereal Glass + Brutal data
high-end-visual-design → 视觉 token：Double-Bezel + 贝塞尔
popular-web-designs → 数据表 token：Linear 等宽/分割线/悬停
```

## 核心改动

| 维度 | 旧 | 新 |
|------|-----|-----|
| 字体 | Inter | **Geist + Geist Mono** |
| 主色 | `#5e6ad2` 靛紫 | **`#10b981` Emerald** |
| 背景 | `#0a0a0c` 纯黑 | **`#0c0c0f` + 径向微光** |
| 图标 | ✏ 🗑 emoji | **SVG 描线图标** |
| 卡片 | 单层 bg+border | **Double-Bezel（外壳+内芯）** |
| 动效 | `(0.22,1,0.36,1)` | **`(0.32,0.72,0,1)`** |
| 加载 | 空白等待 | **骨架屏 + 设计空态** |
| 语言 | 中英混 | **zh 全中文 / en 全英文** |

## 玻璃特效

```css
/* 卡片 */
.stat-outer { backdrop-filter: blur(12px); border: 1px solid rgba(255,255,255,0.07); }
.stat {
  background: rgba(20,20,24,0.65); 
  backdrop-filter: blur(10px);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.04);  /* 内高光线 */
}

/* 模态 */
.modal-box {
  backdrop-filter: blur(20px);
  box-shadow: inset 0 1px 1px rgba(255,255,255,0.04), 0 24px 80px rgba(0,0,0,0.5);
}

/* 按钮 */
.btn { backdrop-filter: blur(8px); }
```

## 动画关键帧

```css
@keyframes cardIn   { from { opacity:0; transform:translateY(16px) scale(0.97); } }
@keyframes slideUp  { from { opacity:0; transform:translateY(10px); } }
@keyframes scaleIn  { from { opacity:0; transform:scale(0.94); } }
```

统计卡入场交错：nth-child(1) 0.05s → (2) 0.12s → (3) 0.19s → (4) 0.26s  
表行动画：`animation-delay: calc(var(--index) * 30ms)`

## i18n 修复（关键）

**问题：** 全量重写 HTML 时，`i18n` 对象从旧版复制但 zh/en 部分混入对方语言（如 `zh.col-skills: "Skill"`）。

**修复：**
- 重写完整 i18n 对象，zh 和 en 各自独立定义
- 表头 `<th>` 和模态框动态文本走 `data-lang` + `t()` 
- `render()` 函数内按钮 title 用 `t("btn-edit")` / `t("btn-delete")`
- 新增 `hit-rate` key 避免拼接（`t("col-hits")+"率"` → `t("hit-rate")`）

## 坑点：全量重写必丢功能

两次全量 `write_file` 重写 dashboard.html 导致：
1. 主题切换按钮消失（`toggleTheme` 函数 + ☀ 按钮）
2. i18n 部分翻译错乱

**规则：** 重写整个文件后，必须从旧版 `diff` 逐项核对功能清单。不依赖自我感觉"都保留了"。

## 文件清单

| 文件 | 用途 |
|------|------|
| `dashboard.html` | 前端 UI（Geist + Glass + SVG icons） |
| `dashboard.py` | Python HTTP 服务器（8766 端口） |
| `a_rules.json` | A 层关键词规则（100 条） |
| `embeddings.json` | bge-m3 1024 维索引（296 skill） |
