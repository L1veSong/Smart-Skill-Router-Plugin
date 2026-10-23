# SSR 三维评分系统 v2 — 实施计划

> 创建: 2026-06-21 | 更新: 同日 v2 | 依赖: 门控 v0.7.0

## 设计原则

1. **top-3 不是 top-1。** "新疆旅游路线图"→ geojson-svg-map #1、svg-geo-map #2、geographic-viz #3，三个都对。只奖 #1 不公平。
2. **期望 skill 有多个正确答案。** "部署网站到 Vercel"→ deploy-to-vercel、vercel-optimize、vercel-composition-patterns 都算对。标注是参考不是标准答案。
3. **每个权重有理由。** 不拍脑袋。
4. **Dashboard 小字声明。** "基于 50 条固定测试，实际体验可能不同。"

## 三个分数

| | 总评分 | embed裸分 | 门控裸分 |
|---|:--:|:--:|:--:|
| 测多少 | 50 | 50 | 50 |
| 关什么 | 无 | 关键词+门控 | 关键词+embed |
| 回答 | SSR 好不好用 | 向量模型强不强 | LLM 能不能当门卫 |

## 基准数据（50 条，零隐私，GitHub-safe）

每个信号标注**多个**可接受 skill。

```
信号 30 条:
  设计×4:  暗色仪表盘           → brainstorming, ui-ux-pro-max, frontend-design, design-taste-frontend
           响应式导航栏          → brainstorming, ui-ux-pro-max, frontend-design
           改这个按钮颜色         → ui-ux-pro-max, frontend-design, redesign-existing-projects
           设计一个登录页         → brainstorming, ui-ux-pro-max, frontend-design, high-end-visual-design

  调试×3:  代码报KeyError        → diagnose, systematic-debugging, code-simplifier
           函数返回None排查       → diagnose, systematic-debugging
           接口超时怎么解决       → diagnose, systematic-debugging

  金融×2:  茅台均线走势           → technical-analysis, tushare-finance, stock-screen-monitor
           北向资金流向           → tushare-finance, finance-news-analyzer, stock-screen-monitor

  旅行×2:  北京自驾到南昌         → road-trip-planner, travel-skill, trip-planner-generator
           三天上海旅游攻略       → travel-skill, travel-plan-html-editor, trip-website-generator

  学术×2:  写论文文献综述         → research-paper-writing, survey, paper-spine-research
           这段文字降重           → research-paper-writing, paper-spine-humanize

  部署×2:  部署网站到Vercel       → deploy-to-vercel, vercel-optimize, vercel-composition-patterns
           Docker部署后端         → deploy-to-vercel

  PPT×2:   季度PPT汇报           → pptx, powerpoint
           产品介绍演示文稿        → pptx, powerpoint

  地图×2:  中国地图GDP分布        → geographic-visualization, svg-geo-map, geojson-svg-map, geographic-viz
           旅游路线图             → svg-geo-map, geojson-svg-map, geographic-visualization, travel-skill

  ASCII×1: 画ASCII猫咪           → ascii-art

  微信×1:  发微信给朋友说晚到     → wechat-desktop-send

  通用×9:  写Python脚本处理CSV    → subagent-driven-development, executing-plans
           分析Nginx日志          → diagnose
           翻译成英文             → (通用，至少匹配 1 个)
           优化慢SQL              → code-simplifier
           解释这段代码           → understand-explain
           配置环境变量           → (通用)
           起个变量名             → (通用)
           正则匹配手机号          → (通用)
           Git合并冲突解决         → using-git-worktrees

噪音 20 条:
  极短×3:  嗯嗯 / 哦 / OK
  寒暄×5:  谢谢你的帮助 / 好的我明白了 / 你觉得呢 / 今天天气怎么样 / 行吧
  闲聊×5:  昨天看了电影 / 这个颜色好看吗 / 你觉得哪个好 / 周末去哪玩 / 我饿了
  反问×4:  能行吗 / 确定吗 / 真的假的 / 不是吧
  无意义×3: ... / ？？？ / 哈哈
```

## 总评分 公式

测全链路（关键词+embed+门控），50 条全跑。

```
指标          满分  公式                    理由
─────────────────────────────────────────────────
信号命中率     40   命中数÷30×40           最重要——用户找 skill 是核心需求
              (任意期望 skill 进 top-12 就算命中)
噪音静默率     30   静默数÷20×30           噪音漏过推无关 skill 破坏信任
top-3 覆盖率   20   期望 skill 进 top-3    精准度——进 top-12 算命中，进 top-3 算精准
              次数÷30×20
延迟          10   <50ms=10, <200ms=7,     用户体感
                   <500ms=3, >500ms=0

总分 100
```

## embedding 裸分 公式

关 A 层关键词、关门控。纯向量匹配。50 条全跑。

```
指标          满分  公式                    理由
─────────────────────────────────────────────────
信号命中率     35   命中数÷30×35           裸向量能做到多少
              (期望 skill 进 top-12 即中)
噪音不该推     30   噪音中一条都没推÷20×30  embedding 没能力判意图，
              推了0条=30分                  但不该对噪音也全推
              推了1-2条=15分
              推了3+条=0分
top-3 覆盖率   25   期望 skill 进 top-3    纯向量语义区分度
              次数÷30×25
延迟          10   <50ms=10, <200ms=7,
                   <500ms=3

总分 100
```

**噪音不该推判定规则（客观，无主观边界）：**
```
floor 过滤后 top-12 非空 → 推了 → 扣分
floor 过滤后 top-12 为空 → 没推 → 加分
```
不用"推了几个"的模糊边界。floor 是配置值（默认 0.35），不算硬编码。

## 门控裸分 公式

关关键词、关 embedding。纯测 LLM YES/NO。50 条全跑。

```
指标          满分  公式                    理由
─────────────────────────────────────────────────
噪音正确率     60   判对数÷20×60           核心——噪音漏过代价最大
              (噪音判 NO 算对)             30条embedding白跑+用户看到垃圾
信号正确率     30   判对数÷30×30           重要——但门控 NO 不致命
              (信号判 YES 算对)            fail open 后面 embedding 兜底
延迟          10   <200ms=10, <500ms=5,
                   <1000ms=3, >1000ms=1

总分 100
```

**为什么噪音 60 信号 30：**
```
门控 NO 噪音 → 静默 ✅ 省 30 条 embedding → 满分贡献
门控 YES 噪音 → embedding 跑 30 条垃圾 → 最差，扣最多
门控 NO 信号 → fail open 放行 → embedding 兜底 → 不致命
门控 YES 信号 → 正常 → 中等贡献
```
一个对所有消息都说 YES 的模型：噪音 0 分 → 总分 30。无用。

## 分数区间（三个分统一）

| 分数 | 判定 | 颜色 | 用户看到 |
|:--:|------|:--:|------|
| 85-100 | 优秀 | 绿 | 推荐使用 |
| 65-84 | 可用 | 蓝 | SSR 够用 |
| 45-64 | 勉强 | 黄 | 建议换/配门控 |
| <45 | 不可用 | 红 | 换模型 |

## Dashboard 展示

```
模型面板
┌─────────────────────────────────────────┐
│ [总评分 68] [embed裸分 52] [门控裸分 88]  │
│                                         │
│ bge-large-zh-v1.5 · 1024维 · Ollama     │
│ 30信号: 26进top-12, 14进top-3           │
│ 20噪音: 15静默, 5误推                   │
│                                         │
│ 基于 50 条固定测试 · 实际体验可能不同    │
│ [刷新评分]                               │
└─────────────────────────────────────────┘
```

三个 tab 各自显示对应公式的详细分解。Dashboard 底部小字："基于 50 条固定基准测试，不同使用场景结果可能不同。"

## 基准脚本

`tests/ssr_scoring_benchmark.py`，三种模式 + 50 条测试数据内置：

```bash
python3 tests/ssr_scoring_benchmark.py --mode total      # 总评分
python3 tests/ssr_scoring_benchmark.py --mode embedding  # 裸分
python3 tests/ssr_scoring_benchmark.py --mode gate       # 门控分
python3 tests/ssr_scoring_benchmark.py --mode all        # 三个一起跑
```

输出 JSON → Dashboard `/api/scores` 读取 → 前端渲染。

## model_scores.json

```json
{
  "bge-large-zh-v1.5": {
    "total": 68, "embedding_bare": 52,
    "signal_hit": 26, "signal_top3": 14, "noise_silent": 15,
    "last_benchmark": "2026-06-21"
  },
  "qwen2.5:3b": {
    "gate": 88, "noise_correct": 18, "signal_correct": 28,
    "last_benchmark": "2026-06-21"
  },
  "deepseek-chat": {
    "gate": 72, "noise_correct": 14, "signal_correct": 25,
    "last_benchmark": "2026-06-21"
  }
}
```

## 实施顺序

1. 重启 Hermes，配门控，跑 15 条手动验证存活
2. 写 `ssr_scoring_benchmark.py`（50 条内置）
3. 跑三个分存 `model_scores.json`
4. Dashboard 加三分视图 + `/api/scores`
5. 前端渲染

## 不上限、不造假、不隐藏

- 分数是实测值——"qwen 比 bge 好"由 52→82 的差距说话
- 每个指标可追溯——Dashboard 展开看逐条命中/漏过
- 换模型 → 跑脚本 → 分更新 → 旧分存档
- 小字免责——这是基准，不是真理
