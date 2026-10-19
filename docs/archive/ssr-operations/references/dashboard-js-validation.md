# Dashboard JS 验证两步法

> 2026-06-21 实战：Dashboard 完全空白 → 最终定位 JS 语法错误（read_file 行号污染）

## 问题表现

- Dashboard 页面空白，所有按钮/链接不响应
- `/api/stats`、`/api/model-info` 等 API 正常返回
- 浏览器 Console 有 `SyntaxError`（可能是行号残留或其他 JS 错误）

## 两步诊断

### Step 1: node --check 语法验证

```bash
python3 -c "
with open('$HOME/.hermes/plugins/ssr/dashboard.html') as f:
    h = f.read()
open('/tmp/dash_js.js','w').write(h[h.find('<script>')+8:h.rfind('</script>')])
" && node --check /tmp/dash_js.js 2>&1
```

如果报错 → 跳到 Step 2 清洗。如果通过 → JS 语法没问题，排查其他（CSS 隐藏、fetch 失败、CORS）。

### Step 2: 行号污染清洗

**根因**：`execute_code` 中用 `read_file()` 读取 HTML → 行号前缀 `NNN|NNN|` 被 `write_file` 写入文件 → JS 中出现 `575|  try{var...` → SyntaxError。

**清洗脚本**：

```python
import re
with open('dashboard.html') as f:
    html = f.read()

# 移除所有 NNN|NNN| 模式
html = re.sub(r'\d+\|\d+\|', '', html)
# 移除残留的单个 NNN|
html = re.sub(r'(?<=\n)\d+\|', '', html)

with open('dashboard.html', 'w') as f:
    f.write(html)
```

清洗后重复 Step 1 确认 `node --check` 通过。

## 预防

- `execute_code` 中读文件一律用 `open().read()`，禁止 `from hermes_tools import read_file`
- 改 HTML 后立即 `node --check` 验证 JS
- 如果必须用 `read_file` 读内容 → 只看不写，绝不用返回值做写入源
