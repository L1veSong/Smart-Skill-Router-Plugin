# 本地模型 RAM 约束

> 2026-06-22: qwen3.5:9b (6.6GB) 在 8GB Mac 上触发 swap → 整机卡死。

## 8GB Mac 模型上限

总内存 8GB → OS+应用占 3-5GB → 可用 3-5GB。
Q4 量化模型实际占用 ≈ 参数量 × 0.7。

| 模型 | Q4 大小 | 8GB 适配 |
|------|---------|:--:|
| qwen3.5:9b | 6.6GB | ❌ |
| qwen3.5:4b | 3.5GB | ⚠️ 边缘 |
| qwen3.5:2b | ~2GB | ✅ |
| bge-large-zh-v1.5 | 202MB | ✅ |

## 诊断

```bash
ollama ps              # 当前加载
vm_stat | head -8      # 内存压力
sysctl hw.memsize      # 总内存
```
