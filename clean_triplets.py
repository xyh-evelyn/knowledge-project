"""清洗三元组脚本

规则（启发式）：
- 去除占位/演示三元组（如包含 '演示','示例','三元组' 等词）
- 归一化关系谓词（推进/实现/发展/规划 等）
- 去除头尾相同的三元组
- 去除头/尾为空或仅为标点的三元组
- 对短实体做严格检查：若长度为1，仅允许方向词（北/南/东/西/中/上/下等）
- 仅保留关系谓词中包含常见动词关键词的三元组（推进/实现/发展/建设/采用/覆盖/建立/设置/改善/增加/实现/推进/促进/推动/实施/完成）
- 去重

输出：`triplets_cleaned.json`，并打印清洗前/后统计与删除原因汇总。
"""
import json
import re
from collections import Counter
from pathlib import Path


PLACEHOLDER_KEYWORDS = {'演示', '示例', '三元组', 'demo'}
REL_KEYWORDS = ['推进', '促进', '推动', '实现', '完成', '发展', '建设', '规划', '计划', '采用', '覆盖', '建立', '设置', '改善', '增加', '实施']
DIR_WORDS = {'北','南','东','西','东北','东南','西北','西南','中','上','下'}


def normalize_rel(rel: str) -> str:
    if not isinstance(rel, str):
        return str(rel)
    s = rel.strip()
    # normalize common synonyms
    if any(k in s for k in ['推进','促进','推动']):
        return '推进'
    if any(k in s for k in ['实现','完成']):
        return '实现'
    if any(k in s for k in ['发展','建设']):
        return '发展'
    if any(k in s for k in ['规划','计划']):
        return '规划活动'
    # fallback: strip and return
    return s


def is_placeholder_token(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s2 = s.strip()
    if not s2:
        return True
    for kw in PLACEHOLDER_KEYWORDS:
        if kw in s2:
            return True
    return False


def is_valid_entity(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    if not s:
        return False
    # if single character, only allow direction words
    if len(s) == 1 and s not in DIR_WORDS:
        return False

    # Check if string contains at least one alnum or CJK character
    has_meaningful = False
    for ch in s:
        # ASCII alnum
        if ch.isalnum():
            has_meaningful = True
            break
        # CJK Unified Ideographs range
        if '\u4e00' <= ch <= '\u9fff':
            has_meaningful = True
            break

    if not has_meaningful:
        return False
    return True


def rel_has_keyword(rel: str) -> bool:
    if not isinstance(rel, str):
        return False
    for k in REL_KEYWORDS:
        if k in rel:
            return True
    return False


def clean_triplets(input_path='triplets_final.json', output_path='triplets_cleaned.json'):
    p = Path(input_path)
    if not p.exists():
        raise FileNotFoundError(f'{input_path} not found')

    data = json.loads(p.read_text(encoding='utf-8'))
    total_before = 0
    total_after = 0
    removed_reasons = Counter()
    cleaned = []

    for item in data:
        triplets = item.get('triplets') or []
        kept = []
        if isinstance(triplets, dict) and 'error' in triplets:
            removed_reasons['llm_parse_error'] += 1
            triplets = []

        for tri in triplets:
            total_before += 1
            try:
                if not (isinstance(tri, list) and len(tri) >= 3):
                    removed_reasons['bad_format'] += 1
                    continue
                h = str(tri[0]).strip()
                r = str(tri[1]).strip()
                t = str(tri[2]).strip()

                # placeholder filter
                if is_placeholder_token(h) or is_placeholder_token(r) or is_placeholder_token(t):
                    removed_reasons['placeholder'] += 1
                    continue

                # head == tail
                if h == t:
                    removed_reasons['head_eq_tail'] += 1
                    continue

                # valid entity checks
                if not (is_valid_entity(h) and is_valid_entity(t)):
                    removed_reasons['invalid_entity'] += 1
                    continue

                # relation keyword filter (strict)
                if not rel_has_keyword(r):
                    removed_reasons['rel_no_keyword'] += 1
                    continue

                # normalize relation
                r_norm = normalize_rel(r)

                kept.append([h, r_norm, t])
            except Exception:
                removed_reasons['exception'] += 1
                continue

        # deduplicate
        unique = []
        seen = set()
        for tri in kept:
            key = (tri[0], tri[1], tri[2])
            if key in seen:
                removed_reasons['dup'] += 1
                continue
            seen.add(key)
            unique.append(tri)

        total_after += len(unique)
        cleaned.append({'id': item.get('id'), 'text': item.get('text'), 'syntax': item.get('syntax'), 'entities': item.get('entities'), 'triplets': unique})

    Path(output_path).write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding='utf-8')

    print('清洗完成')
    print('总三元组 (清洗前):', total_before)
    print('总三元组 (清洗后):', total_after)
    print('\n删除原因统计:')
    for k, v in removed_reasons.most_common():
        print(f'  {k}: {v}')

    return {
        'before': total_before,
        'after': total_after,
        'removed': dict(removed_reasons)
    }


if __name__ == '__main__':
    clean_triplets()
