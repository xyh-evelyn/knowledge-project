"""三元组清洗脚本（优化版）

核心优化：
1. 合并语义相同/相近的关系谓词，统一表述规范
2. 最大化保留关键三元组，包括孤点实体对应的三元组
3. 避免过度清洗，仅剔除无效/无意义数据

清洗规则：
- 合并语义相同/相近的关系谓词（如：包含/含有/囊括 → 包含）
- 去除占位/演示三元组（包含'演示','示例','demo'等关键词）
- 去除头尾相同且无语义价值的三元组（如"中国=中国"）
- 去除头/尾为空、纯标点、乱码的三元组
- 去除关系谓词无实际语义的三元组（如"无""未知""测试"）
- 放宽实体限制：除方向词外，具备明确语义的单字实体（如"楼""棚""坝"）均保留
- 去重：完全重复和语义重复的三元组仅保留一条

输出：
- `triplets_cleaned.json`：清洗后的三元组数据
- `relation_merge_map.json`：关系合并对照表
- 控制台输出：清洗前后统计信息
"""
import json
import re
import sys
import os
import argparse
from pathlib import Path
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Set

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config import TRIPLETS_FINAL_PATH, TRIPLETS_CLEANED_PATH, RELATION_MERGE_MAP_PATH, ensure_output_dirs


# ==================== 配置常量 ====================

# 占位/演示关键词（包含这些词的三元组将被删除）
PLACEHOLDER_KEYWORDS = {'演示', '示例', '三元组', 'demo', '测试数据', '占位'}

# 无效关系谓词关键词（包含这些词的关系将被删除）
INVALID_REL_KEYWORDS = {'无', '未知', '测试', '占位', '空', 'null', 'none', 'N/A'}

# 方向词（单字实体中的方向词允许保留）
DIR_WORDS = {'北', '南', '东', '西', '中', '上', '下', '左', '右', 
             '东北', '东南', '西北', '西南', '前', '后'}

# 有意义的单字实体（除方向词外，这些单字实体也允许保留）
MEANINGFUL_SINGLE_CHARS = {'楼', '棚', '坝', '桥', '路', '街', '巷', '门', '窗', 
                           '墙', '顶', '底', '边', '角', '层', '间', '室', '厅',
                           '院', '园', '池', '湖', '河', '山', '岛', '区', '市',
                           '县', '镇', '村', '站', '场', '馆', '所', '局', '处'}


# ==================== 关系合并规则 ====================

# 关系合并映射表：{合并后的标准关系: [同义关系列表]}
RELATION_MERGE_MAP = {
    # 1. 语义完全相同的关系（强制合并）
    '包含': ['包含', '含有', '囊括', '涵盖', '包括', '复合功能区包含', '涵盖范围包括'],
    '属于': ['属于', '归属于', '归类为', '归类于', '归入', '隶属于'],
    '位于': ['位于', '坐落于', '地处', '处于', '坐落在', '地处', '位于在'],
    '具备': ['具备', '拥有', '具有', '持有', '拥有'],
    '应用': ['应用', '采用', '使用', '运用', '利用', '运用了', '采用了'],
    '改造': ['改造', '改建', '翻新', '翻修', '重建', '改造为', '改建为', '改造成', '改造成为', '改建为'],
    
    # 2. 语义相近的关系（可选项合并，保留核心语义）
    '推进': ['推进', '促进', '推动', '助推', '推动发展'],
    '实现': ['实现', '完成', '达成', '做到', '实现', '达成目标'],
    '发展': ['发展', '建设', '打造', '构建', '建设', '打造为', '构建为'],
    '建立': ['建立', '搭建', '创建', '设立', '设置', '建立', '搭建', '创建了'],
    '规划': ['规划', '计划', '谋划', '策划', '计划', '谋划'],
    '实施': ['实施', '执行', '开展', '进行', '实施', '执行了', '开展', '进行中'],
    '改善': ['改善', '优化', '提升', '改进', '改良', '优化', '提升', '改善'],
    '限制': ['限制', '约束', '制约', '管控', '限制', '约束条件'],
    '配套': ['配套', '配合', '协同', '辅助', '配套', '配合'],
    '覆盖': ['覆盖', '笼罩', '遮蔽', '覆盖至', '覆盖范围'],
    '嵌入': ['嵌入', '插入', '置入', '嵌入到'],
    '衔接': ['衔接', '连接', '链接', '联结', '连接', '链接'],
    '邻近': ['邻近', '靠近', '接近', '贴近', '邻近', '靠近'],
    '影响': ['影响', '作用于', '对...影响', '影响', '产生影响'],
    '体现': ['体现', '表现', '展现', '反映', '体现', '表现'],
    
    # 3. 城市规划领域特定关系（扩展）
    '推广': ['推广', '推广实施', '推广应用', '推广使用'],  # 保持独立，不与其他合并
    '提升': ['提升', '提升水平', '提升质量', '提升能力'],  # 保持独立
    '优先考虑': ['优先考虑', '优先', '优先实施', '优先发展'],  # 保持独立
    '调节': ['调节', '调控', '调整'],  # 保持独立
    '选定': ['选定', '选择', '确定'],  # 保持独立
    
    # 4. 其他常见关系（无相近语义的独特关系直接保留）
    # 如：推广、提升、优先考虑、调节、选定、配套、覆盖、嵌入、串联等
    # 这些关系如果不在映射表中，将原样保留
}

# 构建反向映射：从原关系到标准关系
RELATION_REVERSE_MAP = {}
RELATION_CONTAINS_MAP = []  # 用于包含匹配（较长词优先）
for std_rel, synonyms in RELATION_MERGE_MAP.items():
    for syn in synonyms:
        # 完全匹配
        RELATION_REVERSE_MAP[syn] = std_rel
        # 处理"的"结尾的情况
        if not syn.endswith('的'):
            RELATION_REVERSE_MAP[syn + '的'] = std_rel
        # 包含匹配（按长度排序，长词优先）
        RELATION_CONTAINS_MAP.append((syn, std_rel))

# 按长度降序排序，优先匹配长词
RELATION_CONTAINS_MAP.sort(key=lambda x: len(x[0]), reverse=True)


# ==================== 工具函数 ====================

def normalize_relation(rel: str) -> Tuple[str, str]:
    """
    规范化关系谓词，返回(标准化关系, 原始关系)
    
    :param rel: 原始关系谓词
    :return: (标准化后的关系, 原始关系) 的元组
    """
    if not isinstance(rel, str):
        rel = str(rel)
    
    original_rel = rel.strip()
    
    # 如果为空，返回原样
    if not original_rel:
        return original_rel, original_rel
    
    rel = original_rel
    
    # 1. 直接匹配（完全匹配）
    if rel in RELATION_REVERSE_MAP:
        return RELATION_REVERSE_MAP[rel], original_rel
    
    # 2. 处理 "的" 结尾的情况（先处理，避免匹配不准确）
    if rel.endswith('的'):
        base_rel = rel[:-1]
        if base_rel in RELATION_REVERSE_MAP:
            return RELATION_REVERSE_MAP[base_rel], original_rel
    
    # 3. 包含匹配（关系谓词中包含同义词）
    # 优先匹配更长的同义词（避免短词误匹配）
    for orig_rel, std_rel in RELATION_CONTAINS_MAP:
        if orig_rel in rel:
            return std_rel, original_rel
    
    # 4. 不在映射表中的关系，原样保留（不强制合并）
    return original_rel, original_rel


def is_placeholder_token(s: str) -> bool:
    """
    检查是否为占位/演示标记
    """
    if not isinstance(s, str):
        return False
    
    s = s.strip()
    if not s:
        return False
    
    # 检查是否包含占位关键词
    s_lower = s.lower()
    for kw in PLACEHOLDER_KEYWORDS:
        if kw in s or kw in s_lower:
            return True
    
    return False


def is_invalid_relation(rel: str) -> bool:
    """
    检查关系谓词是否无效（无实际语义）
    """
    if not isinstance(rel, str):
        return False
    
    rel = rel.strip().lower()
    
    # 检查无效关键词
    for kw in INVALID_REL_KEYWORDS:
        if kw in rel:
            return True
    
    # 检查是否为空
    if not rel or rel == '':
        return True
    
    return False


def is_valid_entity(entity: str) -> bool:
    """
    检查实体是否有效（放宽限制，最大化保留有效实体）
    
    规则：
    1. 不能为空或纯标点
    2. 必须包含有意义的字符（字母、数字、中文）
    3. 单字实体：除方向词外，具备明确语义的单字实体均保留（放宽限制）
    4. 不限制孤点实体（即使只出现一次也保留）
    """
    if not isinstance(entity, str):
        return False
    
    entity = entity.strip()
    
    # 空字符串无效
    if not entity:
        return False
    
    # 检查是否为纯标点/乱码（不包含任何字母、数字、中文）
    has_meaningful = False
    for ch in entity:
        # ASCII 字母数字
        if ch.isalnum():
            has_meaningful = True
            break
        # 中文字符（包括CJK扩展区）
        if '\u4e00' <= ch <= '\u9fff' or '\u3400' <= ch <= '\u4dbf' or '\uf900' <= ch <= '\ufaff':
            has_meaningful = True
            break
    
    if not has_meaningful:
        return False
    
    # 单字实体处理（放宽限制）
    if len(entity) == 1:
        ch = entity
        # 方向词：允许
        if ch in DIR_WORDS:
            return True
        # 有意义的单字实体：允许（如"楼""棚""坝"等）
        if ch in MEANINGFUL_SINGLE_CHARS:
            return True
        # 其他单字实体：只要包含中文或字母数字，就认为是有效的（最大化保留）
        if ch.isalnum() or '\u4e00' <= ch <= '\u9fff':
            return True
    
    # 多字实体：只要包含有意义字符即可
    return True


def is_valid_triplet(head: str, relation: str, tail: str) -> Tuple[bool, str]:
    """
    检查三元组是否有效
    
    :return: (是否有效, 无效原因)
    """
    # 1. 格式检查（在调用此函数前已检查）
    
    # 2. 占位/演示标记检查
    if is_placeholder_token(head) or is_placeholder_token(relation) or is_placeholder_token(tail):
        return False, 'placeholder'
    
    # 3. 实体有效性检查
    if not is_valid_entity(head):
        return False, 'invalid_head'
    if not is_valid_entity(tail):
        return False, 'invalid_tail'
    
    # 4. 关系有效性检查
    if is_invalid_relation(relation):
        return False, 'invalid_relation'
    
    # 5. 头尾相同检查（头=尾且无语义价值的三元组删除）
    # 大部分情况下，头=尾是无效的（如"中国=中国"）
    # 但某些特殊场景可能有意义，这里采用严格策略：头=尾一律视为无效
    if head == tail:
        return False, 'head_eq_tail'
    
    return True, ''


# ==================== 主清洗函数 ====================

def clean_triplets(
    input_path: str = 'triplets_final.json',
    output_path: str = 'triplets_cleaned.json',
    merge_map_path: str = 'relation_merge_map.json'
) -> Dict:
    """
    清洗三元组数据
    
    :param input_path: 输入JSON文件路径
    :param output_path: 输出清洗后的JSON文件路径
    :param merge_map_path: 关系合并对照表输出路径
    :return: 统计信息字典
    """
    # 读取输入数据
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f'输入文件不存在: {input_path}')
    
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 统计信息
    total_before = 0
    total_after = 0
    removed_reasons = Counter()
    relation_merge_stats = defaultdict(lambda: {'original': [], 'count': 0})
    
    cleaned_data = []
    
    # 用于去重的集合（基于合并后的关系）
    seen_triplets = set()
    
    # 遍历每个文本块
    for item in data:
        triplets = item.get('triplets', [])
        
        # 处理错误情况
        if isinstance(triplets, dict) and 'error' in triplets:
            removed_reasons['llm_parse_error'] += 1
            triplets = []
        
        if not isinstance(triplets, list):
            triplets = []
        
        kept_triplets = []
        
        # 处理每个三元组
        for tri in triplets:
            total_before += 1
            
            try:
                # 格式检查
                if not (isinstance(tri, list) and len(tri) >= 3):
                    removed_reasons['bad_format'] += 1
                    continue
                
                # 提取三元组元素
                head = str(tri[0]).strip()
                relation = str(tri[1]).strip()
                tail = str(tri[2]).strip()
                
                # 有效性检查
                is_valid, reason = is_valid_triplet(head, relation, tail)
                if not is_valid:
                    removed_reasons[reason] += 1
                    continue
                
                # 规范化关系谓词
                normalized_rel, original_rel = normalize_relation(relation)
                
                # 记录关系合并信息（如果发生了合并）
                if normalized_rel != original_rel:
                    relation_merge_stats[normalized_rel]['original'].append(original_rel)
                    relation_merge_stats[normalized_rel]['count'] += 1
                
                # 去重检查（基于合并后的关系）
                triplet_key = (head, normalized_rel, tail)
                if triplet_key in seen_triplets:
                    removed_reasons['dup'] += 1
                    continue
                seen_triplets.add(triplet_key)
                
                # 保留三元组
                kept_triplets.append([head, normalized_rel, tail])
                
            except Exception as e:
                removed_reasons[f'exception: {str(e)[:50]}'] += 1
                continue
        
        # 更新统计
        total_after += len(kept_triplets)
        
        # 构建清洗后的数据项
        cleaned_item = {
            'id': item.get('id'),
            'text': item.get('text'),
            'triplets': kept_triplets
        }
        
        # 保留其他字段（如果存在）
        if 'syntax' in item:
            cleaned_item['syntax'] = item['syntax']
        if 'entities' in item:
            cleaned_item['entities'] = item['entities']
        
        cleaned_data.append(cleaned_item)
    
    # 生成关系合并对照表
    merge_map = {}
    for std_rel, stats in relation_merge_stats.items():
        # 统计每种原始关系的出现次数
        orig_counts = Counter(stats['original'])
        merge_map[std_rel] = {
            'original_relations': dict(orig_counts),
            'merge_count': stats['count']
        }
    
    # 保存清洗后的数据
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(cleaned_data, f, ensure_ascii=False, indent=2)
    
    # 保存关系合并对照表
    merge_map_file = Path(merge_map_path)
    merge_map_file.parent.mkdir(parents=True, exist_ok=True)
    with open(merge_map_file, 'w', encoding='utf-8') as f:
        json.dump(merge_map, f, ensure_ascii=False, indent=2)
    
    # 打印统计信息
    print('=' * 80)
    print('三元组清洗完成！')
    print('=' * 80)
    print(f'总三元组数（清洗前）: {total_before:,}')
    print(f'总三元组数（清洗后）: {total_after:,}')
    print(f'删除三元组数: {total_before - total_after:,}')
    print(f'保留率: {total_after / total_before * 100:.2f}%' if total_before > 0 else 'N/A')
    print()
    
    print('删除原因统计:')
    for reason, count in removed_reasons.most_common():
        print(f'  {reason:30s}: {count:6,d}')
    print()
    
    # 关系合并统计
    if merge_map:
        print('关系合并统计:')
        print(f'  发生合并的关系类型数: {len(merge_map)}')
        total_merged = sum(stats['merge_count'] for stats in merge_map.values())
        print(f'  总合并次数: {total_merged:,}')
        print()
        print('关系合并对照表（前20个最常见的合并）:')
        sorted_merges = sorted(merge_map.items(), key=lambda x: x[1]['merge_count'], reverse=True)
        for std_rel, stats in sorted_merges[:20]:
            orig_str = ', '.join(f'{k}({v}次)' for k, v in stats['original_relations'].items())
            print(f'  {std_rel:15s} ← {orig_str}')
    else:
        print('关系合并统计: 无关系合并')
    print()
    
    print(f'清洗结果已保存至: {output_path}')
    print(f'关系合并对照表已保存至: {merge_map_path}')
    print('=' * 80)
    
    # 返回统计信息
    return {
        'before': total_before,
        'after': total_after,
        'removed_count': total_before - total_after,
        'removed_reasons': dict(removed_reasons),
        'relation_merges': merge_map,
        'retention_rate': total_after / total_before if total_before > 0 else 0.0
    }


# ==================== 主程序入口 ====================

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='三元组清洗工具（优化版）')
    parser.add_argument('--input', '-i', default=None, 
                       help='输入 JSON 文件路径（可选，默认使用配置）')
    parser.add_argument('--output', '-o', default=None,
                       help='输出 JSON 文件路径（可选，默认使用配置）')
    parser.add_argument('--merge-map', '-m', default=None,
                       help='关系合并对照表输出路径（可选，默认使用配置）')
    
    args = parser.parse_args()
    
    # 确保输出目录存在
    ensure_output_dirs()
    
    # 确定输入输出路径
    input_path = args.input or str(TRIPLETS_FINAL_PATH)
    output_path = args.output or str(TRIPLETS_CLEANED_PATH)
    merge_map_path = args.merge_map or str(RELATION_MERGE_MAP_PATH)
    
    if not os.path.exists(input_path):
        print(f"❌ 错误：输入文件不存在 {input_path}")
        sys.exit(1)
    
    print(f"📥 输入文件: {input_path}")
    print(f"📤 输出文件: {output_path}")
    print(f"📋 关系合并表: {merge_map_path}")
    
    try:
        stats = clean_triplets(
            input_path=input_path,
            output_path=output_path,
            merge_map_path=merge_map_path
        )
    except Exception as e:
        print(f'❌ 错误: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)
