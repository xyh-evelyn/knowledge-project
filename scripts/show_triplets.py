import json
from collections import Counter

p = 'triplets_final.json'
with open(p, 'r', encoding='utf-8') as f:
    data = json.load(f)

total_records = len(data)

total_triplets = 0
rel_counter = Counter()
for item in data:
    triplets = item.get('triplets') or []
    if isinstance(triplets, list):
        total_triplets += len(triplets)
        for tri in triplets:
            try:
                rel = str(tri[1])
                rel_counter[rel] += 1
            except Exception:
                continue

print(f"总记录数: {total_records}")
print(f"总三元组数: {total_triplets}")
print('\n关系谓词频次 (前10):')
for rel, c in rel_counter.most_common(10):
    print(f"  {rel}: {c}")

print('\n前 5 条样本:')
for i, item in enumerate(data[:5], 1):
    print('---')
    print(f"样本 #{i}  ID: {item.get('id')}")
    text = item.get('text','').replace('\n',' ')
    print('文本预览:', text[:200])
    triplets = item.get('triplets') or []
    print(f'三元组数: {len(triplets)}')
    for t in triplets[:10]:
        print('  -', t)
