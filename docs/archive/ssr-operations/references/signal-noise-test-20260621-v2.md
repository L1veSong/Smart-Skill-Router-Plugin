# SSR v1.7.0 信号/噪音实测（2026-06-21 第二轮）

## 配置

- A层: 100条规则（含死引用已清理）
- Embedding: bge-large-zh-v1.5 / 1024维 / 387 skill
- B层: main (DeepSeek v4-pro) / qwen3.5:9b
- 意图门控: ollama(qwen2.5:3b,5s)→main(10s)→放行
- 噪音白名单: 新增6条正则（免调LLM）

## 10 信号

| # | 消息 | D档精准 | P/B档救援 | 评价 |
|:--:|------|:--:|------|------|
| 1 | 帮我设计一个暗色仪表盘 | 0/1 | P: ui-ux-pro-max等 ✅ | 🟡 P档方向对，D档缺规则 |
| 2 | Python代码报KeyError怎么调试 | 2/5 | — | 🟡 diagnose+systematic-debugging ✅ |
| 3 | 分析茅台均线走势 | 4/4 | P: finance-news-analyzer ✅ | 🟢 金融规则最成熟 |
| 4 | 北京自驾到南昌路线规划 | 0/1 | P: road-trip-planner ✅ | 🟡 D档缺自驾规则 |
| 5 | 帮我写论文文献综述 | 7/8 | P: nature-writing等 ✅ | 🟢 学术规则最成熟 |
| 6 | 画一个ASCII猫咪 | 0/0 | P: 视觉设计噪音 | ⚠️ ascii-art未安装 |
| 7 | 部署网站到Vercel | 0/3 | P: vercel-optimize ✅ B: vercel-cli-with-tokens ✅ | 🔴 deploy-to-vercel失踪 |
| 8 | 生成季度PPT汇报 | 0/1 | P: pptx ✅ | 🔴 pptx在P档，D档缺规则 |
| 9 | 画中国地图显示GDP | 2/2 | — | 🟢 精准 |
| 10 | 发微信给朋友说晚点到 | 0/1 | B: imessage/wechat-desktop-send ✅ | 🔴 正确答案在B档 |

**综合**: 2🟢 + 3🟡 + 3🔴 + 1⚠️

## 3 噪音（当前门控）

| # | 消息 | 结果 | 根因 |
|:--:|------|:--:|------|
| 1 | 嗯嗯 | ❌ 漏过 | len<4 本应拦截但LLM放行(需验证) |
| 2 | 谢谢你的帮助 | ❌ 漏过 | LLM门控误判YES |
| 3 | 好的我明白了 | ❌ 漏过 | LLM门控误判YES |

噪音 0/3 被拦截。LLM门控对中文礼貌语几乎100%误判。

## 噪音白名单修复（v1.7.0 本次新增）

9条正则，免调LLM，零token消耗：

```
^[嗯哦啊噢好对行可]{1,3}   → 嗯/哦/好
^(谢谢|感谢).{0,8}$         → 谢谢你的帮助
^(好的|明白了)...(明白了|知道了) → 好的我明白了
^(你觉得呢|你认为呢)          → 反问
^(今天|今天天气|天气)         → 天气闲聊
^(哈哈|嘿嘿|嘻嘻)            → 纯语气
```

## 系统级问题

1. **auto-gen规则质量差**: `they`/`will`/`actions`等无意义单词
2. **微信/消息类零A层覆盖**: imessage/wechat全靠B层embedding
3. **视觉类关键词污染**: "画"/"设计"招来design-taste全家桶
4. **dead引用自动清理**: 启动+热删除已内置，零硬编码
