# SSR v2.4.0-MoE 重启验证清单

> 2026-07-23 实战驱动 | 关联坑点: 格式迁移后验证所有域规则存在

## 何时使用

每次 `hermes restart` 之后，或 SSR 插件代码/a_rules.json 修改后。

## 验证脚本

```bash
bash ~/.hermes/skills/software-development/smart-skill-router/scripts/ssr-v2.4.0-moe-test.sh
```

## 三个核心指标

| # | 指标 | 预期 | 失败现象 |
|---|------|------|---------|
| 1 | 规则加载数 | 52 条 | 欠载→域覆盖不全 |
| 2 | 跨域不混杂 | "新疆玩几天拍照片"→旅行+生图各1个 | 5+ 条结果→扁平扫描未路由 |
| 3 | 代码不误推 | "帮我写代码"→无匹配 | 误推 khazix-writer→写作域规则太宽 |

## 域覆盖检查

```bash
python3 -c "
import json
from collections import Counter
with open('$HOME/.hermes/plugins/ssr/a_rules.json') as f:
    rules = json.load(f)
domains = Counter(r.get('domain','(无)') for r in rules.values())
print(f'总规则: {len(rules)} | 域: {dict(domains)}')
core = ['生图','视频','travel','写作','学术','金融','storage','map']
missing = [d for d in core if d not in domains]
if missing:
    print(f'❌ 缺失核心域: {missing}')
else:
    print('✅ 核心域全覆盖')
"
```

## 测试用例全集

### 生图域
| 输入 | 预期 |
|------|------|
| 电影那种感觉的画面 | zy-cinematic-realism |
| 做张海报 | culture-fragment-poster-engine |
| 中国风的设计 | fantasy-oriental-editorial-poster |
| 拍照片 | fantasy-photography-simulation |
| 照片能不能修好看点 | fantasy-life-force-portrait |
| 电影海报 | culture-fragment-poster-engine（不混推zy） |
| 故事板 | zy + cinema-dna + life-force（3个） |
| 城市视觉 | regional-culture-poster |
| 分镜 | zy-cinematic-realism |

### 视频域
| 输入 | 预期 |
|------|------|
| 帮我剪个视频 | video-use + openmontage |
| 视频转码 | video-transcode + video-delivery |
| 加字幕 | embedded-captions |
| 做数学动画 | manim |
| 用remotion做视频 | remotion（不混推通用编辑） |
| 做个短视频 | pixelle-video + douyin-video-transcribe |
| AI做视频 | pixelle-video + douyin-video-transcribe |
| 调色 | video-use + openmontage |

### 旅行域
| 输入 | 预期 |
|------|------|
| 想出去转转 | travel-plan-request |
| 飞过去多少钱 | travel-api |
| 那边吃啥 | travel-food-guide |
| 冷不冷 | travel-api |

### 写作域
| 输入 | 预期 |
|------|------|
| 帮我写一篇文章 | khazix-writer |
| SCI论文 | nature-writing + nature-polishing |
| 帮我写代码 | **不推**（排除验证） |

### 学术域
| 输入 | 预期 |
|------|------|
| 帮我找文献 | arxiv + nature-academic-search + survey |
| 审稿意见回复 | nature-reviewer + nature-response |
| 参考文献格式 | nature-citation + citation-check-skill |
| 深度调研 | deep-research |
| 读论文 | nature-reader |

### 金融域
| 输入 | 预期 |
|------|------|
| 帮我分析一下这只股票 | technical-analysis + tushare-finance |
| MACD金叉 | technical-analysis + tushare-finance |
| 帮我选股 | stock-screen-monitor |
| 短线打板 | short-term-trader-perspective + technical-analysis |
| 财经新闻分析 | finance-news-analyzer |

### 存储域
| 输入 | 预期 |
|------|------|
| 清理磁盘 | storage-analyzer |
| 跑一下洁癖 | neat-freak |

### 跨域
| 输入 | 预期 |
|------|------|
| 新疆玩几天拍照片 | travel-plan-request + fantasy-photography-simulation（2个） |
| 旅行摄影 | fantasy-photography-simulation + travel-plan-request（2个） |

### 排除验证（确保不误推）
| 输入 | 预期 |
|------|------|
| 帮我写代码 | 不推 |
| 帮忙写代码 | 不推 |
| 今天天气 | 不推生图/视频（可推旅行） |
| 电影那种感觉 | 不推视频/金融 |

## 2026-07-23 实战记录

### 第一轮：生图域全丢
**症状：** 重启后 33 条规则（预期 36），生图域 0 条。用户测试"电影那种感觉"→无匹配。
**根因：** v2.4.0-MoE 重构加 domain 字段时只迁移了 4 域，生图域 10 条规则未迁移。
**修复：** 从 `a_rules.json.bak.0723_full` 提取 10 条生图规则，加 `domain: "生图"`，17/17 全绿。

### 第二轮：补齐视频/金融/学术域
**症状：** 覆盖率仅 4%（4/95 功能 skill）。
**修复：** 补视频 10 条 + 金融 6 条 + 学术 7 条，总规则 29→52，覆盖 20→61 skill（64%）。
**坑点：** "做.*视频"贪心→去掉；"调色"裸词漏→补上；"拍照片"双命中→互斥设计。
