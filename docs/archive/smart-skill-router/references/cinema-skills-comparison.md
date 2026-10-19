# 生图 Skill 选择指南（电影感/摄影/海报）

> 2026-07-24 会话整理。7 个生图 skill 全量（FANTASY×6 + ZY×1）。
> 更新：2026-07-24（追加模型适配、短剧流程定位、实战教训、单跑铁则）

## 电影感静帧

| Skill | 输出 | 核心逻辑 | 适合模型 | 适合场景 |
|-------|------|---------|---------|---------|
| **cinema-dna-21x9x3** | 3 张 21:9 三联镜头 + 电影判断 + 自检评分 | 构图=权力关系·视线流量·色彩命题 | **GPT Image**（作者实测平台） | 有叙事需求的多镜头组、概念图 |
| **zy-cinematic-realism** | 单帧 prompt + 画面理解 + Avoid | 物理可信优先·先去术语再加质感 | 万相/Z-Image/GPT 均可 | 一张真实电影感单帧、短剧分镜 |

**配合方式：** zy 定调（光线/摄影机）→ cinema-dna 拉三联（叙事/构图）。单帧需求只用 zy。

### 🔴 铁则：用户说用哪个就只用哪个（2026-07-24）

用户说"按 cdna 出一个"——出 cinema-dna 完整输出，不要偷偷混 zy 的 35mm/Portra/具体焦段。用户说"试试 zy"——出 zy 完整输出，不要带 cdna 的视线流量/构图压力/三联结构。两种语言体系不同，混用互相稀释，用户一眼能看出来。

### 模型适配关键教训（2026-07-24）

**cinema-dna 不吃万相/Z-Image。** 它的"视线流量""构图压力E型""不可解的状态"是叙事语言——万相和 Z-Image 的训练数据不理解抽象叙事概念。作者用 GPT Image 2 实测验证的（README 明确写了 "Image 2 出图"），换模型=skill 空转。

**zy 全模型通用。** 它的方法论是"先让画面物理成立，再加术语"——35mm 镜头、自然光无补光、前景岩石失焦——这些是执行指令，不是叙事分析。万相、Z-Image、GPT 都能吃。

**AI 感根因不是 prompt 不行——是模型训练偏置。** 用户想要"冷灰蓝、无暖色、无金色光"的黎明前风景 → 万相和 Z-Image 的训练数据里"好风景=黄金时刻"→ 模型不听 negative prompt。换 GPT Image 才能突破这个天花板。

### 短剧流程定位

| 流程阶段 | 用哪个 | 理由 |
|---------|--------|------|
| 概念图 | cinema-dna | 需要叙事张力和氛围 |
| 分镜图（逐镜） | **zy** | 需要单帧、物理精确、GPT Image 能精确执行 |
| 海报/封面 | oriental-editorial-poster | 版式系统+文化物证 |

Plan 决策 0-19（提示词铁律）与 zy 方法论重叠：去污染化=zy 的"去掉 cinematic/35mm 后画面依然成立"；视觉代偿=zy 的"只描述可观察动作"。

## 摄影/人像

| Skill | 定位 |
|-------|------|
| **fantasy-life-force-portrait-photography** | 生命感人像（废片升级/从零生成） |
| **fantasy-photography-simulation** | 哈苏/徕卡/理光相机美学摄影组图 |

## 海报/视觉

| Skill | 定位 |
|-------|------|
| **oriental-editorial-poster**（GitHub: fantasy-dongfang-jianyuehaibao） | 东方文化编辑式海报，v2.0.0 |
| **regional-culture-poster** | 省/市/文化区域转化汉字海报 |
| **culture-fragment-poster-engine** | 零散文化图片→品牌视觉系统 |

## 向用户交付 prompt 的规范（2026-07-24 实战纠正）

用户不是来读分析的——是来拿 prompt 去生图的。交付时：

1. **纯英文 prompt 文件**：`.txt`，三段英文 `---` 分隔，无中文、无 CLI 语法、无标点装饰
2. **完整版另存**：`_完整版.txt`（含电影判断+自检评分），存档用，不给用户
3. **zy 只给 Final Prompt**：不给 Avoid（国产模型网页端通常没有 negative prompt 框）
4. **不要写"这是用 XX skill 生成的"**——用户知道，不需要你标注
5. **文件名中文描述**：`戈壁公路_三联prompts.txt`，让用户一眼知道是什么

Kōda 是用户 AI 短剧《墨刑》的分镜方法论（颜色标注系统 + 故事板→Seedance 2.0），做**多镜头视频**。cinema/zy 做**静帧 prompt**。可做上下游：cinema-dna/zy 出关键帧概念图→喂 Kōda 做分镜参考。

## 生图平台实测对比（2026-07-24）

| 平台 | 模型 | 分辨率 | 价格 | 构图服从 | 写实 | 暖色克制 |
|------|------|:--:|------|:--:|:--:|:--:|
| GPT Image 2 | gpt-image-1 | 2K | $20/mo | ★★★★★ | ★★★★★ | ✅ |
| 阿里百炼 | wan2.7-image-pro | 4K | ¥0.45 | ★★★☆☆ | ★★★★☆ | ❌ |
| 阿里百炼 | qwen-image-2.0 | 2K | ¥0.20 | ★★★☆☆ | ★★★☆☆ | ❌ |
| 硅基流动 | Z-Image-Turbo | 1024 | ¥0.04 | ★★★☆☆ | ★★★☆☆ | ❌ |
| 阮捷 API | GPT Image(中转) | ? | RMB | 待验证 | 待验证 | 待验证 |

> qwen-image-2.0 是文字排版特化模型（PPT/图表/海报），不宜写实风景。
> 阮捷 API (ruanjieapi.com) 声称支持 GPT Image 中转，人民币支付，待实测。

### 合成方式

cinema-dna 要求三张独立 21:9 图纵向拼接，8px 黑间隔。用 Python PIL：
```python
from PIL import Image
a,b,c = [Image.open(f"gobi_{i}.png") for i in [1,2,3]]
w = max(a.width, b.width, c.width)
h = a.height + b.height + c.height + 16
out = Image.new('RGB', (w,h), (0,0,0))
out.paste(a, (0,0)); out.paste(b, (0,a.height+8)); out.paste(c, (0,a.height+b.height+16))
out.save('output.png')
```

21:9 比例在部分平台会被裁切变形——万相网页端会变成 7:3。建议用 16:9 生图，后期手动裁。或者填精确像素 `3840*1640`。
