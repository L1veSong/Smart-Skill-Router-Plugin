# 域扩张测试套件 (2026-07-23)

v2.5.0 域扩张 (16→32域) 后建立的标准测试套件。

## 核心测试 (25条)

覆盖所有 32 域的典型触发词。每条验证: 命中域 = 预期域，无跨域污染。

```
想出去转转          → travel
电影那种感觉        → 生图
帮我写代码          → (无命中)
新疆玩几天拍照片    → travel, 生图
做个短视频          → 视频
股票行情分析        → 金融
文献综述            → 学术
清理磁盘            → storage
AI生成音乐          → 音乐
Claude帮我写代码    → agent
清理Mac磁盘         → storage, macos
今天天气            → travel
帮我做个PPT         → docs
快速做个原型验证    → planning
帮我调试这个bug     → code-quality
验证一下是不是真完成了 → code-quality
国内用什么AI生成图片 → china-services
在备忘录记一下      → macos
附近有什么好吃的    → macos
找个表情包          → media
整理一下Obsidian笔记 → obsidian
元宝那个群          → messaging
微调一个模型        → ml
搭个Minecraft服务器  → gaming
Figma设计系统       → 设计
```

## 噪音测试 (10条)

验证闲聊/问候不触发任何域:

```
今天吃什么
你好
谢谢
帮我看看
怎么样
好的
行
OK
继续
不对
```

全部应返回空。

## 回归验证方法

```python
import json, re
with open('a_rules.json') as f: rules = json.load(f)
for msg in tests:
    hit = set()
    for regex, data in rules.items():
        if re.search(regex, msg, re.IGNORECASE):
            hit.add(data.get('domain','(none)'))
    # compare hit vs expected
```
