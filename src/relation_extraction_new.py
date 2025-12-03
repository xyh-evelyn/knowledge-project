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
CORE_CONCEPT = "本土设计"

SYSTEM_PROMPT = f"""
你是一个城市规划专家，专注于构建关于【{CORE_CONCEPT}】的知识图谱。
你的目标是解决“数据孤岛”问题，确保提取出的实体尽可能连接到核心网络中。

任务规则：
1. 分析原文和已提取的实体。
2. 提取原文中明确的实体间关系（如：[政府, 推广, 绿色建筑]）。
3. 【关键步骤】：必须尝试寻找实体与核心概念【{CORE_CONCEPT}】之间的关系。
   - 如果原文提到某地正在实施规划，且上下文隐含这是为了{CORE_CONCEPT}，请生成 <地点, 实施, {CORE_CONCEPT}>。
   - 如果某概念属于{CORE_CONCEPT}的一部分，请生成 <概念, 属于, {CORE_CONCEPT}>。
4. 关系谓词不限于“规划活动”，可以使用：包含、属于、位于、促进、阻碍、相关于、旨在实现。
5. 仅输出 JSON 数组格式。
"""

def call_llm(messages, model=None, max_retries=5):
    if OpenAI is None:
        raise RuntimeError('openai package not installed')
    
    api_key = os.getenv('GRAPHRAG_CHAT_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('请设置环境变量')
    
    api_base = os.getenv('GRAPHRAG_API_BASE')
    model = model or os.getenv('GRAPHRAG_CHAT_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-4o')
    
    client = OpenAI(api_key=api_key, base_url=api_base) if api_base else OpenAI(api_key=api_key)
    
    attempt = 0
    while True:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
            return response.choices[0].message.content
        except Exception as e:
            attempt += 1
            if attempt >= max_retries:
                return "[]"
            time.sleep(1 * (2 ** (attempt - 1)))

def extract_json_array(s):
    s = s.strip()
    # 清理 Markdown
    s = re.sub(r'^```json', '', s, flags=re.MULTILINE)
    s = re.sub(r'^```', '', s, flags=re.MULTILINE)
    
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r'\[\s*\[.*\]\s*\]', s, re.S) # 寻找 [[...]]
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # 尝试寻找单层数组并转换
    m2 = re.search(r'\[.*\]', s, re.S)
    if m2:
        try:
            data = json.loads(m2.group(0))
            if data and not isinstance(data[0], list):
                return [data] # 修正格式
            return data
        except Exception:
            pass
    return []

def build_messages(text, entities):
    # 扁平化实体列表，方便 prompt 阅读
    flat_entities = []
    for k, v in entities.items():
        if isinstance(v, list):
            flat_entities.extend(v)
    
    # 过滤掉空的实体列表
    if not flat_entities:
        return None

    ent_str = ", ".join(flat_entities)
    
    user_prompt = (
        f"核心概念：【{CORE_CONCEPT}】\n"
        f"原文：\n{text}\n\n"
        f"已识别实体：[{ent_str}]\n\n"
        f"请提取三元组，格式为 [[Head, Relation, Tail]]。\n"
        f"特别注意：如果实体与【{CORE_CONCEPT}】有隐含关联，请务必显式生成一条包含“{CORE_CONCEPT}”作为头实体或尾实体的三元组，以消除孤岛。"
    )
    
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}]

def run(input_json, output_json, model=None):
    if not os.path.exists(input_json):
        print(f"错误：找不到输入文件 {input_json}")
        return

    with open(input_json, 'r', encoding='utf-8') as f:
        items = json.load(f)

    all_triplets = []
    
    print(f"开始关系抽取，策略：Hub-and-Spoke (围绕 {CORE_CONCEPT})...")

    for it in tqdm(items, desc='Relation Extraction'):
        text = it.get('text')
        entities = it.get('entities')
        
        # 如果没有实体，跳过
        if not any(entities.values()):
            continue
            
        messages = build_messages(text, entities)
        if messages is None:
            continue

        resp = call_llm(messages, model=model)
        triplets = extract_json_array(resp)
        
        # --- 后处理优化：强制连接孤岛 ---
        # 如果 LLM 返回空，或者没有包含核心概念，我们人工通过启发式规则补充一条
        # 只有当确实存在实体时才补充
        has_core_link = False
        flat_entities = []
        for cat, ent_list in entities.items():
            flat_entities.extend(ent_list)

        for t in triplets:
            if CORE_CONCEPT in t[0] or CORE_CONCEPT in t[2]:
                has_core_link = True
                break
        
        # 如果没有找到核心连接，且有提取到“规划概念”或“行动”，强制连接第一个重要实体
        if not has_core_link and flat_entities:
            # 优先连接 Concept 或 Location
            candidates = entities.get("Concept", []) + entities.get("Location", [])
            if candidates:
                # 补充一个弱连接，保证图谱连通
                forced_triplet = [candidates[0], "相关于", CORE_CONCEPT]
                triplets.append(forced_triplet)

        all_triplets.append({"id": it.get('id'), "text": text, "triplets": triplets})

    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_triplets, f, ensure_ascii=False, indent=2)
    print('关系抽取完成。已保存至', output_json)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', default='entities_extracted.json')
    p.add_argument('--output', '-o', default='triplets_final.json')
    p.add_argument('--model', '-m', default=None)
    args = p.parse_args()
    run(args.input, args.output, model=args.model)

if __name__ == '__main__':
    main()
