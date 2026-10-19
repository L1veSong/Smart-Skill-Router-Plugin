# SSR 与 CMG 的协作关系

> 创建于 2026-06-04，随 SSR v0.1.0

## 角色定位

| 组件 | 类型 | 职责 | 覆盖范围 |
|------|------|------|---------|
| **sentinel** task_recommendations | Plugin hook | 检测 5 种 CMG 相关任务 → 推荐 CMG 配套工具 | ralph-loop, VBC, brainstorming, TDD, diagnose |
| **SSR** (Smart Skill Router) | Plugin hook | 扫描用户消息 → 匹配全量 skill 库 → 推荐加载 | 200+ skill，零限制 |

## 不冲突，互补

```
用户说话
    ↓
sentinel pre_llm_call:
  ├─ task_recommendations → 检测"打包/写代码/调试/测试/写文章"
  │   └─ 命中 → 推荐 CMG 配套工具（如 ralph-loop + VBC）
  └─ 继续

SSR pre_llm_call:
  ├─ A 层关键词匹配 → 命中 → 推荐匹配的 skill
  ├─ B 层 LLM 语义匹配 → 命中 → 推荐匹配的 skill
  └─ 继续

两个注入可能同时出现在上下文中。不冲突——sentinel 推荐的是 CMG 质检工具，
SSR 推荐的是任务相关 skill。目的不同，用户看到的是两条互补建议。
```

## IF 与 SSR 的关系

```
用户说"帮我开发一个网站"
    ↓
SSR 注入: [SSR] 建议加载: brainstorming, ui-ux-pro-max, popular-web-designs
    ↓
AI 看到推荐 → 加载 brainstorming
    ↓
brainstorming 可能触发 IF:
    └─ IF 接管 → Phase -3 自己做完整 skill 扫描 → 输出流水线
         └─ SSR 的推荐被 IF 的输出覆盖（IF 的流水线更完整）
```

**不冲突**：SSR 是建议层（pre_llm_call），IF 是调度层（skill）。建议在前，调度在后。

## SSR 给 CMG 带来什么

- 填补了 CMG 坑点 31 的缺口：SSR 解决了"配套工具列了但 AI 不会主动提议"的问题——不只是 CMG 配套，而是全量 skill
- 与 sentinel 的 task_recommendations 互补：sentinel 继续负责 CMG 质检场景（5 种），SSR 负责广阔的任务匹配（200+ skill）
- 设计理念一致：都是 pre_llm_call 注入，不阻塞对话，崩溃降级

## 安装

SSR 需要两项配置才能激活。**关键**：B 层后端由 `b_layer.provider` 控制。不写此字段 → 默认 `main`（主模型）→ `ollama_*` 配置全部忽略。

### 方案 A：B 层用 Ollama（省钱，但 M3 8GB 可能超时）

```yaml
# config.yaml
plugins:
  enabled:
    - ssr

ssr:
  hooks:
    pre_llm_call: true
  b_layer:
    provider: ollama        # ← 必须！默认是 main，不写则 Ollama 配置全无效
    model: qwen2.5:3b
    timeout: 30             # M3 8GB 跑 20 候选 prompt 需要 30s+
  ollama_model: qwen2.5:3b
  ollama_base_url: http://localhost:11434
  ollama_timeout: 30        # 与 b_layer.timeout 保持一致
  a_rules_max: 100
  a_rules_ttl_days: 30
```

### 方案 B：B 层用主模型（贵但快，零超时风险）

```yaml
# config.yaml（b_layer 段省略即可，provider 默认 main）
ssr:
  hooks:
    pre_llm_call: true
  b_layer:
    provider: main          # 可省略，main 是默认值
  ollama_model: qwen2.5:3b
  ollama_base_url: http://localhost:11434
  ollama_timeout: 5         # 仅预热用，B 层不走 Ollama
```

### 验证 B 层实际后端

重启后查日志：

```bash
grep '插件注册完成' ~/.hermes/logs/agent.log | tail -1
# 输出示例:
# B 层: ollama/qwen2.5:3b timeout=30s   ← Ollama 后端
# B 层: main/qwen2.5:3b timeout=30s     ← 主模型后端，model 字段无意义
```

依赖 Ollama（qwen2.5:3b）。Ollama 不可用时仅 A 层工作，不报错。

## 存活验证（v0.1.0 必须）

SSR 装了≠在工作。每次会话开始或用户询问时，运行：

```bash
grep 'ssr' ~/.hermes/logs/agent.log | tail -5
```

关键字段解读：

| 字段 | 含义 | 健康值 |
|------|------|--------|
| `可用 skill: N` | SSR 扫描到的 skill 数 | >0 即正常 |
| `A 层规则: N` | 已训练的关键词规则数 | >0 才算有 A 层兜底 |
| `B 层 Ollama 调用失败` | B 层语义匹配失败 | 可接受（A 层仍工作） |

**致命组合：A 层规则 0 + B 层超时 = SSR 纯摆设。** 此时必须手动 `skill_view` 匹配 skill，不可等待 SSR。

常见失败原因及修复：

| 症状 | 原因 | 修复 |
|------|------|------|
| B 层超时 | Ollama 未启动 / timeout 太短 | `ollama serve` 或增大 `ollama_timeout` |
| A 层规则始终 0 | 从未训练过关键词 | 正常（新装），靠 B 层兜底 + 时间积累 |
| 两者都死 | A 层空 + Ollama 挂了 | 手动匹配，标记为已知限制 |

### 实战案例

**2026-06-04 #1**：用户列 5 个任务（导航栏设计/Python调试/ASCII猫咪/论文写作/茅台分析），SSR 注册 223 skill / A层 0 规则 / B层连续超时 → 产出 0 条推荐。AI 手动加载 ui-ux-pro-max、diagnose、ascii-art、technical-analysis 完成匹配。

**2026-06-04 #2（SSR 专项测试）**：用户以"帮我设计一个登录页面"+"这段代码一直报 KeyError"测试 SSR 匹配质量。发现三个问题：

1. **B 层语义匹配质量差**（qwen2.5:3b 太小）："代码报 KeyError" → 匹配到 `codebase-inspection`（LOC 统计工具），而非 `diagnose`。qwen2.5:3b 对中文调试意图的理解能力不足，会混淆"检查代码库"和"调试代码错误"。

2. **Session 缓存导致静默失败**：SSR 的 `_SESSION_CACHE` 去重机制阻止同一 session 内重复推荐同一 skill。用户从"登录页设计"切换到"KeyError 调试"后，如果 diagnose 已在前一轮被推荐过（即使在错误上下文），后续正确匹配也会被缓存拦截 → fresh 为空 → 回退到 B 层 → B 层超时 → 用户看不到任何推荐。

3. **SSR 推荐注入上下文但 AI 未展示**：SSR 通过 `{"context": rec}` 注入上下文字段，但 AI 在回复中可能跳过展示直接行动，用户看不到 `[SSR] 检测到任务需求...` 行。

## 已知坑点

### 坑点 4: B 层持续超时——config 加载失败导致 timeout fallback 到 5s（2026-06-05 发现）

**症状：** B 层全部超时（日志连续 9 次 `B 层 Ollama 调用失败（降级跳过）: timed out`），但 Ollama 本身正常（`curl api/generate` 0.5s 返回），手动小 prompt 也能 2.6s 返回。

**根因链：**
1. `_b_timeout()` 从 config 读取 `b_layer.timeout` → 如果 config 加载失败 → 回退到 `_ollama_timeout()` → 再回退到 hardcode 的 `5`
2. config 加载依赖 `from hermes_cli.config import load_config` — 如果此导入在 plugin 上下文中失败，cfg={}，timeout=5s
3. 预过滤后 prompt 仍有 ~20 候选 + 各 skill 的 description → qwen2.5:3b 在 M3 8GB 上 5s 不够
4. 重试机制（`retry=True → warmup → 重试`）也因为 timeout=5s 而失败
5. 重试的条件 `"timed out" in str(e).lower()` 可能不匹配 httpx.ReadTimeout 的实际消息 → 重试根本没触发（日志中无"冷启动重试中"）

**诊断命令：**
```bash
# 1. 确认 Ollama 健康
curl -s http://localhost:11434/api/tags | python3 -c "import json,sys; print(json.load(sys.stdin).get('models',[]))"

# 2. 看 SSR 实际 timeout 值（需要插件内加 logger.info 行）
grep 'ssr.*预热\|ssr.*timeout\|ssr.*配置' ~/.hermes/logs/agent.log | tail -5

# 3. 看 B 层命中/失败比例
grep 'B 层' ~/.hermes/logs/agent.log | awk -F'B 层' '{print $2}' | sort | uniq -c
```

**修复方向（按优先级）：**
1. 把 `_ollama_timeout()` 的 fallback 从 `5` 改成 `30`（一行 patch）
2. 在 `_match_b_layer` 中加 `logger.info("[ssr] B 层 timeout=%ds, candidates=%d", _b_timeout(), len(candidates))` 用于诊断
3. 重试条件改为 `isinstance(e, httpx.TimeoutException)` 替代字符串匹配
4. 如果 config 加载确实失败 → 查 `hermes_cli.config` 在 plugin context 是否可用

### 坑点 5: 预过滤引入的副作用——`_prefilter_skills` 内部调用 `_match_a_layer`

**症状：** `_prefilter_skills`（纯读操作）在第 494 行调用 `_match_a_layer(user_message)` 给 A 层命中的 skill 加分。但 `_match_a_layer` 会更新 `_A_RULES` 的 hits 并 `_save_a_rules()` 写磁盘。

**后果：** 一次 B 层匹配会触发两次 A 层查询：
1. `_pre_llm_call` 开头调 `_match_a_layer()` → 更新 hits + 写盘
2. `_match_b_layer` → `_prefilter_skills` → 再调 `_match_a_layer()` → 再次更新 hits + 写盘

**影响：** hits 计数翻倍、磁盘 I/O 翻倍。当前未造成功能问题，但增加了不必要的写操作。

**修复方向：** `_prefilter_skills` 改为直接读 `_A_RULES` 做关键词匹配，不调 `_match_a_layer()`（它内部会修改全局状态）。

### 坑点 6: `_b_provider()` 默认 `main`——Ollama 配置写了对但 B 层根本没用（2026-06-05 发现）

**症状：** 配置了 `ollama_model: qwen2.5:3b`、`ollama_timeout: 30`，但启动日志显示 `B 层配置: main/qwen2.5:3b`。B 层调用走 deepseek-v4-pro，不走 Ollama。用户以为 B 层用 Ollama，实际上在烧主模型 token。

**根因：** `_b_provider()`（第 81 行）默认返回 `"main"`：
```python
def _b_provider() -> str:
    return _load_ssr_config().get("b_layer", {}).get("provider", "main")
```
只有显式设置 `b_layer.provider: ollama` 才会走 Ollama。`ollama_model` / `ollama_base_url` / `ollama_timeout` 只在 `b_layer.provider == "ollama"` 时生效；`provider: main` 时全部忽略。

**启动日志中的 model 字段含义：**
- `main/qwen2.5:3b` → B 层走主模型，后面的 model 名无实际作用（主模型用自己的名）
- `ollama/qwen2.5:3b` → B 层走 Ollama，model 就是实际调用的 Ollama 模型

**正确做法：** 想让 B 层用 Ollama，必须在 config.yaml 加 `b_layer.provider: ollama`。参见上方「安装」章节的方案 A。

### 坑点 7: 重启 Hermes 前必须 kill 所有旧进程 + 卸载 launchd gateway（2026-06-05 发现）

**症状：** 修了 SSR `__init__.py` 的 `_ollama_model` 函数定义，但重启后仍是旧代码在跑。日志持续报 `name '_ollama_model' is not defined`。

**根因：** Hermes 在 macOS 上有三层保活：
1. 用户手动启动的 CLI 进程（`hermes`）
2. launchd 管理的 gateway 服务（`ai.hermes.gateway`）——kill 后自动重生
3. 可能有多个残留 CLI 进程（多次启动未关）

**正确重启流程：**
```bash
# 1. 卸载 launchd 保活（否则 gateway 杀不死）
launchctl unload ~/Library/LaunchAgents/ai.hermes.gateway.plist

# 2. 全杀所有 Hermes 进程
pkill -9 -f hermes

# 3. 确认死透
pgrep -fl hermes    # 应无输出

# 4. 重新启动
hermes &

# 5. 恢复 gateway 保活
launchctl load ~/Library/LaunchAgents/ai.hermes.gateway.plist
```

**跳过步骤 1 的后果：** gateway 被 kill 后 launchd 秒级重启 → 旧代码继续跑 → 你以为重启了其实没换进程。

### 坑点 1: Session 缓存去重太激进

**症状：** 用户在同 session 切换话题后，SSR 不再推荐之前推荐过的 skill，即使新话题也需要它。

**根因：** `_pre_llm_call` 中的 `_SESSION_CACHE` 按 session_id + skill name 去重，且仅在检测到任务切换关键词（"另外/换个/还有/也要/..."）时清缓存。用户说"这段代码一直报 KeyError"不包含这些关键词 → 缓存未清 → 即使 A 层正确匹配也被拦截。

**当前状态：** 已记录，待 SSR v0.2.0 修复。可行方向：
- 语义任务切换检测（非关键词依赖）
- 缓存过期：N 轮未命中自动过期
- 降级展示：即使已推荐过，仍展示但标注"(已推荐)"

### 坑点 2: B 层 qwen2.5:3b 语义理解不足

**症状：** 中文技术查询（"代码报错"/"KeyError"）被匹配到不相关 skill（codebase-inspection）。

**根因：** qwen2.5:3b 参数量太小，对中文技术意图的语义区分能力弱。B 层 prompt 要求从 200+ skill 中精准匹配 1-3 个，对 3B 模型要求过高。

**缓解方向：**
- 扩大 A 层关键词覆盖（减少 B 层调用）
- 升级 Ollama 模型（qwen2.5:7b 或更大）
- B 层失败时明确告知用户而非静默

### 坑点 9: A 层 100 规则积累导致全场景噪音（2026-06-09 确认）

**症状：** 重启后 A 层 100 条规则在任何消息上都命中 10+ skill，包括完全无关的（讨论 SSR 自身 → 命中 paper-spine-rewrite、openwebui-data-recovery、huashu-nuwa）。

**根因：** A 层规则关键词是宽泛单字/短语（"修复"、"配置"、"诊断"），日常对话频繁出现。100 条规则 ≈ 100 组宽泛关键词 → 几乎覆盖所有用户消息。关键词命中不受 similarity_floor 和 confidence_threshold 影响——只有 embedding 路径走阈值。

**判定：** 这是 A 层设计的固有代价（快但糙），不是 bug。AI 自行判断忽略不相关推荐即可。

**长期修复：** Phase 3 Task 3.3 混合匹配权重（embedding 权重 > 关键词权重，让精准匹配浮上来、宽泛关键词沉底）。

### 坑点 8: bge-m3 中文领域术语盲区——金融/UI 专业场景 embedding 完全失效（2026-06-09 GREEN v2）

**症状：** similarity_floor=0.35 / confidence_threshold=0.40 下，金融分析场景"分析贵州茅台的均线走势"的期望 skill（technical-analysis, tushare-finance）完全未进入 bge-m3 top-30。top-5 全是随机无关 skill（文章插图、CMG、Webhook、音乐生成）。

**根因：** bge-m3 的预训练语料对中文金融术语（均线、走势、茅台）和 UI 术语（导航栏）的语义理解不足。这些术语不在其分布中 → embedding 向量漂移到随机方向 → 余弦相似度匹配到无关 skill。

**影响：** 专业中文领域（金融、UI、法律、医疗）的 A 层 embedding 路径基本不可靠。必须靠 A 层关键词规则兜底。纯 embedding 方案对中文长尾领域不可行。

**验证数据：** 详见 `references/ssr-green-benchmark-v2.md`。

**修复方向：**
- 持续扩充 A 层中文关键词规则（金融术语、UI 组件名、学术领域词）
- bge-m3 不可替代（本地唯一可用 1024维中文模型），接受其局限
- 长期：探索 bge-m3 → bge-large 或其他中文 embedding 模型的升级路径

### 坑点 3: A 层 pattern 需要持续迭代

**已修复：** debug 类 pattern 从 `debug|修复|报错|bug|异常|不工作|调试` 扩展为 `debug|修复|报错|bug|异常|不工作|调试|KeyError|Traceback|代码.*报错|报错.*代码`

**教训：** A 层规则是静态关键词，无法覆盖所有变体。需要在使用中持续补充（用户纠正 → SSR B→A 升级 → 人工审核 pattern）。

## AI 行为规范：必须展示 SSR 推荐

**SSR 将推荐注入上下文后，AI 必须在回复中展示推荐结果。** 不能跳过直接行动。

## 基准测试

- **GREEN v1 (2026-06-04)**: 首次 SSR 安装后 5 场景测试，A 层关键词规则覆盖 → 5/5 通过
- **GREEN v1 Force (2026-06-09)**: 修复 research-paper-writing A 层缺失 → 5/5 通过。详见 SSR precision-upgrade plan 归档内的 `2026-06-09-green-force-verification.md`
- **GREEN v2 (2026-06-09)**: 新阈值 (0.35/0.40) + auto-gen 关闭 → 5/5 全通过（修正后——初版 3/5 是测试脚本用错 A 层规则格式导致的误报）。**非负优化：关键词规则兜底全部场景，embedding 弱不影响体验。** 可复现脚本：`references/ssr-green-benchmark-v2.py`。

正确行为：
```
用户: 帮我设计一个登录页面
→ SSR 注入: [SSR] 检测到任务需求，建议加载: 🔍brainstorming | 🔨ui-ux-pro-max | 🔨popular-web-designs
→ AI 回复: 先加载 SSR 推荐的 skill...（然后加载并行动）
```

错误行为：
```
用户: 帮我设计一个登录页面
→ SSR 注入上下文
→ AI 直接 clarify("这个登录页是给什么项目用的？")  ← 跳过了 SSR 展示
```
