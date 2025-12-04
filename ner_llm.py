"""调用 OpenAI-compatible LLM 进行 Few-shot NER (OpenAI v1.0+ 兼容)

用法举例:
    python ner_llm.py --input processed_texts.json --output entities_extracted.json

依赖: openai>=1.0.0, tqdm
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
    "你是一个城市规划专家。请从给定文本中提取以下5类实体："
    "Location (地点)、Land use function (用地功能)、Direction (方位)、"
    "Concept (规划概念)、Planned activity (规划行动/动词)。"
)

FEW_SHOT_EXAMPLE_INPUT = (
    "Priority is given to securing development space for advanced manufacturing, strategic emerging industry, "
    "and urban industry, while promoting the construction of value innovation parks."
)

FEW_SHOT_EXAMPLE_OUTPUT = {
    "Location": [],
    "Land use function": [
        "advanced manufacturing",
        "strategic emerging industry",
        "urban industry",
        "value innovation park",
    ],
    "Direction": [],
    "Concept": [],
    "Planned activity": ["give priority to", "promote"],
}


def call_llm(prompt_messages, model=None, max_retries=5, wait_base=1.0):
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
                messages=prompt_messages,
                temperature=0,
                max_tokens=1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            attempt += 1
            if attempt >= max_retries:
                raise
            sleep = wait_base * (2 ** (attempt - 1))
            time.sleep(sleep)


def extract_json_from_text(s):
    # 尝试直接解析；如失败，尝试抓取第一对大括号或中括号
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r'\{.*\}$', s, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    m2 = re.search(r'\[\s*\[.*\]\s*\]$', s, re.S)
    if m2:
        try:
            return json.loads(m2.group(0))
        except Exception:
            pass
    # 最后尝试找到第一个 { ... }
    m3 = re.search(r'\{.*?\}', s, re.S)
    if m3:
        try:
            return json.loads(m3.group(0))
        except Exception:
            pass
    raise ValueError('无法从 LLM 响应中解析 JSON')


def build_messages(text):
    fewshot_user = f"示例输入: \"{FEW_SHOT_EXAMPLE_INPUT}\"\n示例输出(仅JSON): {json.dumps(FEW_SHOT_EXAMPLE_OUTPUT, ensure_ascii=False)}"
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": fewshot_user},
        {"role": "user", "content": f"请仅输出标准 JSON。要提取的文本：\n{text}"},
    ]
    return messages


def run(input_json, output_json, model=None):
    with open(input_json, 'r', encoding='utf-8') as f:
        items = json.load(f)

    results = []
    for it in tqdm(items, desc='NER'):
        text = it.get('text')
        messages = build_messages(text)
        resp = call_llm(messages, model=model)
        try:
            parsed = extract_json_from_text(resp)
        except Exception as e:
            parsed = {"error": str(e), "raw": resp}
        results.append({"id": it.get('id'), "text": text, "entities": parsed})

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print('Saved', len(results), 'NER results to', output_json)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', default='processed_texts.json')
    p.add_argument('--output', '-o', default='entities_extracted.json')
    p.add_argument('--model', '-m', default=None)
    args = p.parse_args()
    run(args.input, args.output, model=args.model)


if __name__ == '__main__':
    main()
