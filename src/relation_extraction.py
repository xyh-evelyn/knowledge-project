# """关系抽取模块（src 版本）"""
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
#     "你是一个城市规划专家。给定原文与已抽取实体，请判断哪些实体之间存在“规划活动”(Planned activity)关系，"
#     "并按 [主语, 谓语, 宾语] 格式返回三元组列表。只输出 JSON 数组。"
# )


# def call_llm(messages, model=None, max_retries=5):
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
#                 messages=messages,
#                 temperature=0,
#                 max_tokens=1024,
#             )
#             return response.choices[0].message.content
#         except Exception as e:
#             attempt += 1
#             if attempt >= max_retries:
#                 raise
#             time.sleep(1 * (2 ** (attempt - 1)))


# def extract_json_array(s):
#     s = s.strip()
#     try:
#         return json.loads(s)
#     except Exception:
#         pass
#     m = re.search(r'\[\s*\[.*\]\s*\]', s, re.S)
#     if m:
#         try:
#             return json.loads(m.group(0))
#         except Exception:
#             pass
#     raise ValueError('无法解析 LLM 输出为三元组列表')


# def build_messages(text, entities):
#     ent_summary = json.dumps(entities, ensure_ascii=False)
#     user = (
#         f"原文：\n{text}\n\n已提取实体：{ent_summary}\n\n任务：请找出所有由“规划活动”(Planned activity)连接的主-谓-宾三元组。"
#         "仅输出 JSON 数组，例如 [[\"政府\", \"加强\", \"基础设施建设\"]]。"
#     )
#     return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


# def run(input_json, output_json, model=None):
#     with open(input_json, 'r', encoding='utf-8') as f:
#         items = json.load(f)
#     all_triplets = []
#     for it in tqdm(items, desc='Relation Extraction'):
#         text = it.get('text')
#         entities = it.get('entities')
#         messages = build_messages(text, entities)
#         resp = call_llm(messages, model=model)
#         try:
#             triplets = extract_json_array(resp)
#         except Exception as e:
#             triplets = {"error": str(e), "raw": resp}
#         all_triplets.append({"id": it.get('id'), "text": text, "triplets": triplets})
#     with open(output_json, 'w', encoding='utf-8') as f:
#         json.dump(all_triplets, f, ensure_ascii=False, indent=2)
#     print('Saved triplets to', output_json)


# if __name__ == '__main__':
#     import argparse
#     p = argparse.ArgumentParser()
#     p.add_argument('--input', '-i', default='entities_extracted.json')
#     p.add_argument('--output', '-o', default='triplets_final.json')
#     p.add_argument('--model', '-m', default=None)
#     args = p.parse_args()
#     run(args.input, args.output, model=args.model)

import os
import json
import time
import argparse
import re
from tqdm import tqdm  # 进度条显示，提升用户体验

# 尝试导入OpenAI客户端（用于调用大模型），若导入失败则设为None（后续会抛出异常）
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

# --- 配置区 ---
# 核心概念（Hub）：所有关系抽取都围绕该概念展开，确保图谱连通性
CORE_CONCEPT = "本土设计"

# 系统提示词（System Prompt）：定义大模型的角色、任务目标和核心规则
SYSTEM_PROMPT = f"""
你是一个城市规划专家，专注于构建关于【{CORE_CONCEPT}】的知识图谱。
你的目标是解决“数据孤岛”问题，确保提取出的实体尽可能连接到核心网络中（核心策略：Hub-and-Spoke，以{CORE_CONCEPT}为中心枢纽）。

任务规则：
1. 分析原文和已提取的实体。
2. 提取原文中明确的实体间关系（如：[政府, 推广, 绿色建筑]），生成三元组（Head实体, Relation关系, Tail实体）。
3. 【关键步骤】：必须尝试寻找实体与核心概念【{CORE_CONCEPT}】之间的关系（消除孤岛的核心）。
   - 如果原文提到某地正在实施规划，且上下文隐含这是为了{CORE_CONCEPT}，请生成 <地点, 实施, {CORE_CONCEPT}>。
   - 如果某概念属于{CORE_CONCEPT}的一部分，请生成 <概念, 属于, {CORE_CONCEPT}>。
4. 关系谓词不限于“规划活动”，可使用：包含、属于、位于、促进、阻碍、相关于、旨在实现（支持多样化关系表达）。
5. 仅输出 JSON 数组格式（如 [[实体1, 关系, 实体2], [实体3, 关系, 核心概念]]），不添加额外文本。
"""

def call_llm(messages, model=None, max_retries=5):
    """
    调用大模型（LLM）获取关系抽取结果
    :param messages: 传给大模型的消息列表（包含system prompt、原文+实体信息）
    :param model: 指定使用的大模型（如gpt-4o），默认从环境变量读取
    :param max_retries: 调用失败后的最大重试次数（默认5次）
    :return: 大模型返回的原始文本响应（预期为JSON数组格式）
    """
    # 检查OpenAI客户端是否导入成功
    if OpenAI is None:
        raise RuntimeError('未安装openai包，请执行 pip install openai 安装')
    
    # 获取API密钥：优先读取GRAPHRAG_CHAT_API_KEY，其次读取OPENAI_API_KEY（兼容不同环境）
    api_key = os.getenv('GRAPHRAG_CHAT_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('请设置环境变量 GRAPHRAG_CHAT_API_KEY 或 OPENAI_API_KEY 以提供API密钥')
    
    # 获取API基础地址（用于自定义部署，如Azure OpenAI、本地部署等）
    api_base = os.getenv('GRAPHRAG_API_BASE')
    # 确定大模型：参数指定 > 环境变量GRAPHRAG_CHAT_MODEL > 环境变量OPENAI_MODEL > 默认gpt-4o
    model = model or os.getenv('GRAPHRAG_CHAT_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-4o')
    
    # 初始化OpenAI客户端（若有自定义API基础地址则传入）
    client = OpenAI(api_key=api_key, base_url=api_base) if api_base else OpenAI(api_key=api_key)
    
    attempt = 0  # 记录重试次数
    while True:
        try:
            # 调用大模型的聊天接口
            response = client.chat.completions.create(
                model=model,  # 指定模型
                messages=messages,  # 消息列表
                temperature=0.1,  # 低温度：降低随机性，保证关系抽取的准确性和一致性
                max_tokens=1024,  # 最大响应token数：足够容纳多个三元组
            )
            # 返回大模型的响应内容（纯文本格式，后续需解析为JSON数组）
            return response.choices[0].message.content
        except Exception as e:
            attempt += 1
            # 重试次数达到上限，返回空数组字符串（避免程序崩溃）
            if attempt >= max_retries:
                return "[]"
            # 指数退避策略：每次重试等待时间翻倍（1s → 2s → 4s...），避免频繁请求触发API限流
            time.sleep(1 * (2 ** (attempt - 1)))

def extract_json_array(s):
    """
    从大模型的文本响应中提取并解析JSON数组（适配三元组格式）
    处理场景：大模型可能返回带Markdown代码块、多余文本的响应，需清洗后解析
    :param s: 大模型返回的原始文本响应
    :return: 解析后的三元组列表（如[[实体1, 关系, 实体2], ...]，解析失败返回空列表）
    """
    # 去除文本首尾的空白字符（空格、换行、制表符等）
    s = s.strip()
    # 清理Markdown代码块标记（如```json、```），避免影响JSON解析
    s = re.sub(r'^```json', '', s, flags=re.MULTILINE)  # 移除开头的```json
    s = re.sub(r'^```', '', s, flags=re.MULTILINE)      # 移除开头的```（无json标识）
    
    try:
        # 尝试直接解析清洗后的文本为JSON数组
        return json.loads(s)
    except Exception:
        # 直接解析失败，尝试用正则提取多层数组（[[...]]格式，三元组标准格式）
        pass
    # 正则表达式：匹配最长的[[...]]格式（re.S表示.匹配换行符）
    m = re.search(r'\[\s*\[.*\]\s*\]', s, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    # 若未匹配到多层数组，尝试提取单层数组（如[实体1, 关系, 实体2]）
    m2 = re.search(r'\[.*\]', s, re.S)
    if m2:
        try:
            data = json.loads(m2.group(0))
            # 若提取到的是单个三元组（单层数组），转换为多层数组格式（统一输出结构）
            if data and not isinstance(data[0], list):
                return [data]
            return data
        except Exception:
            pass
    # 所有解析尝试失败，返回空列表
    return []

def build_messages(text, entities):
    """
    构建传给大模型的消息列表：整合原文、已提取实体，明确任务要求
    :param text: 原始文本块（来自processed_texts.json）
    :param entities: 已提取的实体字典（来自entities_extracted.json，含5类实体）
    :return: 格式化后的消息列表（无实体时返回None，跳过后续调用）
    """
    # 扁平化实体列表：将5类实体的所有值合并为一个列表，便于大模型快速查看
    flat_entities = []
    for k, v in entities.items():
        if isinstance(v, list):  # 确保值是列表类型（避免异常）
            flat_entities.extend(v)
    
    # 过滤掉空的实体列表：无实体时无需调用大模型，直接返回None
    if not flat_entities:
        return None

    # 将扁平化实体列表转换为字符串（如"南沙区, 岭南文化, 推广"）
    ent_str = ", ".join(flat_entities)
    
    # 构建用户提示词：明确核心概念、提供原文和实体，强调三元组格式和孤岛处理要求
    user_prompt = (
        f"核心概念：【{CORE_CONCEPT}】\n"
        f"原文：\n{text}\n\n"
        f"已识别实体：[{ent_str}]\n\n"
        f"请提取三元组，格式为 [[Head, Relation, Tail]]。\n"
        f"特别注意：如果实体与【{CORE_CONCEPT}】有隐含关联，请务必显式生成一条包含“{CORE_CONCEPT}”作为头实体或尾实体的三元组，以消除孤岛。"
    )
    
    # 消息列表：system prompt定义规则，user prompt提供具体数据和要求
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_prompt}]

def run(input_json, output_json, model=None):
    """
    关系抽取核心流程：读取实体数据 → 逐段调用大模型 → 解析三元组 → 后处理（强制连接核心概念）→ 保存输出
    核心策略：Hub-and-Spoke（以CORE_CONCEPT为中心枢纽，消除实体孤岛）
    :param input_json: 输入JSON文件路径（来自ner_llm.py的entities_extracted.json）
    :param output_json: 输出JSON文件路径（关系抽取结果，默认triplets_final.json）
    :param model: 指定大模型（可选，覆盖默认配置）
    """
    # 检查输入文件是否存在
    if not os.path.exists(input_json):
        print(f"错误：找不到输入文件 {input_json}")
        return

    # 读取输入文件：加载实体提取结果（每个元素包含id、text、entities）
    with open(input_json, 'r', encoding='utf-8') as f:
        items = json.load(f)

    all_triplets = []  # 存储最终的三元组结果
    
    # 打印任务信息：明确关系抽取策略（Hub-and-Spoke，围绕核心概念）
    print(f"开始关系抽取，策略：Hub-and-Spoke (围绕核心概念 {CORE_CONCEPT} 消除实体孤岛)...")

    # 遍历每个文本块，逐段提取关系（tqdm显示进度条）
    for it in tqdm(items, desc='关系抽取进度'):
        text = it.get('text')  # 原始文本块
        entities = it.get('entities', {})  # 该文本块已提取的实体字典
        
        # 如果实体字典中所有类别都是空列表，跳过当前文本块（无实体可抽取关系）
        if not any(entities.values()):
            continue
            
        # 构建传给大模型的消息列表
        messages = build_messages(text, entities)
        if messages is None:  # 无实体时跳过
            continue

        # 调用大模型，获取关系抽取响应
        resp = call_llm(messages, model=model)
        # 解析响应为三元组列表
        triplets = extract_json_array(resp)
        
        # --- 后处理优化：强制连接孤岛（核心逻辑）---
        # 目的：确保所有实体都与核心概念{CORE_CONCEPT}有连接，避免图谱中存在孤立节点
        has_core_link = False  # 标记当前三元组是否已包含与核心概念的连接
        # 扁平化实体列表：用于后续筛选候选实体
        flat_entities = []
        for cat, ent_list in entities.items():
            flat_entities.extend(ent_list)

        # 检查现有三元组是否包含与核心概念的连接（头实体或尾实体是核心概念）
        for t in triplets:
            if len(t) >= 3 and (CORE_CONCEPT in t[0] or CORE_CONCEPT in t[2]):
                has_core_link = True
                break
        
        # 如果没有找到核心连接，且存在提取到的实体，强制补充一条连接三元组
        if not has_core_link and flat_entities:
            # 优先选择“规划概念”或“地点”作为候选实体（与核心概念关联性更强）
            candidates = entities.get("Concept", []) + entities.get("Location", [])
            if candidates:  # 若有候选实体
                # 补充弱连接三元组：[第一个候选实体, "相关于", 核心概念]，确保连通性
                forced_triplet = [candidates[0], "相关于", CORE_CONCEPT]
                triplets.append(forced_triplet)

        # 将当前文本块的id、原文、提取的三元组添加到结果列表
        all_triplets.append({"id": it.get('id'), "text": text, "triplets": triplets})

    # 保存关系抽取结果到JSON文件（ensure_ascii=False保留中文，indent=2格式化输出）
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_triplets, f, ensure_ascii=False, indent=2)
    print(f'关系抽取完成！共处理 {len(all_triplets)} 个文本块，三元组结果已保存至', output_json)

def main():
    """程序主函数：解析命令行参数，启动关系抽取流程"""
    # 初始化命令行参数解析器
    p = argparse.ArgumentParser(description=f"基于大模型的关系抽取工具（核心策略：以{CORE_CONCEPT}为中心消除孤岛）")
    # 输入文件参数（默认entities_extracted.json，即ner_llm.py的输出）
    p.add_argument('--input', '-i', default='entities_extracted.json', help='输入实体JSON文件路径')
    # 输出文件参数（默认triplets_final.json，关系抽取结果）
    p.add_argument('--output', '-o', default='triplets_final.json', help='输出三元组结果JSON文件路径')
    # 模型指定参数（可选，如--model gpt-4o-mini）
    p.add_argument('--model', '-m', default=None, help='指定使用的大模型（如gpt-4o、gpt-3.5-turbo等）')
    # 解析参数
    args = p.parse_args()
    # 启动关系抽取流程
    run(args.input, args.output, model=args.model)

# 程序入口：当脚本被直接运行时，执行main函数
if __name__ == '__main__':
    main()
