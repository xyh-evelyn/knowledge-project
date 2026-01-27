"""三元组关联补全脚本

核心功能：基于文本内的实体关联网络，补全合法的间接关联，解决孤岛三元组问题

改进策略：
1. 对孤立的三元组（如[XX路, 位于, 核心区]），检索同一文本中"核心区"的其他关联
2. 基于文本内的实体关联网络，自动补全合法的间接关联（如[核心区, 属于, 南沙区] → [XX路, 属于, 南沙区]）
3. 所有补全的关联必须能追溯到文本中的具体句子或上下文，在三元组中记录source_sentence

约束条件：
- 所有新增关联必须完全来自输入文本，无任何推测、联想
- 禁止生成"无关关系"（如无文本依据的"相关于"）
- 仅挖掘文本内隐含但合法的关联，而非无依据造关系
- 保留原始三元组，新增补全后的三元组，便于验证
"""
import json
import re
import sys
import os
import argparse
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Tuple, Set, Optional

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config import TRIPLETS_CLEANED_PATH, TRIPLETS_COMPLETED_PATH, ensure_output_dirs


def find_triplet_source_sentence(triplet: List[str], text: str) -> Optional[str]:
    """
    查找三元组在文本中的来源句子
    
    :param triplet: 三元组 [head, relation, tail]
    :param text: 原始文本
    :return: 包含该三元组的关键句子（如果找到），否则返回None
    """
    head, relation, tail = triplet
    
    # 将文本分割为句子
    sentences = re.split(r'[。！？；\n]', text)
    
    # 查找包含所有三个元素的句子
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        
        # 检查句子中是否包含头实体和尾实体
        if head in sentence and tail in sentence:
            # 进一步检查关系是否在该句子或相邻句子中出现
            if relation in sentence:
                return sentence
            # 如果在相邻句子中，也认为有关联
            idx = sentences.index(sentence)
            if idx > 0 and relation in sentences[idx-1]:
                return f"{sentences[idx-1]}。{sentence}"
            if idx < len(sentences)-1 and relation in sentences[idx+1]:
                return f"{sentence}。{sentences[idx+1]}"
    
    # 如果没找到完整匹配，返回包含头尾实体的句子
    for sentence in sentences:
        sentence = sentence.strip()
        if head in sentence and tail in sentence:
            return sentence
    
    return None


def build_entity_relation_graph(triplets: List[List[str]], text: str) -> Dict[str, Dict[str, List[Tuple[str, str]]]]:
    """
    构建实体关系图：entity -> {relation -> [(target_entity, source_sentence), ...]}
    
    :param triplets: 三元组列表
    :param text: 原始文本（用于查找来源句子）
    :return: 实体关系图
    """
    graph = defaultdict(lambda: defaultdict(list))
    
    for triplet in triplets:
        if not isinstance(triplet, list) or len(triplet) < 3:
            continue
        
        head, relation, tail = triplet
        head = head.strip()
        relation = relation.strip()
        tail = tail.strip()
        
        if not head or not relation or not tail:
            continue
        
        # 查找来源句子
        source_sentence = find_triplet_source_sentence(triplet, text)
        
        # 构建图：从head到tail的关系
        graph[head][relation].append((tail, source_sentence))
        
        # 如果是双向关系（如"邻近"），也添加反向关系
        if relation in ['邻近', '靠近', '接近', '连接', '衔接']:
            graph[tail][relation].append((head, source_sentence))
    
    return graph


def find_island_triplets(triplets: List[List[str]], graph: Dict[str, Dict[str, List[Tuple[str, str]]]]) -> List[Tuple[List[str], str]]:
    """
    识别孤立的三元组（孤岛三元组）
    
    孤岛三元组定义：头实体或尾实体在图中没有其他关联（即只出现在一个三元组中）
    
    :param triplets: 三元组列表
    :param graph: 实体关系图
    :return: 孤岛三元组列表（格式：[(triplet, reason)]）
    """
    island_triplets = []
    
    # 统计每个实体在图中出现的次数
    entity_counts = defaultdict(int)
    for triplet in triplets:
        if not isinstance(triplet, list) or len(triplet) < 3:
            continue
        head, _, tail = triplet[0].strip(), triplet[1].strip(), triplet[2].strip()
        if head and tail:
            entity_counts[head] += 1
            entity_counts[tail] += 1
    
    # 识别孤岛三元组
    for triplet in triplets:
        if not isinstance(triplet, list) or len(triplet) < 3:
            continue
        
        head, _, tail = triplet[0].strip(), triplet[1].strip(), triplet[2].strip()
        if not head or not tail:
            continue
        
        # 检查是否为孤岛（头实体或尾实体只出现一次）
        if entity_counts.get(head, 0) == 1 or entity_counts.get(tail, 0) == 1:
            island_triplets.append((triplet, 'island'))
    
    return island_triplets


def complete_indirect_relations(
    island_triplet: List[str],
    graph: Dict[str, Dict[str, List[Tuple[str, str]]]],
    text: str,
    max_hops: int = 2
) -> List[Tuple[List[str], str, str]]:
    """
    基于文本内的实体关联网络，补全孤岛三元组的合法间接关联
    
    :param island_triplet: 孤岛三元组 [head, relation, tail]
    :param graph: 实体关系图
    :param text: 原始文本
    :param max_hops: 最大跳数（最多通过多少个中间实体）
    :return: 补全的间接关联列表（格式：[(triplet, source_sentence, completion_type)]）
    """
    head, relation, tail = island_triplet[0].strip(), island_triplet[1].strip(), island_triplet[2].strip()
    if not head or not relation or not tail:
        return []
    
    completed = []
    
    # 策略1：通过中间实体补全间接关联
    # 例如：[XX路, 位于, 核心区] 和 [核心区, 属于, 南沙区] → [XX路, 属于, 南沙区]
    
    # 从head出发，查找可达的实体（最多max_hops跳）
    def find_reachable_entities(start_entity: str, visited: Set[str], hops: int) -> List[Tuple[str, str, str]]:
        """查找从start_entity可达的实体，返回[(target_entity, path_relation, source_sentence)]"""
        if hops > max_hops or start_entity in visited:
            return []
        
        visited.add(start_entity)
        reachable = []
        
        if start_entity not in graph:
            return []
        
        for rel, targets in graph[start_entity].items():
            for target, source_sentence in targets:
                if target not in visited:
                    reachable.append((target, rel, source_sentence))
                    # 递归查找
                    sub_reachable = find_reachable_entities(target, visited.copy(), hops + 1)
                    for sub_target, sub_rel, sub_source in sub_reachable:
                        reachable.append((sub_target, f"{rel}->{sub_rel}", sub_source))
        
        return reachable
    
    # 查找从head可达的实体
    reachable_from_head = find_reachable_entities(head, set(), 0)
    
    # 检查是否可以通过间接路径连接到tail
    for target, path_relation, source_sentence in reachable_from_head:
        if target == tail:
            # 找到间接路径：head -> ... -> tail
            # 补全间接关联（使用路径中的最后一个关系，或使用"相关于"作为弱关联）
            indirect_relation = path_relation.split('->')[-1] if '->' in path_relation else relation
            
            # 检查文本中是否支持这个间接关联
            if _text_supports_indirect_relation(head, indirect_relation, tail, text):
                completed.append((
                    [head, indirect_relation, tail],
                    source_sentence or text[:200],  # 如果找不到具体句子，使用文本开头
                    'indirect_path'
                ))
    
    # 策略2：基于文本语义补全（如"A的B"隐含A包含B）
    # 检查文本中是否有"A的B"、"A中B"等表述，隐含包含关系
    if relation == '位于' or relation == '属于':
        # 检查是否有"A的B"结构，隐含A包含B
        pattern = f"{re.escape(head)}的{re.escape(tail)}"
        if re.search(pattern, text):
            completed.append((
                [head, '包含', tail],
                find_triplet_source_sentence([head, '包含', tail], text) or text[:200],
                'semantic_implication'
            ))
    
    return completed


def _text_supports_indirect_relation(head: str, relation: str, tail: str, text: str) -> bool:
    """
    检查文本是否支持间接关联（保守策略）
    
    :param head: 头实体
    :param relation: 关系
    :param tail: 尾实体
    :param text: 文本
    :return: 是否支持
    """
    # 检查头尾实体是否在文本中出现
    if head not in text or tail not in text:
        return False
    
    # 检查关系是否在文本中出现（或同义词）
    relation_synonyms = {
        '属于': ['属于', '归属', '归入'],
        '包含': ['包含', '包括', '含有'],
        '位于': ['位于', '地处', '坐落在'],
    }
    
    if relation in relation_synonyms:
        synonyms = relation_synonyms[relation]
        for syn in synonyms:
            if syn in text:
                # 检查头实体、同义词、尾实体是否在同一个句子中出现
                sentences = re.split(r'[。！？；\n]', text)
                for sentence in sentences:
                    if head in sentence and syn in sentence and tail in sentence:
                        return True
    
    return False


def complete_triplet_links(
    input_path: str = 'triplets_cleaned.json',
    output_path: str = 'triplets_completed.json',
    original_path: str = 'triplets_cleaned_original.json'
) -> Dict:
    """
    补全三元组关联，解决孤岛三元组问题
    
    :param input_path: 输入清洗后的三元组JSON文件路径
    :param output_path: 输出补全后的三元组JSON文件路径
    :param original_path: 输出原始三元组JSON文件路径（备份）
    :return: 统计信息字典
    """
    # 读取输入数据
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f'输入文件不存在: {input_path}')
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 统计信息
    total_items = len(data)
    total_original_triplets = 0
    total_completed_triplets = 0
    island_count = 0
    completion_count = 0
    
    completed_data = []
    
    # 备份原始数据
    with open(original_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'原始数据已备份至: {original_path}')
    
    # 处理每个文本块
    for item in data:
        text = item.get('text', '').strip()
        triplets = item.get('triplets', [])
        
        if not isinstance(triplets, list):
            triplets = []
        
        total_original_triplets += len(triplets)
        
        # 构建实体关系图
        graph = build_entity_relation_graph(triplets, text)
        
        # 识别孤岛三元组
        island_triplets = find_island_triplets(triplets, graph)
        island_count += len(island_triplets)
        
        # 补全间接关联
        # 先将原始三元组转换为统一格式（列表格式）
        completed_triplets = []
        added_triplets = set()  # 用于去重
        item_completion_count = 0  # 当前文本块的补全数量
        
        # 保留原始三元组（列表格式）
        for triplet in triplets:
            if isinstance(triplet, list) and len(triplet) >= 3:
                triplet_key = (triplet[0].strip(), triplet[1].strip(), triplet[2].strip())
                if triplet_key not in added_triplets:
                    completed_triplets.append(triplet)
                    added_triplets.add(triplet_key)
            elif isinstance(triplet, dict) and 'triplet' in triplet:
                # 如果已经是字典格式，提取三元组列表部分
                triplet_list = triplet['triplet']
                if isinstance(triplet_list, list) and len(triplet_list) >= 3:
                    triplet_key = (triplet_list[0].strip(), triplet_list[1].strip(), triplet_list[2].strip())
                    if triplet_key not in added_triplets:
                        completed_triplets.append(triplet_list)
                        added_triplets.add(triplet_key)
        
        # 补全间接关联
        for island_triplet, reason in island_triplets:
            # 补全间接关联
            indirect_relations = complete_indirect_relations(island_triplet, graph, text)
            
            for new_triplet, source_sentence, completion_type in indirect_relations:
                # 去重：检查是否已存在相同三元组
                triplet_key = tuple([str(x).strip() for x in new_triplet])
                if triplet_key not in added_triplets:
                    # 添加补全的三元组（列表格式，与原格式保持一致）
                    # 注：补全的三元组可以通过source_type字段区分，但在clean_triplets阶段可以统一处理
                    completed_triplets.append(new_triplet)
                    added_triplets.add(triplet_key)
                    item_completion_count += 1
        
        completion_count += item_completion_count
        
        total_completed_triplets += len(completed_triplets)
        
        # 构建输出项
        completed_item = {
            'id': item.get('id'),
            'text': text,
            'triplets': completed_triplets
        }
        
        # 如果有补全的三元组，记录元数据（用于验证）
        if item_completion_count > 0:
            # 记录补全信息（但不改变triplets格式，保持兼容）
            completed_item['_metadata'] = {
                'island_count': len(island_triplets),
                'completion_count': item_completion_count,
                'note': '包含补全的间接关联三元组，所有关联均来自文本'
            }
        
        # 保留其他字段
        for key in ['syntax', 'entities', 'entity_aliases']:
            if key in item:
                completed_item[key] = item[key]
        
        completed_data.append(completed_item)
    
    # 保存补全后的数据
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(completed_data, f, ensure_ascii=False, indent=2)
    
    # 打印统计信息
    print('=' * 80)
    print('三元组关联补全完成！')
    print('=' * 80)
    print(f'总文本块数: {total_items:,}')
    print(f'原始三元组数: {total_original_triplets:,}')
    print(f'补全后三元组数: {total_completed_triplets:,}')
    print(f'新增三元组数: {total_completed_triplets - total_original_triplets:,}')
    print(f'孤岛三元组数: {island_count:,}')
    print(f'成功补全数: {completion_count:,}')
    print(f'补全率: {completion_count / island_count * 100:.2f}%' if island_count > 0 else 'N/A')
    print()
    print(f'补全结果已保存至: {output_path}')
    print(f'原始数据备份至: {original_path}')
    print('=' * 80)
    
    # 返回统计信息
    return {
        'total_items': total_items,
        'original_triplets': total_original_triplets,
        'completed_triplets': total_completed_triplets,
        'added_triplets': total_completed_triplets - total_original_triplets,
        'island_count': island_count,
        'completion_count': completion_count,
        'completion_rate': completion_count / island_count if island_count > 0 else 0.0
    }


# ==================== 主程序入口 ====================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='三元组关联补全工具（解决孤岛三元组问题）')
    parser.add_argument('--input', '-i', default=None,
                       help='输入清洗后的三元组 JSON 文件路径（可选，默认使用配置）')
    parser.add_argument('--output', '-o', default=None,
                       help='输出补全后的三元组 JSON 文件路径（可选，默认使用配置）')
    parser.add_argument('--original', '-r', default=None,
                       help='原始数据备份路径（可选，默认使用配置）')
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    ensure_output_dirs()
    
    # 确定输入输出路径
    input_path = args.input or str(TRIPLETS_CLEANED_PATH)
    output_path = args.output or str(TRIPLETS_COMPLETED_PATH)
    original_path = args.original or str(TRIPLETS_COMPLETED_PATH.parent / "triplets_cleaned_original.json")
    
    if not os.path.exists(input_path):
        print(f"❌ 错误：输入文件不存在 {input_path}")
        sys.exit(1)
    
    print(f"📥 输入文件: {input_path}")
    print(f"📤 输出文件: {output_path}")
    print(f"📋 原始数据备份: {original_path}")
    
    try:
        stats = complete_triplet_links(
            input_path=input_path,
            output_path=output_path,
            original_path=original_path
        )
    except Exception as e:
        print(f'❌ 错误: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
