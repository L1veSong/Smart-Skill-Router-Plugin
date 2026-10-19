# SSR 中文 GREEN 基准（30 场景）

> 用途：模型对测（非快速冒烟）。GREEN 5 是快速验证，30 场景是质量评估。
> 使用：force 模式对 a_rules.json 做关键词正则匹配，或用 Embedding 语义匹配比较模型排名。

## 测试查询（30 条中文，10 域）

| # | 域 | 查询 | 期望命中 |
|---|-----|------|---------|
| D1 | 设计 | 帮我设计一个暗色主题的仪表盘 | dashboard, ui-ux-pro-max |
| D2 | 设计 | 设计一个响应式导航栏带搜索框 | ui-ux-pro-max, frontend-design |
| D3 | 设计 | 写一个登录页面的前端代码 | frontend-design, ui-ux-pro-max |
| D4 | 调试 | Python代码报KeyError怎么调试 | diagnose, systematic-debugging |
| D5 | 调试 | 这段Node.js代码Segfault帮我看看 | diagnose, node-inspect-debugger |
| D6 | 调试 | 我的应用老是闪退怎么办 | diagnose, systematic-debugging |
| F1 | 金融 | 分析贵州茅台60日均线走势 | technical-analysis |
| F2 | 金融 | 帮我写一个股票筛选器 | stock-screen-monitor, technical-analysis |
| F3 | 金融 | 帮我检查一下这个股票的MACD金叉 | technical-analysis |
| F4 | 金融 | 今天的财经新闻有什么大事 | finance-news-analyzer |
| T1 | 旅行 | 规划从北京到南昌的自驾游路线 | road-trip-planner, travel-plan-request |
| T2 | 旅行 | 新疆伊犁有什么好吃的推荐 | travel-food-guide, travel-skill |
| T3 | 旅行 | 去大理玩三天怎么安排 | travel-skill, travel-plan-request |
| A1 | 学术 | 帮我写论文的文献综述部分 | paper-spine-research, research-paper-writing |
| A2 | 学术 | 写一篇关于深度学习的学术论文 | academic-paper, research-paper-writing |
| A3 | 学术 | 硕士论文的开题报告怎么写 | research-paper-writing, academic-paper |
| A4 | 学术 | 帮我做文献调研 | survey, paper-spine-research |
| O1 | 办公 | 生成一个季度汇报PPT | pptx |
| O2 | 办公 | 导出这份数据到Excel表格 | xlsx |
| O3 | 办公 | 把这个Word转成PDF | pdf, docx |
| M1 | 地图 | 画一张中国地图显示各省GDP | svg-geo-map, geographic-viz |
| M2 | 地图 | 帮我查一下张家界的地形图 | geographic-viz, svg-geo-map |
| S1 | 社交 | 帮我搜索Twitter上关于AI的消息 | xitter |
| S2 | 社交 | 给示例用户A发条微信 | wechat-desktop-send |
| S3 | 社交 | 给女朋友发一条iMessage | imessage |
| V1 | 视频 | 把这个视频转成逐字稿 | youtube-content |
| V2 | 视频 | 做一个人脸交换的视频 | facefusion |
| C1 | 部署 | 把我的网站部署到Vercel | deploy-to-vercel |
| C2 | 部署 | 帮我同步skill到GitHub仓库 | github-skills-sync |
| C3 | ASCII | 画一个ASCII艺术猫咪 | ascii-art, creative |

## 通过标准

- **A 层关键词**: ≥24/30（80%）通过
- **Embedding 语义 top-5**: ≥20/30（67%）通过  
- **模型对比**: 对每个模型跑完整 30 条 → 比较 top-5 命中数和平均排名

## 对测方法

```python
# 伪代码
for query in 30_queries:
    q_vec_bge = embed("bge-m3", query)      # 1024维
    q_vec_qwen = embed("qwen3-embedding", query)  # 4096维
    top5_bge = cosine_top5(q_vec_bge, index_bge)
    top5_qwen = cosine_top5(q_vec_qwen, index_qwen)
    compare(top5_bge, top5_qwen, expected[query])
```
