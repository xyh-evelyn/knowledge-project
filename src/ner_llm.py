import os
import json
import time
import argparse
import re
from tqdm import tqdm

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# --- 配置区（移除核心概念，优化实体定义）---
# 实体分类及定义（清晰化每类实体的边界，便于LLM精准提取）
ENTITY_DEFINITIONS = {
    "Location": "地点：城市规划/建筑领域的具体地理空间，如行政区、街道、园区、地标建筑、地块等（仅提取文本中明确出现的具体名称）",
    "Land use function": "用地功能：空间的使用属性，如居住用地、商业办公、工业生产、公共绿地、文化休闲、交通枢纽等",
    "Direction": "方位：空间方位描述，如东/南/西/北、中心城区/郊区、沿江/沿湖、核心区/边缘区等",
    "Concept": "规划概念：城市规划/建筑领域的理论、理念、专有名词、技术体系等，如绿色建筑、海绵城市、 TOD 模式、岭南文化、智慧城市等",
    "Planned activity": "规划行动：针对空间/项目采取的具体规划、建设、管控动作，如规划、建设、改造、提升、推广、优化、限制、优先考虑等"
}

# 系统提示词（通用化，无特定核心概念绑定）
SYSTEM_PROMPT = f"""
你是一个城市规划与建筑领域的知识图谱实体提取专家。
你的任务是从文本中精准提取以下5类实体（仅提取文本中**明确出现**的内容，拒绝推测、联想或无中生有）：

{chr(10).join([f"{k}：{v}" for k, v in ENTITY_DEFINITIONS.items()])}

提取规则：
1. 实体必须是文本中**直接出现**的词汇/短语，禁止添加文本中没有的内容；
2. 同一实体仅保留一次（去重），如多次出现同一地点只记录一次；
3. 若某类实体在文本中无对应内容，返回空列表 []；
4. 严格按照指定格式输出JSON，仅包含上述5个实体类别，不新增其他字段；
5. 实体名称保持与原文一致，不做同义替换（如“南沙新区”≠“南沙区”，需分别保留）；
6. 仅输出JSON内容，无任何额外说明、注释或markdown格式。
"""

# 通用示例（适配城市规划场景，无特定概念绑定）
FEW_SHOT_EXAMPLE_INPUT = (
    "在南沙区的城市更新规划中，将核心区的工业用地改造为商业办公与公共绿地复合功能区，"
    "推广海绵城市建设理念，优先提升沿江片区的基础设施水平。"
)

FEW_SHOT_EXAMPLE_OUTPUT = {
    "Location": ["南沙区", "核心区", "沿江片区"],
    "Land use function": ["工业用地", "商业办公", "公共绿地"],
    "Direction": ["核心区", "沿江片区"],
    "Concept": ["城市更新", "海绵城市"],
    "Planned activity": ["改造", "推广", "提升"]
}

def call_llm(prompt_messages, model=None, max_retries=5, wait_base=1.0):
    """
    调用大模型（LLM）获取实体提取结果
    :param prompt_messages: 传给大模型的消息列表
    :param model: 指定使用的大模型（如gpt-4o、gpt-3.5-turbo等）
    :param max_retries: 调用失败后的最大重试次数
    :param wait_base: 重试等待时间基数（指数退避）
    :return: 大模型返回的原始文本响应
    """
    if OpenAI is None:
        raise RuntimeError('请安装openai包：pip install openai')
    
    # 读取API密钥（兼容多环境变量）
    api_key = os.getenv('GRAPHRAG_CHAT_API_KEY') or os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise RuntimeError('请设置环境变量 GRAPHRAG_CHAT_API_KEY 或 OPENAI_API_KEY')
    
    # 读取API基础地址和模型
    api_base = os.getenv('GRAPHRAG_API_BASE')
    model = model or os.getenv('GRAPHRAG_CHAT_MODEL') or os.getenv('OPENAI_MODEL', 'gpt-4o')
    
    client = OpenAI(api_key=api_key, base_url=api_base) if api_base else OpenAI(api_key=api_key)
    
    attempt = 0
    while attempt < max_retries:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=prompt_messages,
                temperature=0.0,  # 0温度：完全确定性输出，避免随机误差
                max_tokens=2048,
                response_format={"type": "json_object"}  # 强制JSON输出
            )
            return response.choices[0].message.content
        except Exception as e:
            attempt += 1
            if attempt >= max_retries:
                print(f"LLM调用失败（已重试{max_retries}次）：{str(e)[:100]}")
                return json.dumps({k: [] for k in ENTITY_DEFINITIONS.keys()})
            # 指数退避等待
            sleep_time = wait_base * (2 ** (attempt - 1))
            time.sleep(sleep_time)
    return json.dumps({k: [] for k in ENTITY_DEFINITIONS.keys()})

def extract_json_from_text(s):
    """
    从LLM返回的文本中提取并解析JSON（鲁棒性优化）
    :param s: LLM返回的原始文本
    :return: 解析后的JSON字典（失败返回包含5个空列表的默认结构）
    """
    if not s:
        return {k: [] for k in ENTITY_DEFINITIONS.keys()}
    
    # 预处理：移除markdown代码块、多余空格和换行
    s = s.strip()
    s = re.sub(r'^```(json)?|```$', '', s, flags=re.MULTILINE)
    s = re.sub(r'\n+', '', s)
    
    # 尝试直接解析
    try:
        parsed = json.loads(s)
        # 验证是否包含所有实体类别（缺失则补全空列表）
        for entity_type in ENTITY_DEFINITIONS.keys():
            if entity_type not in parsed:
                parsed[entity_type] = []
        return parsed
    except json.JSONDecodeError:
        pass
    
    # 正则提取JSON片段（应对LLM输出多余文本的情况）
    json_pattern = re.compile(r'\{[\s\S]*\}')
    match = json_pattern.search(s)
    if match:
        try:
            parsed = json.loads(match.group())
            for entity_type in ENTITY_DEFINITIONS.keys():
                if entity_type not in parsed:
                    parsed[entity_type] = []
            return parsed
        except json.JSONDecodeError:
            pass
    
    # 解析失败则返回默认实体结构
    return {k: [] for k in ENTITY_DEFINITIONS.keys()}

def deduplicate_entities(entities):
    """
    实体去重（保持顺序，去除重复值）
    :param entities: 原始实体字典
    :return: 去重后的实体字典
    """
    deduplicated = {}
    for entity_type, values in entities.items():
        # 去重并保留顺序
        seen = set()
        unique_values = []
        for val in values:
            # 过滤空值、纯空格
            clean_val = val.strip()
            if clean_val and clean_val not in seen:
                seen.add(clean_val)
                unique_values.append(clean_val)
        deduplicated[entity_type] = unique_values
    return deduplicated


def normalize_entity_names(entities, text):
    """
    实体归一化：基于文本上下文进行实体同义合并和指代消解
    解决"同体异名"导致的孤岛问题（如"南沙新区"vs"南沙区"、"海绵城市建设"vs"海绵城市"）
    
    :param entities: 原始实体字典（已去重）
    :param text: 原始文本（用于上下文判断）
    :return: (归一化后的实体字典, 实体别名映射表)
        实体别名映射格式：{"标准实体名": ["别名1", "别名2", ...]}
    """
    if not text or len(text.strip()) < 10:
        # 文本过短，无法进行上下文判断，直接返回原实体
        return entities, {}
    
    normalized = {}
    entity_aliases = {}
    
    # 用于记录每个实体类型中的归一化结果
    for entity_type, entity_list in entities.items():
        if not entity_list:
            normalized[entity_type] = []
            continue
        
        # 构建实体标准名映射（基于文本上下文判断）
        entity_map = {}  # {标准名: [别名列表]}
        entity_freq = {}  # 记录每个实体在文本中的出现频率（用于选择标准名）
        
        for entity in entity_list:
            entity = entity.strip()
            if not entity:
                continue
            
            # 统计实体在文本中的出现频率
            count = text.count(entity)
            entity_freq[entity] = count
            
            # 查找可能的同义实体（基于文本上下文判断）
            normalized_name = None
            
            # 策略1：检查是否已有相似实体（通过子串匹配和上下文判断）
            for std_name, aliases in entity_map.items():
                # 检查是否指向同一实体
                if _is_same_entity(entity, std_name, text):
                    normalized_name = std_name
                    break
            
            # 策略2：检查指代消解（如"该区"、"该片区"、"该区域"等指向之前提到的实体）
            if normalized_name is None:
                normalized_name = _resolve_reference(entity, entity_list, text)
            
            # 如果找到归一化的标准名，加入别名列表
            if normalized_name:
                if normalized_name not in entity_map:
                    entity_map[normalized_name] = []
                if entity != normalized_name:
                    entity_map[normalized_name].append(entity)
            else:
                # 作为新的标准实体
                normalized_name = entity
                entity_map[normalized_name] = []
        
        # 选择出现频率最高的作为标准名（如果存在同义实体）
        final_map = {}
        for std_name, aliases in entity_map.items():
            # 如果有别名，选择频率最高的作为标准名
            all_names = [std_name] + aliases
            best_name = max(all_names, key=lambda x: entity_freq.get(x, 0))
            
            other_names = [n for n in all_names if n != best_name]
            if other_names:
                final_map[best_name] = other_names
                if best_name not in entity_aliases:
                    entity_aliases[best_name] = []
                entity_aliases[best_name].extend(other_names)
            else:
                final_map[best_name] = []
        
        # 生成归一化后的实体列表（仅保留标准名，去重）
        normalized_list = list(final_map.keys())
        normalized[entity_type] = sorted(normalized_list, key=lambda x: entity_freq.get(x, 0), reverse=True)
    
    return normalized, entity_aliases


def _is_same_entity(entity1, entity2, text):
    """
    判断两个实体是否指向同一对象（基于文本上下文）
    
    :param entity1: 实体1
    :param entity2: 实体2
    :param text: 文本上下文
    :return: 是否指向同一实体
    """
    if entity1 == entity2:
        return True
    
    # 策略1：一个实体是另一个的子串，且上下文支持（如"南沙区"和"南沙新区"）
    if entity1 in entity2 or entity2 in entity1:
        # 检查在文本中是否明确指向同一对象
        # 简单规则：如果较短的实体在文本中出现位置紧邻较长的实体，可能是同一实体
        shorter, longer = (entity1, entity2) if len(entity1) < len(entity2) else (entity2, entity1)
        # 查找较长实体的位置，检查前后是否有较短实体
        idx = text.find(longer)
        if idx != -1:
            # 检查前后20个字符内是否有较短实体
            context = text[max(0, idx-20):idx+len(longer)+20]
            if shorter in context:
                # 进一步检查：如果短实体是长实体的前缀，且长实体只出现一次，可能是同一实体
                if longer.startswith(shorter) and text.count(longer) <= 2:
                    return True
    
    # 策略2：检查是否在同一个句子或紧密上下文中，且语义相似
    # 这里采用保守策略，只处理明显的情况
    # 如"海绵城市建设"和"海绵城市"在同一个句子中出现，可能是同一概念
    sentences = re.split(r'[。！？；\n]', text)
    for sentence in sentences:
        if entity1 in sentence and entity2 in sentence:
            # 在同一个句子中，检查是否为包含关系
            if entity1 in entity2 or entity2 in entity1:
                return True
    
    return False


def _resolve_reference(entity, entity_list, text):
    """
    指代消解：识别如"该区"、"该片区"等指代性实体，找到其指向的实际实体
    
    :param entity: 待消解的实体（可能是代词或指代性短语）
    :param entity_list: 所有实体列表
    :param text: 文本上下文
    :return: 指向的实际实体名（如果找到），否则返回None
    """
    # 常见的指代性短语
    reference_patterns = [
        r'该(区|片区|区域|区域|地区|地块|区域|区域)',
        r'该(用地|功能区|概念|项目)',
        r'上述(.*)',
        r'前述(.*)',
        r'这一(.*)',
        r'这一(区|片区|区域|区域|地区|地块)',
    ]
    
    # 检查是否为指代性实体
    is_reference = False
    for pattern in reference_patterns:
        if re.search(pattern, entity):
            is_reference = True
            break
    
    if not is_reference:
        return None
    
    # 在文本中查找该指代实体出现的位置
    entity_pos = text.find(entity)
    if entity_pos == -1:
        return None
    
    # 在该位置之前的文本中，查找最近的地点或区域实体
    preceding_text = text[:entity_pos]
    sentences = re.split(r'[。！？；\n]', preceding_text)
    
    # 从最近的句子开始，向前查找可能的指向实体
    for sentence in reversed(sentences[-3:]):  # 只看最近3个句子
        # 查找句子中的Location或Direction类型实体（最可能被指代）
        for candidate in entity_list:
            if candidate in sentence and candidate != entity:
                # 简单规则：如果是地点类实体，且在同一个段落中，可能是被指代的对象
                if len(candidate) >= 2:  # 避免单字实体被误匹配
                    return candidate
    
    return None

def build_messages(text):
    """
    构建传给LLM的消息列表（优化提示词结构）
    :param text: 待提取实体的文本
    :return: 标准化的消息列表
    """
    # 示例说明（清晰展示输入输出格式）
    fewshot_content = f"""
示例输入文本：
{FEW_SHOT_EXAMPLE_INPUT}

示例输出JSON：
{json.dumps(FEW_SHOT_EXAMPLE_OUTPUT, ensure_ascii=False, indent=2)}
    """
    
    # 用户指令（强化规则）
    user_content = f"""
请严格按照要求提取以下文本中的实体，仅输出标准JSON格式：

待提取文本：
{text}
    """
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": fewshot_content},
        {"role": "user", "content": user_content}
    ]
    return messages

def run(input_json, output_json, model=None):
    """
    实体抽取核心流程
    :param input_json: 输入JSON文件路径（格式：[{"id": "...", "text": "..."}]）
    :param output_json: 输出JSON文件路径
    :param model: 指定大模型
    """
    # 检查输入文件
    if not os.path.exists(input_json):
        print(f"错误：输入文件 {input_json} 不存在")
        return
    
    # 读取输入文本
    with open(input_json, 'r', encoding='utf-8') as f:
        try:
            items = json.load(f)
        except json.JSONDecodeError:
            print(f"错误：输入文件 {input_json} 不是有效的JSON格式")
            return
    
    # 批量提取实体
    results = []
    print("开始实体抽取（城市规划与建筑领域）...")
    for item in tqdm(items, desc='实体提取进度'):
        text = item.get('text', '').strip()
        item_id = item.get('id', '')
        
        # 过滤空文本/极短文本（仍生成完整结构）
        if len(text) < 5:
            results.append({
                "id": item_id,
                "text": text,
                "entities": {k: [] for k in ENTITY_DEFINITIONS.keys()}
            })
            continue
        
        # 构建消息并调用LLM
        messages = build_messages(text)
        llm_resp = call_llm(messages, model=model)
        
        # 解析并处理实体（去重、归一化、补全）
        raw_entities = extract_json_from_text(llm_resp)
        clean_entities = deduplicate_entities(raw_entities)
        
        # 实体归一化：基于文本上下文进行同义合并和指代消解
        normalized_entities, entity_aliases = normalize_entity_names(clean_entities, text)
        
        # 记录结果（保留原始实体和归一化后的实体，以及别名映射）
        result_item = {
            "id": item_id,
            "text": text,
            "entities": normalized_entities  # 归一化后的实体
        }
        
        # 如果有别名映射，记录到结果中
        if entity_aliases:
            result_item["entity_aliases"] = entity_aliases
        
        results.append(result_item)
    
    # 保存结果
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"实体抽取完成！结果已保存至：{output_json}")

def main():
    parser = argparse.ArgumentParser(description='城市规划与建筑领域实体提取工具（无核心概念绑定）')
    parser.add_argument('--input', '-i', default='processed_texts.json', help='输入JSON文件路径')
    parser.add_argument('--output', '-o', default='entities_extracted.json', help='输出JSON文件路径')
    parser.add_argument('--model', '-m', default=None, help='指定大模型（如gpt-4o、gpt-3.5-turbo）')
    args = parser.parse_args()
    run(args.input, args.output, model=args.model)

if __name__ == '__main__':
    main()
