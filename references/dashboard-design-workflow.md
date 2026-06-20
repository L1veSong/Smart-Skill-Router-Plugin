# Dashboard 美化工作流 — 2026-06-10 实战

> 四 skill 组合方法论。8 个设计 skill 评估 → 冲突分析 → 选最优组合 → 审计 → 重写。

## 触发条件

用户说「美化/重设计/好看一点」+ 已有 HTML/CSS 产物。

## 流程

### Phase 1: 加载 + 评估

加载所有候选设计 skill（SSR 推荐 + 手动扫描），逐条评估适用度：

| 维度 | 检查 |
|------|------|
| 目标匹配 | 暗色仪表盘？营销页？数据表？ |
| 字体冲突 | 是否禁 Inter？要求 Geist/Outfit？ |
| 色系冲突 | 是否禁紫色/蓝色？ |
| 复杂度 | GSAP 重武器 vs 纯 CSS？ |
| 可组合性 | 是否与其他 skill 冲突？ |

**本会话实际评估结果：**

| Skill | 评估 | 原因 |
|-------|:--:|------|
| high-end-visual-design | ⭐⭐⭐⭐⭐ | Ethereal Glass + Double-Bezel |
| redesign-existing-projects | ⭐⭐⭐⭐⭐ | 审计→诊断→修复流程 |
| popular-web-designs | ⭐⭐⭐⭐ | Linear 数据表 DNA |
| frontend-design | ⭐⭐⭐⭐ | 美学方向定调 |
| design-taste-frontend-v1 | ⭐⭐⭐ | 反 AI 套路清单，但与 Linear 冲突 (禁 Inter/禁紫) |
| gpt-taste | ⭐⭐ | GSAP 重武器，仪表盘杀鸡用牛刀 |
| claude-design | ⭐⭐⭐ | 流程纪律（被 redesign-existing-projects 替代） |
| minimalist-ui | ❌ | 暖色浅色系，暗色仪表盘反方向 |

### Phase 2: 冲突分析

交叉对比已选 skill 的设计约束：

```
high-end:  禁 Inter → 要 Geist
tasty:     禁 Inter + 禁紫 + 禁 emoji
popular:   Linear 用 Inter + 靛紫
gpt:       禁 Inter

交集: 全部禁 Inter → Geist 是唯一共识
      全部禁 AI 紫 → Emerald #10b981
      全部禁 emoji → SVG 图标
```

### Phase 3: 执行

```
1. redesign-existing-projects 审计当前 → 列 AI slop
2. frontend-design 定美学方向 → Ethereal Glass
3. high-end-visual-design 出 token → 颜色/阴影/贝塞尔
4. popular-web-designs 出表 token → 行高/分割线/等宽
5. 重写 CSS，不动 JS
6. 截图对比
```

### Phase 4: 验证清单

- [ ] 字体是否按共识（Geist，非 Inter）？
- [ ] 品牌色是否按共识（Emerald，非紫）？
- [ ] Emoji 是否全部替换为 SVG？
- [ ] 卡片是否有 Double-Bezel？
- [ ] 动效是否用定制贝塞尔？
- [ ] 是否有加载态/空态？
- [ ] 黑白切换是否可用？
- [ ] i18n 是否纯语言（zh=全中文，en=全英文）？

## 本会话产出

- `~/.hermes/plugins/ssr/dashboard.html` — SSR 仪表盘最终版
- Glassmorphism + Emerald accent + Double-Bezel + Geist + SVG 图标
- 功能完整：规则管理 / 引擎配置 / 统计面板 / 骨架屏 / 黑白切换 / 中英切换
