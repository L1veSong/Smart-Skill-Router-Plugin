# DeepSeek-Reasonix — Hermes 编程子 Agent 集成

> 创建日期: 2026-06-09 | 相关: SSR Phase 3（编程意图 → 推荐 Reasonix）

## 基本信息

| 项目 | 值 |
|-----|-----|
| 仓库 | `esengine/DeepSeek-Reasonix` |
| 安装 | `npm i -g reasonix` |
| 版本 | v0.53.2 (CLI) / desktop-v1.3.0 (GUI) |
| 许可 | MIT |
| 后端 | DeepSeek API（共用现有 key） |

## 运行方式

```bash
# 非交互式（Hermes 调用的方式）
DEEPSEEK_API_KEY=sk-xxx reasonix run "编程任务描述"

# 交互式 TUI
reasonix chat
```

## 基准测试结果（2026-06-09）

**任务:** Python LRU Cache（泛型、线程安全、O(1)、含单元测试）

| 维度 | Reasonix | Hermes (DeepSeek v4-pro) |
|-----|----------|--------------------------|
| 实现 | 手写双向链表 + 哈希表 120 行 | OrderedDict 30 行 |
| 测试 | 8 个用例（含并发测试） | 无 |
| `__slots__` 优化 | ✅ | ❌ |
| 成本 | $0.000665 | 未单独计算（同 API key） |
| 缓存命中 | 95.4% | 无此机制 |

**结论:** Reasonix 编程更强（手写实现、自带测试、内存优化），Hermes 更 Pythonic（用标准库取巧、代码少但无测试）。互补。

## 适用场景

| 场景 | 用谁 | 原因 |
|-----|------|------|
| 算法/数据结构实现 | Reasonix | 它会手写核心逻辑 |
| API/后端/数据库 | Reasonix | 专为编程优化 |
| 网站/UI/前端 | Hermes | 需要 40 个 design skill |
| 写 Skill 文件 | Hermes | 需要 writing-skills + authoring |
| 混合（代码+UI） | Reasonix 出代码核心 → Hermes 润色 UI/UX | 各取所长 |

## 局限性

- `run` 是单次非交互式——一次任务出一次代码，不能多轮打磨
- 不认 Hermes skill——没有 design taste
- macOS 需要 `DEEPSEEK_API_KEY` 环境变量或先跑一次 `reasonix chat` 保存密钥

## API Key 配置

```bash
# 方法 1: 环境变量
export DEEPSEEK_API_KEY=sk-xxx

# 方法 2: 交互式保存
reasonix chat  # 首次会提示输入 key，保存到 ~/.config/reasonix/
```

**从 Hermes config 提取 key 传给 Reasonix:**
```python
import yaml, subprocess, os
from pathlib import Path
c = yaml.safe_load(Path.home().joinpath('.hermes','config.yaml').read_text())
k = c['model']['api_key']
os.environ['DEEPSEEK_API_KEY'] = k
subprocess.run(['reasonix', 'run', '编程任务'], ...)
```
