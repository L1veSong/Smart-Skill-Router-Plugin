# Embedding 模型列表 — 真实 Ollama 安装

> 2026-06-22: 旧版从 model_scores.json 读取预设模型列表（bge-m3, nomic等），
> 用户只装了 bge-large-zh-v1.5 却显示 4 个误导性选项。

## 修复

`get_model_info()` 改为从 `ollama list` 读取真实已安装模型:

```python
result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
for line in result.stdout.strip().split("\n")[1:]:
    parts = line.split()
    if parts:
        name = parts[0].replace(":latest", "")
        models.append({"name": name, "status": "installed"})
```

API 返回: 只显示真正已安装的模型。
Dashboard: `<datalist id="emb-ollama-list">` + `<input list="emb-ollama-list">` — 可选可输入。
