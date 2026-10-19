# Dashboard 重设计反模式

> 2026-06-24 会话：三次 dashboard 重设计全失败，根因总结。

## 反模式 1: 用 landing page 设计 skill 做 dashboard

`design-taste-frontend` 在 Section 13 明确写了 NOT for dashboards。`sleek`、`bento`、`mono`、`neobrutalism` 都是 landing/marketing 页面的设计系统，做仪表盘效果差。

**正确做法：** dashboard 是功能页面，设计优先级是信息密度 > 对齐 > 可读性 > 视觉风格。不需要"设计系统"，需要干净的数据排版。

## 反模式 2: write_file 全量覆盖单文件应用

dashboard.html 是 CSS+HTML+JS 三合一单文件。用 write_file 覆写整个文件会丢失未修改的部分（已发生两次：HTML body+JS 丢失，从零重建）。

**正确做法：**
1. 改前 `cp dashboard.html dashboard.html.bak.$(date +%m%d%H%M)`
2. 用 `patch` 逐段替换 CSS，不碰 HTML/JS
3. 改后立即浏览器验证

## 反模式 3: 不理解用户说的"对齐"

用户说"右对齐"指开关（toggle switch）在卡片行右侧，不是数字右对齐。不要自作主张改表格数字对齐。

**开关右对齐的标准实现：**
```css
.card-row { display: flex; align-items: center; }
.card-row label.switch { margin-left: auto; }
```

HTML 结构中 label text 在前，switch 在后。CSS 用 `margin-left: auto` 把开关推到右边。

## 反模式 4: 过度设计

统计卡片不需要玻璃效果、不需要渐变、不需要动画。dashboard 用户要的是信息，不是视觉体验。

**简洁设计清单：**
- 单强调色（蓝 `#3B82F6` 或绿 `#10b981`）
- 暗底（`#0a0a0f`）+ 卡片（`#111118`）
- 无玻璃效果（`backdrop-filter` 全删）
- Geist 字体
- 卡片用 `border: 1px solid`，不用 shadow
- hover 只改 border-color，不 translate

## 反模式 5: 功能改动时连带改设计

SSR v2.1 加了 `llm_screen`、`display` 配置项，只需在 HTML 加对应的开关卡片 + JS 加 save 函数。不需要趁机重写整个 CSS。功能迭代和设计重做是两次独立操作。
