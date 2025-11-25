# """调用 OpenAI-compatible LLM 进行 Few-shot NER

# 这是 `ner_llm.py` 的 src 版本（便于模块化导入）。
# """
# import os
# import json
# import time
# import re
# from tqdm import tqdm

# try:
#     from openai import OpenAI
# except Exception:
#     OpenAI = None

# SYSTEM_PROMPT = (
#     "你是一个城市规划专家。请从给定文本中提取以下5类实体："
#     "Location (地点)、Land use function (用地功能)、Direction (方位)、"
#     "Concept (规划概念)、Planned activity (规划行动/动词)。"
# )

# FEW_SHOT_EXAMPLE_INPUT = (
#     "Priority is given to securing development space for advanced manufacturing, strategic emerging industry, "
#     "and urban industry, while promoting the construction of value innovation parks."
# )

# FEW_SHOT_EXAMPLE_OUTPUT = {
#     "Location": [],
#     "Land use function": [
#         "advanced manufacturing",
#         "strategic emerging industry",
#         "urban industry",
#         "value innovation park",
#     ],
#     "Direction": [],
#     "Concept": [],
#     "Planned activity": ["give priority to", "promote"],
# }


# def call_llm(prompt_messages, model=None, max_retries=5, wait_base=1.0):
#     if OpenAI is None:
#         raise RuntimeError('openai package not installed')
#     api_key = os.getenv('GRAPHRAG_CHAT_API_KEY') or os.getenv('OPENAI_API_KEY')
#     if not api_key:
#         raise RuntimeError('请设置环境变量 GRAPHRAG_CHAT_API_KEY 或 OPENAI_API_KEY')
#     api_base = os.getenv('GRAPHRAG_API_BASE')
#     model = model or os.getenv('GRAPHRAG_CHAT_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-4o-mini')
#     client = OpenAI(api_key=api_key, base_url=api_base) if api_base else OpenAI(api_key=api_key)
#     attempt = 0
#     while True:
#         try:
#             response = client.chat.completions.create(
#                 model=model,
#                 messages=prompt_messages,
#                 temperature=0,
#                 max_tokens=1024,
#             )
#             return response.choices[0].message.content
#         except Exception as e:
#             attempt += 1
#             if attempt >= max_retries:
#                 raise
#             sleep = wait_base * (2 ** (attempt - 1))
#             time.sleep(sleep)


# def extract_json_from_text(s):
#     s = s.strip()
#     try:
#         return json.loads(s)
#     except Exception:
#         pass
#     m = re.search(r'\{.*\}$', s, re.S)
#     if m:
#         try:
#             return json.loads(m.group(0))
#         except Exception:
#             pass
#     m2 = re.search(r'\[\s*\[.*\]\s*\]$', s, re.S)
#     if m2:
#         try:
#             return json.loads(m2.group(0))
#         except Exception:
#             pass
#     m3 = re.search(r'\{.*?\}', s, re.S)
#     if m3:
#         try:
#             return json.loads(m3.group(0))
#         except Exception:
#             pass
#     raise ValueError('无法从 LLM 响应中解析 JSON')


# def build_messages(text):
#     fewshot_user = f"示例输入: \"{FEW_SHOT_EXAMPLE_INPUT}\"\n示例输出(仅JSON): {json.dumps(FEW_SHOT_EXAMPLE_OUTPUT, ensure_ascii=False)}"
#     messages = [
#         {"role": "system", "content": SYSTEM_PROMPT},
#         {"role": "user", "content": fewshot_user},
#         {"role": "user", "content": f"请仅输出标准 JSON。要提取的文本：\n{text}"},
#     ]
#     return messages


# def run(input_json, output_json, model=None):
#     with open(input_json, 'r', encoding='utf-8') as f:
#         items = json.load(f)
#     results = []
#     for it in tqdm(items, desc='NER'):
#         text = it.get('text')
#         messages = build_messages(text)
#         resp = call_llm(messages, model=model)
#         try:
#             parsed = extract_json_from_text(resp)
#         except Exception as e:
#             parsed = {"error": str(e), "raw": resp}
#         results.append({"id": it.get('id'), "text": text, "entities": parsed})
#     with open(output_json, 'w', encoding='utf-8') as f:
#         json.dump(results, f, ensure_ascii=False, indent=2)
#     print('Saved', len(results), 'NER results to', output_json)


# if __name__ == '__main__':
#     import argparse
#     p = argparse.ArgumentParser()
#     p.add_argument('--input', '-i', default='processed_texts.json')
#     p.add_argument('--output', '-o', default='entities_extracted.json')
#     p.add_argument('--model', '-m', default=None)
#     args = p.parse_args()
#     run(args.input, args.output, model=args.model)

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

# --- 配置区 ---
# 核心概念：所有的提取工作都将围绕这个词展开
CORE_CONCEPT = "本土设计"

SYSTEM_PROMPT = f"""
你是一个城市规划与建筑领域的知识图谱专家。
你的任务是从文本中提取与核心概念【{CORE_CONCEPT}】紧密相关的实体。

请提取以下5类实体：
1. Location (地点): 与{CORE_CONCEPT}发生关联的具体场所。
2. Land use function (用地功能): 涉及{CORE_CONCEPT}的功能区。
3. Direction (方位): 空间方位。
4. Concept (规划概念): 与{CORE_CONCEPT}相关的理论、理念或专有名词。
5. Planned activity (规划行动): 针对{CORE_CONCEPT}采取的具体动作。

注意：如果实体与【{CORE_CONCEPT}】完全无关，请不要提取，以减少图谱中的噪音。
"""

FEW_SHOT_EXAMPLE_INPUT = (
    "在南沙区的规划中，我们将优先考虑融合岭南文化的本土设计元素，"
    "推广具有地域特色的绿色建筑技术。"
)

FEW_SHOT_EXAMPLE_OUTPUT = {
    "Location": ["南沙区"],
    "Land use function": [],
    "Direction": [],
    "Concept": ["岭南文化", "本土设计元素", "地域特色", "绿色建筑技术"],
    "Planned activity": ["优先考虑", "融合", "推广"]
}

def call_llm(prompt_messages, model=None, max_retries=5, wait_base=1.0):
    if OpenAI is None:
        raise RuntimeError('openai package not installed')
    
    api_key = os.getenv('GRAPHRAG_CHAT_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('请设置环境变量 GRAPHRAG_CHAT_API_KEY 或 OPENAI_API_KEY')
    
    api_base = os.getenv('GRAPHRAG_API_BASE')
    model = model or os.getenv('GRAPHRAG_CHAT_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-4o') # 建议使用强模型
    
    client = OpenAI(api_key=api_key, base_url=api_base) if api_base else OpenAI(api_key=api_key)
    
    attempt = 0
    while True:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=prompt_messages,
                temperature=0.1, # 降低随机性
                max_tokens=2048,
                response_format={"type": "json_object"} # 强制 JSON 模式（如果模型支持）
            )
            return response.choices[0].message.content
        except Exception as e:
            attempt += 1
            if attempt >= max_retries:
                print(f"Error calling LLM: {e}")
                return "{}" # 失败返回空对象
            sleep = wait_base * (2 ** (attempt - 1))
            time.sleep(sleep)

def extract_json_from_text(s):
    s = s.strip()
    # 移除可能存在的 markdown 代码块标记
    s = re.sub(r'^```json', '', s, flags=re.MULTILINE)
    s = re.sub(r'^```', '', s, flags=re.MULTILINE)
    try:
        return json.loads(s)
    except Exception:
        pass
    # 正则提取
    m = re.search(r'\{.*\}', s, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return {}

def build_messages(text):
    fewshot_user = f"示例输入: \"{FEW_SHOT_EXAMPLE_INPUT}\"\n示例输出(JSON): {json.dumps(FEW_SHOT_EXAMPLE_OUTPUT, ensure_ascii=False)}"
    
    # 增强 Prompt：在输入文本前再次强调核心概念
    user_content = (
        f"请仅输出标准 JSON。\n"
        f"当前任务的核心关注点是：【{CORE_CONCEPT}】\n"
        f"要提取的文本：\n{text}"
    )
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": fewshot_user},
        {"role": "user", "content": user_content},
    ]
    return messages

def run(input_json, output_json, model=None):
    if not os.path.exists(input_json):
        print(f"错误：找不到输入文件 {input_json}")
        return

    with open(input_json, 'r', encoding='utf-8') as f:
        items = json.load(f)

    results = []
    print(f"开始实体抽取，核心概念：{CORE_CONCEPT}...")
    
    for it in tqdm(items, desc='NER'):
        text = it.get('text')
        # 简单过滤：如果句子太短，跳过
        if len(text) < 5: 
            continue
            
        messages = build_messages(text)
        resp = call_llm(messages, model=model)
        parsed = extract_json_from_text(resp)
        
        # 验证：如果提取结果为空，记录空列表
        if not parsed:
            parsed = {"Location": [], "Land use function": [], "Direction": [], "Concept": [], "Planned activity": []}
            
        results.append({"id": it.get('id'), "text": text, "entities": parsed})

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print('实体抽取完成。已保存至', output_json)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', default='processed_texts.json')
    p.add_argument('--output', '-o', default='entities_extracted.json')
    p.add_argument('--model', '-m', default=None)
    args = p.parse_args()
    run(args.input, args.output, model=args.model)

if __name__ == '__main__':
    main()
