import os
import json
import time
import argparse
import re
from typing import Dict, List, Any, Optional
from tqdm import tqdm

# 尝试导入OpenAI客户端
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

# 导入项目内模块
try:
    from .prompt_builder import PromptBuilder  # 假设PromptBuilder类存在或扩展
    from .spacy_nlp import analyze_sentence_syntax  # 用于句法分析
except ImportError:
    # 当直接运行脚本时使用绝对导入
    from prompt_builder import PromptBuilder
    from spacy_nlp import analyze_sentence_syntax

# --- 配置区 ---
# 关系类型规范
RELATION_SPEC = """
可提取的关系类型（仅使用文本中隐含/明确的关系，优先选择以下标准化谓词）：
1. 空间关系：位于、包含、邻近、属于（行政区/地块层级）、覆盖
2. 功能关系：用作、具备、属于（用地功能）、配套
3. 动作关系：规划、建设、改造、推广、提升、限制、实施、优先考虑
4. 概念关系：属于、基于、包含、体现、应用
5. 关联关系：相关于、影响、促进、阻碍（仅文本明确提及关联时使用）
"""

# 系统提示词（扩展版：支持间接关联挖掘）
SYSTEM_PROMPT = f"""
你是一个城市规划领域的知识图谱关系抽取专家。
你的任务是从文本和已提取的实体中，精准提取**文本明确提及或通过上下文隐含**的实体间三元组关系（Head实体, Relation关系, Tail实体）。

{RELATION_SPEC}

提取规则（严格遵守，否则会产生无效数据）：
1. 仅提取文本中**明确出现/直接隐含**的关系，拒绝推测、联想或无中生有；
2. 三元组的Head和Tail必须是已识别实体列表中的实体（或实体别名映射中的标准实体名），禁止添加未提及的实体；
3. 关系谓词需简洁、准确（优先使用上述标准化谓词），避免模糊表述（如"有关""涉及"）；
4. 同一组实体间的相同关系仅保留一次（去重）；
5. 若文本中无任何实体间关系，返回空数组 []；
6. 仅输出标准JSON数组格式（如 [[实体1, 关系, 实体2], [实体3, 关系, 实体4]]），无任何额外文本、注释或markdown格式；
7. 拒绝为了"连通性"生成无文本依据的关系（如"实体X 相关于 实体Y"仅当文本明确提及关联时使用）；

【扩展规则：挖掘文本内合法的间接关联】
8. 允许提取文本内"通过上下文隐含的间接关联"（但必须有文本依据）：
   - 示例1："A的B"（如"南沙区的核心区"）→ 提取 [A, 包含, B]（如[南沙区, 包含, 核心区]）
   - 示例2："A对B做C，B属于D"（如"对核心区进行改造，核心区属于南沙区"）→ 可提取 [A, C, D]（如[改造, 涉及, 南沙区]）
   - 规则：必须能在文本中找到明确的语言结构支持，不能凭空推断；
   
9. 允许提取"链式关联"（基于已有直接关联推断间接关联，但必须有文本支持）：
   - 示例：文本中有 [A, 包含, B] 和 [B, 包含, C]，且文本中有"A的B的C"或类似表述 → 可提取 [A, 包含, C]
   - 规则：链式关联必须能追溯到文本中的具体语言表达，禁止基于逻辑推理生成文本中没有依据的关联；
   
10. 【谨慎使用】共现实体的弱关联（仅当满足严格条件时）：
    - 条件：同一语义完整文本段落中，实体对出现≥2次，且无其他直接关系，但共现且语义相关
    - 处理：添加 [实体A, 共现于, 实体B] 关系（明确标注为"共现关联"）
    - 限制：此类关系仅用于连通节点，需在三元组中标注 source_type="cooccurrence"，严格限制数量
    - 注意：优先提取直接关系，只有在确实无直接关系时才考虑共现关系

输出格式要求：
- 每个三元组格式：[Head实体, 关系谓词, Tail实体]
- 若使用了规则8-10挖掘的间接关联，建议在后续处理中记录source_type（直接/间接/链式/共现）
- 所有关系必须能追溯到文本中的具体句子或上下文
"""

class RelationExtractor:
    """
    关系抽取器类，基于LLM驱动的关系抽取
    """
    def __init__(self, llm_client: Any, prompt_builder: 'PromptBuilder'):
        """
        初始化关系抽取器
        :param llm_client: LLM客户端实例（如OpenAI客户端）
        :param prompt_builder: PromptBuilder实例，用于构建提示词
        """
        self.llm_client = llm_client
        self.prompt_builder = prompt_builder

    def extract_relations(self, text_id: str, source_text: str, ner_entities: Dict[str, List[str]]) -> Dict[str, Any]:
        """
        提取关系三元组
        :param text_id: 文本唯一标识
        :param source_text: 原始分块文本内容
        :param ner_entities: NER实体字典，格式如{"Location": ["实体1"], ...}
        :return: 符合规范的输出字典
        """
        # 扁平化实体列表
        flat_entities = []
        for ent_list in ner_entities.values():
            flat_entities.extend(ent_list)
        flat_entities = list(set(flat_entities))  # 去重

        if not flat_entities or len(source_text.strip()) < 5:
            return {
                "text_id": text_id,
                "source_text": source_text,
                "relation_triplets": []
            }

        # 构建句法分析信息（用于prompt_builder）
        syntax_info = analyze_sentence_syntax(source_text)

        # 使用prompt_builder构建提示词
        prompt = self.prompt_builder.build_relation_prompt(
            sentence=source_text,
            entities=flat_entities,
            syntax_info=syntax_info
        )

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt}
        ]

        # 调用LLM
        llm_resp = self._call_llm(messages)
        triplets = self._parse_triplets(llm_resp)

        # 构建输出
        relation_triplets = []
        for triplet in triplets:
            subject, predicate, obj = triplet
            # 计算位置（简单查找首次出现位置）
            subj_start = source_text.find(subject)
            subj_end = subj_start + len(subject) if subj_start != -1 else -1
            pred_start = source_text.find(predicate, subj_end)
            pred_end = pred_start + len(predicate) if pred_start != -1 else -1
            obj_start = source_text.find(obj, pred_end)
            obj_end = obj_start + len(obj) if obj_start != -1 else -1

            # 置信度：简单设置为0.95，可扩展为基于LLM的评分
            confidence = 0.95

            relation_triplets.append({
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "confidence": confidence,
                "position": {
                    "subject_start": subj_start,
                    "subject_end": subj_end,
                    "predicate_start": pred_start,
                    "predicate_end": pred_end,
                    "object_start": obj_start,
                    "object_end": obj_end
                }
            })

        return {
            "text_id": text_id,
            "source_text": source_text,
            "relation_triplets": relation_triplets
        }

    def save_relations(self, relations: Dict[str, Any], output_dir: str = "run_output"):
        """
        保存关系抽取结果到文件
        :param relations: 关系抽取结果字典
        :param output_dir: 输出目录
        """
        os.makedirs(output_dir, exist_ok=True)
        filename = f"{relations['text_id']}_relation.json"
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(relations, f, ensure_ascii=False, indent=2)
        print(f"关系抽取结果已保存至：{filepath}")

    def validate_relation_format(self, relations: Dict[str, Any]) -> bool:
        """
        校验输出格式是否符合规范
        :param relations: 关系抽取结果字典
        :return: 是否有效
        """
        required_keys = {"text_id", "source_text", "relation_triplets"}
        if not all(key in relations for key in required_keys):
            return False
        if not isinstance(relations["relation_triplets"], list):
            return False
        for triplet in relations["relation_triplets"]:
            required_triplet_keys = {"subject", "predicate", "object", "confidence", "position"}
            if not all(key in triplet for key in required_triplet_keys):
                return False
            if not isinstance(triplet["confidence"], (int, float)) or not (0 <= triplet["confidence"] <= 1):
                return False
            pos = triplet["position"]
            pos_keys = {"subject_start", "subject_end", "predicate_start", "predicate_end", "object_start", "object_end"}
            if not all(key in pos for key in pos_keys):
                return False
        return True

    def _call_llm(self, messages: List[Dict[str, str]], model: Optional[str] = None, max_retries: int = 5) -> str:
        """
        调用LLM获取响应
        :param messages: 消息列表
        :param model: 模型名称
        :param max_retries: 最大重试次数
        :return: LLM响应文本
        """
        if not self.llm_client:
            raise RuntimeError('LLM客户端未初始化')

        model = model or os.getenv('GRAPHRAG_CHAT_MODEL') or 'gpt-4o'
        attempt = 0
        while attempt < max_retries:
            try:
                response = self.llm_client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.0,
                    max_tokens=1024,
                )
                return response.choices[0].message.content
            except Exception as e:
                attempt += 1
                if attempt >= max_retries:
                    print(f"LLM调用失败：{str(e)[:100]}")
                    return "[]"
                time.sleep(1 * (2 ** (attempt - 1)))
        return "[]"

    def _parse_triplets(self, response: str) -> List[List[str]]:
        """
        解析LLM响应为三元组列表
        :param response: LLM响应文本
        :return: 三元组列表
        """
        # 预处理
        response = response.strip()
        response = re.sub(r'^```(json)?|```$', '', response, flags=re.MULTILINE)
        response = re.sub(r'\n+', '', response)

        try:
            triplets = json.loads(response)
        except json.JSONDecodeError:
            # 正则提取
            match = re.search(r'\[\s*\[.*\]\s*\]', response, re.S)
            if match:
                try:
                    triplets = json.loads(match.group(0))
                except:
                    return []
            else:
                return []

        # 校验和去重
        valid_triplets = []
        seen = set()
        for triplet in triplets:
            if not isinstance(triplet, list) or len(triplet) < 3:
                continue
            subj, pred, obj = triplet[0].strip(), triplet[1].strip(), triplet[2].strip()
            if not subj or not pred or not obj:
                continue
            key = (subj.lower(), pred.lower(), obj.lower())
            if key not in seen:
                seen.add(key)
                valid_triplets.append([subj, pred, obj])
        return valid_triplets

def build_messages(text, entities):
    """
    构建LLM消息列表（通用化，无核心概念绑定）
    :param text: 原始文本
    :param entities: 已提取的实体字典
    :return: 消息列表（无实体时返回None）
    """
    # 扁平化实体列表并去重
    flat_entities = []
    seen_ents = set()
    for ent_list in entities.values():
        for ent in ent_list:
            clean_ent = ent.strip()
            if clean_ent and clean_ent not in seen_ents:
                seen_ents.add(clean_ent)
                flat_entities.append(clean_ent)
    
    # 无实体时返回None
    if not flat_entities:
        return None
    
    # 构建用户提示词（强调仅提取文本中真实存在的关系）
    user_prompt = f"""
请基于以下文本和已识别实体，提取**文本明确提及**的三元组关系：

原文：
{text}

已识别实体：
{', '.join(flat_entities)}

输出要求：
1. 仅输出JSON数组，格式为 [[Head实体, Relation关系, Tail实体], ...]；
2. 关系必须来自文本，禁止生成无依据的关联；
3. 严格遵守关系谓词规范，拒绝模糊表述。
    """
    
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt}
    ]

def run(input_json, output_json, model=None):
    """
    关系抽取核心流程（使用RelationExtractor类）
    :param input_json: 输入实体JSON文件路径
    :param output_json: 输出三元组JSON文件路径
    :param model: 指定大模型
    """
    # 检查输入文件
    if not os.path.exists(input_json):
        print(f"错误：输入文件 {input_json} 不存在")
        return

    # 读取输入实体数据
    with open(input_json, 'r', encoding='utf-8') as f:
        try:
            items = json.load(f)
        except json.JSONDecodeError:
            print(f"错误：输入文件 {input_json} 不是有效JSON格式")
            return

    # 初始化LLM客户端
    try:
        from openai import OpenAI
        api_key = os.getenv('GRAPHRAG_CHAT_API_KEY') or os.getenv('OPENAI_API_KEY')
        api_base = os.getenv('GRAPHRAG_API_BASE')
        llm_client = OpenAI(api_key=api_key, base_url=api_base) if api_base else OpenAI(api_key=api_key)
    except ImportError:
        print("错误：未安装openai包，请运行 pip install openai")
        return
    except Exception as e:
        print(f"错误：LLM客户端初始化失败: {e}")
        return

    # 初始化组件
    prompt_builder = PromptBuilder()
    extractor = RelationExtractor(llm_client, prompt_builder)

    all_results = []
    print("开始关系抽取（城市规划领域，仅提取文本中真实存在的关系）...")

    # 批量处理每个文本块
    for item in tqdm(items, desc='关系抽取进度'):
        text = item.get('text', '').strip()
        item_id = item.get('id', '')
        entities = item.get('entities', {})

        # 过滤空文本/无实体的情况
        if len(text) < 5 or not any(entities.values()):
            all_results.append({
                "id": item_id,
                "text": text,
                "triplets": []
            })
            continue

        # 使用RelationExtractor提取关系
        try:
            result = extractor.extract_relations(item_id, text, entities)
            # 转换为旧格式以保持兼容性
            triplets = []
            for triplet in result['relation_triplets']:
                triplets.append([
                    triplet['subject'],
                    triplet['predicate'],
                    triplet['object']
                ])

            result_item = {
                "id": item_id,
                "text": text,
                "triplets": triplets
            }
            
            # 保留实体别名映射（如果存在）
            if 'entity_aliases' in item:
                result_item['entity_aliases'] = item['entity_aliases']
            
            # 保留其他字段（如entities、syntax等）
            for key in ['entities', 'syntax']:
                if key in item:
                    result_item[key] = item[key]
            
            all_results.append(result_item)
        except Exception as e:
            print(f"处理文本块 {item_id} 时出错: {e}")
            all_results.append({
                "id": item_id,
                "text": text,
                "triplets": []
            })

    # 保存结果
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"关系抽取完成！共处理 {len(all_results)} 个文本块，结果已保存至：{output_json}")

def main():
    """程序主函数（通用化参数解析）"""
    parser = argparse.ArgumentParser(description='城市规划领域三元组关系抽取工具（仅提取文本中真实存在的关系）')
    parser.add_argument('--input', '-i', default='entities_extracted.json', help='输入实体JSON文件路径')
    parser.add_argument('--output', '-o', default='triplets_final.json', help='输出三元组结果JSON文件路径')
    parser.add_argument('--model', '-m', default=None, help='指定大模型（如gpt-4o、gpt-3.5-turbo）')
    args = parser.parse_args()
    run(args.input, args.output, model=args.model)

if __name__ == '__main__':
    main()

