# Skill 元数据覆盖率扫描 (2026-06-23)

> 触发：讨论 SSR embedding 信号提升时，提出"利用 skill 自带 tag/category"方案。用户说「先扫再说」。
> 结论：方案当场淘汰——97% 的 skill 没有任何元数据。

## 扫描数据

```
总 skill: 401
有 tag:      11 (3%)
有 category:  6 (1%)
至少一个有:  13 (3%)
都没有:     388 (97%)
```

## 扫描脚本

```python
import json, os
from pathlib import Path

emb = json.load(open(os.path.expanduser('~/.hermes/plugins/ssr/embeddings.json')))
tags_found = set()
cats_found = set()
no_meta = []

for name in emb.keys():
    found_tag = False
    found_cat = False
    for base in [Path.home()/'.hermes'/'skills', Path.home()/'.agents'/'skills']:
        for md in base.rglob(f'{name}/SKILL.md'):
            text = md.read_text()
            in_front = False
            for line in text.split('\n'):
                if line.strip() == '---':
                    if not in_front: in_front = True; continue
                    else: break
                if in_front:
                    if 'tags:' in line and line.strip() != 'tags: []':
                        found_tag = True
                    if 'category:' in line:
                        found_cat = True
            break
    if not found_tag and not found_cat:
        no_meta.append(name)
    if found_tag: tags_found.add(name)
    if found_cat: cats_found.add(name)

print(f'有 tag: {len(tags_found)}')
print(f'有 category: {len(cats_found)}')
print(f'都没有: {len(no_meta)} ({len(no_meta)/len(emb)*100:.0f}%)')
```

## 教训

1. **任何依赖"外部数据已存在"的方案，先扫描再设计。** 看几个知名 skill 有元数据 ≠ 大部分都有。
2. Hermes skill 生态中 frontmatter 的 tag/category 极少被填写——不能作为优化方案的数据源。
3. 不扫就设计 = 在沙子上盖楼。
