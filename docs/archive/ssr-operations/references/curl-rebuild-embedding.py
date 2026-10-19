#!/usr/bin/env python3
"""SSR embedding 索引手动重建脚本 (curl 版本)

当 SSR 内部 httpx 返回 404 时使用本脚本。
用法: python3 curl-rebuild-embedding.py [模型名]

默认模型: bge-large-zh-v1.5
备用: qwen3-embedding

前提: 
  1. Ollama 正在运行 (ollama list 有输出)
  2. 目标模型已安装
  3. 旧 embeddings.json 备份已存在
"""

import json, os, subprocess, time, sys, numpy as np

MODEL = sys.argv[1] if len(sys.argv) > 1 else "bge-large-zh-v1.5"
SSR_DIR = os.path.expanduser("~/.hermes/plugins/ssr")
BAK = f"{SSR_DIR}/embeddings.json.bak.{time.strftime('%m%d%H%M')}"

def embed(text):
    r = subprocess.run(['curl', '-s', '--max-time', '30',
        'http://localhost:11434/api/embeddings',
        '-d', json.dumps({"model": MODEL, "prompt": text})],
        capture_output=True, text=True, timeout=35)
    d = json.loads(r.stdout)
    if 'embedding' not in d:
        raise RuntimeError(f"API error: {d.get('error', r.stdout[:200])}")
    return np.array(d['embedding'])

# 加载旧索引获取 skill 描述列表
bak_files = sorted([f for f in os.listdir(SSR_DIR) if f.startswith('embeddings.json.bak')],
                   reverse=True)
if not bak_files:
    print("❌ 找不到 embeddings.json 备份文件。请先备份当前索引。")
    sys.exit(1)

bak_path = os.path.join(SSR_DIR, bak_files[0])
print(f"从备份读取: {bak_path}")
with open(bak_path) as f:
    old_idx = json.load(f)

print(f"Skill 总数: {len(old_idx)}")
print(f"目标模型: {MODEL}")

# 重建
start = time.time()
new_idx = {}
done = errors = 0

for name in list(old_idx.keys()):
    desc = old_idx[name].get('description', name)
    if not desc or len(str(desc)) < 3:
        desc = name
    try:
        vec = embed(str(desc))
        new_idx[name] = {
            "embedding": vec.tolist(),
            "model": MODEL,
            "description": desc,
            "dim": len(vec)
        }
        done += 1
    except Exception as e:
        errors += 1
        if errors <= 3:
            print(f"  ❌ {name}: {e}")
    if done % 100 == 0:
        print(f"  {done}/{len(old_idx)} ({time.time()-start:.0f}s)")

# 保存
out_path = f"{SSR_DIR}/embeddings.json"
with open(out_path, 'w') as f:
    json.dump(new_idx, f, ensure_ascii=False)

elapsed = time.time() - start
sz = os.path.getsize(out_path)
dim = len(new_idx[list(new_idx.keys())[0]]['embedding'])
print(f"\n✅ 完成: {done} skill, {errors} 错误, {elapsed:.0f}s")
print(f"已保存: {out_path} ({sz:,} bytes, {dim}维)")
