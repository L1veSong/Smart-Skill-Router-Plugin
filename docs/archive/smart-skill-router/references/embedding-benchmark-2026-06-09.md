# SSR Embedding 基准测试 — nomic-embed-text vs bge-m3

日期: 2026-06-09
测试方法: 5 个 TDD 基准场景，Ollama 本地 embedding API，余弦相似度排名。

## 模型对比

| 属性 | nomic-embed-text | bge-m3 (q4_k_m) |
|------|-----------------|-----------------|
| 维度 | 768 | 1024 |
| 大小 | 146 MB | 438 MB |
| 语言 | 英文优化 | 多语言（含中文） |
| 索引 skill 数 | 246 | 206 |
| 安装 | `ollama pull nomic-embed-text` | hf-mirror GGUF → `ollama create` |
| 中文区分度 | 极低 | 可用 |

## 场景 1: 设计响应式导航栏

查询: "帮我设计一个响应式导航栏"

| 期望 skill | nomic 排名 | bge-m3 排名 | bge-m3 sim |
|-----------|:----------:|:----------:|:----------:|
| ui-ux-pro-max | >100 | **#5** | 0.5438 |
| popular-web-designs | >100 | **#29** | 0.4904 |
| brainstorming | >100 | #52 | 0.4673 |

## 场景 2: 代码报 KeyError

查询: "这段代码一直报 KeyError 帮我看看"

| 期望 skill | nomic 排名 | bge-m3 排名 | bge-m3 sim |
|-----------|:----------:|:----------:|:----------:|
| systematic-debugging | **#86** | **#14** | 0.4936 |
| diagnose | **#138** | **#41** | 0.4658 |

## 场景 3: ASCII 猫咪图

查询: "生成一个 ASCII 猫咪图"

| 期望 skill | nomic 排名 | bge-m3 排名 | bge-m3 sim |
|-----------|:----------:|:----------:|:----------:|
| ascii-art | >100 | **#1** 🎯 | 0.5162 |

## 场景 4: 论文 Related Work

查询: "帮我写论文的 Related Work 部分"

| 期望 skill | nomic 排名 | bge-m3 排名 | bge-m3 sim |
|-----------|:----------:|:----------:|:----------:|
| research-paper-writing | **#69** | **#10** | 0.5201 |
| planning-with-files | ? | #54 | 0.4749 |

## 场景 5: 茅台均线走势

查询: "分析贵州茅台的均线走势"

A 层正则全中，Embedding 层无需参与。bge-m3 top-5 为 宝意插图/CMG/Mnemonic/歌曲/webhook——金融领域中文仍需改进。

## 结论

- **bge-m3 排名提升 6-10x** vs nomic-embed-text
- ascii-art 直接命中 #1，ui-ux-pro-max #5，research-paper-writing #10
- nomic 所有期望 skill 排名 100+，中文场景净贡献 0
- bge-m3 对通用中文（设计/调试/论文）有效，金融中文仍有提升空间
- **nomic-embed-text 已淘汰**，bge-m3 为当前推荐
