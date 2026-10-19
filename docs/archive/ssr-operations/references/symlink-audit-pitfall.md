# 审计坑点：creative 目录是符号链接（2026-08-03 发现）

`~/.hermes/skills/creative` 是指向 `~/.cc-switch/skills/creative` 的符号链接（`hyperframes-creative -> ~/.agents/skills/` 同理）。

## 坑

os.walk / find 默认**不跟随** symlink → 磁盘遍历会漏掉 creative 下全部 skill：
cinema-dna-21x9x3、zy-cinematic-realism、culture-fragment-poster-engine、
fantasy-life-force-portrait-photography、fantasy-photography-simulation、
regional-culture-poster、oriental-editorial-poster 等 ~10 个。

后果：审计"死引用"时误报这些 skill 不存在 → 错误删除规则。

## 正确做法

1. 先 `ls -la ~/.hermes/skills/ | grep creative` 查 symlink
2. 死引用验证用 `grep -rl '^name: <skill>$' ~/.hermes/skills ~/.agents/skills`
   （grep -r 会跟随 symlink），或 Python `os.walk(followlinks=True)`
3. 这些 skill 真实存在且 Hermes 可加载，SSR manual 规则引用它们**不是**死引用

## 附加验证结论（2026-08-03）

SSR 全量审计：a_rules.json 296→293 条（删 2 条 auto 垃圾 Reviewtheconversation*、
合并 to-tickets 重复、修复 animejs→animation-engines、react-bits→gsap-react、
travel→travel-skill、auto-editor/losslesscut/shotcut→video-toolchain、
whisperx→whisper）。测试 22/0/4 全绿。
