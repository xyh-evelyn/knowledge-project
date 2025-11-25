"""关系抽取：基于实体判断文本中实体间是否存在 Planned activity 关系

用法示例:
    python relation_extraction.py --input entities_extracted.json --output triplets_final.json
"""
import os
import json
import time
import argparse
import re
from tqdm import tqdm

try:
    from openai import OpenAI
except Exception:
    OpenAI = None


SYSTEM_PROMPT = (
    "你是一个城市规划专家。给定原文与已抽取实体，请判断哪些实体之间存在“规划活动”(Planned activity)关系，"
    "并按 [主语, 谓语, 宾语] 格式返回三元组列表。只输出 JSON 数组。"
)


def call_llm(messages, model=None, max_retries=5):
    if OpenAI is None:
        raise RuntimeError('openai package not installed')
    
    api_key = os.getenv('GRAPHRAG_CHAT_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('请设置环境变量 GRAPHRAG_CHAT_API_KEY 或 OPENAI_API_KEY')
    
    api_base = os.getenv('GRAPHRAG_API_BASE')
    model = model or os.getenv('GRAPHRAG_CHAT_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
    
    client = OpenAI(api_key=api_key, base_url=api_base) if api_base else OpenAI(api_key=api_key)
    
    attempt = 0
    while True:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0,
                max_tokens=1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            attempt += 1
            if attempt >= max_retries:
                raise
            time.sleep(1 * (2 ** (attempt - 1)))


def extract_json_array(s):
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r'\[\s*\[.*\]\s*\]', s, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    raise ValueError('无法解析 LLM 输出为三元组列表')


def build_messages(text, entities):
    ent_summary = json.dumps(entities, ensure_ascii=False)
    user = (
        f"原文：\n{text}\n\n已提取实体：{ent_summary}\n\n任务：请找出所有由“规划活动”(Planned activity)连接的主-谓-宾三元组。"
        "仅输出 JSON 数组，例如 [[\"政府\", \"加强\", \"基础设施建设\"]]。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def run(input_json, output_json, model=None):
    with open(input_json, 'r', encoding='utf-8') as f:
        items = json.load(f)

    all_triplets = []
    for it in tqdm(items, desc='Relation Extraction'):
        text = it.get('text')
        entities = it.get('entities')
        messages = build_messages(text, entities)
        resp = call_llm(messages, model=model)
        try:
            triplets = extract_json_array(resp)
        except Exception as e:
            triplets = {"error": str(e), "raw": resp}
        all_triplets.append({"id": it.get('id'), "text": text, "triplets": triplets})

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_triplets, f, ensure_ascii=False, indent=2)
    print('Saved triplets to', output_json)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', default='entities_extracted.json')
    p.add_argument('--output', '-o', default='triplets_final.json')
    p.add_argument('--model', '-m', default=None)
    args = p.parse_args()
    run(args.input, args.output, model=args.model)


if __name__ == '__main__':
    main()
