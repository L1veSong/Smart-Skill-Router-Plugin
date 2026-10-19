#!/usr/bin/env python3
"""SSR 三方案实测对比脚本
用法: python3 compare_pipelines.py
需要: Ollama (bge-large-zh-v1.5), DeepSeek API key (.env)"""
import json, re, time, yaml
from pathlib import Path
import httpx

SSR_DIR = Path.home() / '.hermes/plugins/ssr'
with open(SSR_DIR / 'a_rules.json') as f: A_RULES = json.load(f)
with open(SSR_DIR / 'embeddings.json') as f: EMB = json.load(f)

SKILL_INDEX = {}
for md in Path.home().joinpath('.hermes/skills').rglob('SKILL.md'):
    try:
        c = md.read_text()
        nm = re.search(r'^name:\s*(.+)$', c, re.MULTILINE)
        dm = re.search(r'^description:\s*(.+)$', c, re.MULTILINE)
        if nm: SKILL_INDEX[nm.group(1).strip()] = dm.group(1).strip()[:100] if dm else ''
    except: pass

KEY = ""
with open(Path.home() / '.hermes/.env', 'rb') as f:
    for line in f:
        if b'DEEPSEEK_API_KEY' in line:
            KEY = line[line.index(b'=')+1:].strip().decode()
            break

with open(Path.home() / '.hermes/config.yaml') as f: CFG = yaml.safe_load(f)
MODEL = CFG['model']['default']
API_URL = f"{CFG['model']['base_url'].rstrip('/').removesuffix('/v1')}/v1/chat/completions"

NOISE = [r'^[嗯哦啊噢好对行可]{1,3}[.!~。！～]*$', r'^(谢谢|感谢|多谢)[你您]?[.!~。！～]*$', r'^(好的|明白了|知道了|懂了|收到|OK|ok)[.!~。！～]*$']

def call_llm(p, mt=300):
    r = httpx.post(API_URL, headers={'Authorization': f'Bearer {KEY}', 'Content-Type': 'application/json'},
        json={'model': MODEL, 'messages': [{'role': 'user', 'content': p}], 'max_tokens': mt, 'temperature': 0}, timeout=30)
    return r.json()['choices'][0]['message']['content'] if r.status_code==200 else f"ERR{r.status_code}"

def is_noise(msg): return any(re.match(p, msg.strip()) for p in NOISE)

def emb_match(msg, n=8):
    r = httpx.post('http://localhost:11434/api/embeddings', json={'model': 'bge-large-zh-v1.5', 'prompt': msg}, timeout=10)
    if r.status_code!=200: return []
    q = r.json()['embedding']
    sc = []
    for nm, e in EMB.items():
        if 'embedding' not in e: continue
        ev = e['embedding']; dot = sum(a*b for a,b in zip(q,ev)); n1 = sum(a*a for a in q)**0.5; n2 = sum(b*b for b in ev)**0.5
        s = dot/(n1*n2) if n1*n2>0 else 0
        if s>=0.35: sc.append((nm,s))
    sc.sort(key=lambda x:-x[1])
    return sc[:n]

def slist(skills):
    return '\n'.join([f"- {n}: {SKILL_INDEX.get(n,'')[:80]}" for n in skills]) if skills else '(无)'

# Pipeline 1: current (emb → LLM filter)
def p1(msg):
    if is_noise(msg): return ("NOISE",[])
    emb = emb_match(msg); cands = [n for n,s in emb]
    if not cands: return ("NO_CAND",[])
    prompt = f"技能路由器。候选:\n{slist(cands)}\n消息:「{msg}」\n返回JSON: {{\"relevant\":[\"名\"]}}。无关空数组。只JSON。"
    resp=call_llm(prompt,200)
    try: m=re.search(r'\{[^}]+\}',resp); hits=json.loads(m.group()).get('relevant',[]) if m else []
    except: hits=[]
    return (f"{len(hits)}个:{','.join(hits[:3])}" if hits else "0个", hits)

# Pipeline 2: pure LLM
def p2(msg):
    if is_noise(msg): return ("NOISE",[])
    prompt = f"技能路由器。可用技能:\n{slist(list(SKILL_INDEX.keys()))}\n消息:「{msg}」\n闲聊/感叹/问候->{{\"need_skill\":false,\"relevant\":[]}}\n需要技能->{{\"need_skill\":true,\"relevant\":[\"名1\",\"名2\"]}}\n只JSON,最多5个。"
    resp=call_llm(prompt,400)
    try: m=re.search(r'\{[^}]+\}',resp); r=json.loads(m.group()) if m else {}
    except: return ("PARSE",[])
    if not r.get('need_skill',False): return ("NO_NEED",[])
    return (f"{len(r.get('relevant',[]))}个", r.get('relevant',[]))

# Pipeline 3: LLM+emb
def p3(msg):
    if is_noise(msg): return ("NOISE",[])
    emb = emb_match(msg,8); ctx = slist([n for n,s in emb])
    prompt = f"技能路由器。参考(embedding结果,仅供参考):\n{ctx}\n消息:「{msg}」\n闲聊/感叹/问候->{{\"need_skill\":false,\"relevant\":[]}}\n需要技能->{{\"need_skill\":true,\"relevant\":[\"名1\",\"名2\"]}}\n参考上下文但不盲从。只JSON,最多5个。"
    resp=call_llm(prompt,400)
    try: m=re.search(r'\{[^}]+\}',resp); r=json.loads(m.group()) if m else {}
    except: return ("PARSE",[])
    if not r.get('need_skill',False): return ("NO_NEED",[])
    return (f"{len(r.get('relevant',[]))}个", r.get('relevant',[]))

TESTS = [
    ("嗯","noise"),("好的","noise"),
    ("帮我写一篇学术论文","rec",["research","paper"]),
    ("这段代码有bug帮我修","rec",["debug","diagnose"]),
    ("推荐一只A股","rec",["finance","stock","tushare"]),
    ("画一个好看的登录页面","rec",["ui","design","frontend"]),
    ("帮我部署到Vercel","rec",["deploy","vercel"]),
    ("女朋友生气了怎么办","rec",["relationship","conflict"]),
    ("今天天气真好啊","noise"),("你吃饭了吗","noise"),
    ("做一份PPT","rec",["powerpoint","pptx"]),
    ("ASCII画一只猫","rec",["ascii","art"]),
    ("新疆旅游攻略","rec",["travel","trip"]),
]

print(f"{'消息':<22} {'预期':<6} | {'当前管线':<28} | {'纯LLM一次':<28} | {'LLM+emb':<28}")
print("-"*120)
st = {k:{'nok':0,'nwr':0,'hit':0,'mis':0,'wr':0} for k in ['p1','p2','p3']}

for tx in TESTS:
    msg, exp = tx[0], tx[1]; exp_kw = tx[2] if len(tx)>2 else []
    r1s,r1h = p1(msg); r2s,r2h = p2(msg); r3s,r3h = p3(msg)
    for pk,rh in [('p1',r1h),('p2',r2h),('p3',r3h)]:
        if exp=='noise':
            if isinstance(rh,list) and len(rh)==0: st[pk]['nok']+=1
            else: st[pk]['nwr']+=1
        else:
            if isinstance(rh,list) and len(rh)>0:
                hn=' '.join(rh).lower()
                if any(kw.lower() in hn for kw in exp_kw): st[pk]['hit']+=1
                else: st[pk]['wr']+=1
            else: st[pk]['mis']+=1
    print(f"{msg:<22} {exp:<6} | {r1s:<28} | {r2s:<28} | {r3s:<28}")

n_noise=sum(1 for t in TESTS if t[1]=='noise'); n_rec=sum(1 for t in TESTS if t[1]=='rec')
print("\n--- 统计 ---")
for pk,nm in [('p1','当前管线'),('p2','纯LLM一次'),('p3','LLM+emb')]:
    s=st[pk]; w=s['mis']+s['wr']+s['nwr']
    print(f"{nm}: 噪音={s['nok']}/{n_noise} 命中={s['hit']}/{n_rec} 漏={s['mis']} 误={s['wr']} 噪音误={s['nwr']} 准确率={(len(TESTS)-w)/len(TESTS)*100:.0f}%")
