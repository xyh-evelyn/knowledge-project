"""本地演示脚本：模拟 NER 和 RE，生成实体和三元组"""
import json
import random

def demo_ner(input_json):
    """读取分块文本，模拟 NER 输出"""
    with open(input_json, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    # 模拟提取规则（演示用，不基于实际 LLM）
    results = []
    for chunk in chunks:
        text = chunk['text']
        entities = {
            "Location": [],
            "Land use function": [],
            "Direction": [],
            "Concept": [],
            "Planned activity": []
        }
        
        # 简单的关键词匹配示例
        if '规划' in text or '建筑' in text or '设计' in text:
            entities["Concept"].append("规划设计")
        if '发展' in text or '建设' in text:
            entities["Planned activity"].append("发展建设")
        if '地点' in text or '区' in text or '城市' in text:
            entities["Location"].append("城市地区")
        if '产业' in text or '功能' in text:
            entities["Land use function"].append("产业功能区")
        if '北' in text or '南' in text or '东' in text or '西' in text:
            entities["Direction"].append("方位指向")
        
        results.append({
            "id": chunk['id'],
            "text": text,
            "entities": entities
        })
    
    return results


def demo_re(input_json):
    """读取 NER 结果，模拟 RE 生成三元组"""
    with open(input_json, 'r', encoding='utf-8') as f:
        ner_data = json.load(f)
    
    results = []
    for item in ner_data:
        text = item['text']
        entities = item['entities']
        triplets = []
        
        # 根据实体类型生成简单的三元组
        locations = entities.get("Location", [])
        activities = entities.get("Planned activity", [])
        functions = entities.get("Land use function", [])
        concepts = entities.get("Concept", [])
        
        # 生成 SPO 三元组示例
        if locations and activities:
            for loc in locations:
                for act in activities:
                    triplets.append([loc, act, "发展目标"])
        
        if functions and concepts:
            for func in functions:
                for concept in concepts:
                    triplets.append(["城市规划", "实现", func])
        
        # 添加一些通用三元组
        if activities:
            for act in activities:
                triplets.append(["政府", "推进", act])
        
        results.append({
            "id": item['id'],
            "text": text,
            "triplets": triplets if triplets else [["演示", "三元组", "示例"]]
        })
    
    return results


def demo_pipeline():
    """演示完整 pipeline"""
    print("=" * 60)
    print("城市规划知识图谱 - 本地演示")
    print("=" * 60)
    
    # 第1步：数据准备（已完成）
    print("\n【第1步】数据准备 - 已完成")
    print("✓ processed_texts.json 已生成（114 个文本块）")
    
    # 第2步：实体抽取
    print("\n【第2步】实体抽取（NER）- 运行中...")
    ner_results = demo_ner('processed_texts.json')
    with open('entities_extracted.json', 'w', encoding='utf-8') as f:
        json.dump(ner_results, f, ensure_ascii=False, indent=2)
    print(f"✓ entities_extracted.json 已生成（{len(ner_results)} 条数据）")
    print(f"  示例 - 第1块的实体：")
    if ner_results:
        for key, vals in ner_results[0]['entities'].items():
            if vals:
                print(f"    {key}: {vals}")
    
    # 第3步：关系抽取
    print("\n【第3步】关系抽取（RE）- 运行中...")
    re_results = demo_re('entities_extracted.json')
    with open('triplets_final.json', 'w', encoding='utf-8') as f:
        json.dump(re_results, f, ensure_ascii=False, indent=2)
    print(f"✓ triplets_final.json 已生成（{len(re_results)} 条数据）")
    print(f"  示例三元组：")
    if re_results:
        for item in re_results[:3]:
            if item['triplets']:
                for tri in item['triplets'][:2]:
                    print(f"    {tri}")
    
    # 统计信息
    print("\n【统计信息】")
    total_triplets = sum(len(item.get('triplets', [])) for item in re_results)
    print(f"• 总文本块数: {len(ner_results)}")
    print(f"• 总三元组数: {total_triplets}")
    
    # 关键样本
    print("\n【关键样本】")
    print("第1个文本块（前100字）:")
    print(f"  {ner_results[0]['text'][:100]}...")
    print(f"提取的实体类型:")
    for key, vals in ner_results[0]['entities'].items():
        print(f"  • {key}: {vals}")
    if re_results[0]['triplets']:
        print(f"生成的三元组:")
        for tri in re_results[0]['triplets'][:3]:
            print(f"  • {tri}")
    
    print("\n" + "=" * 60)
    print("演示完成！已生成以下文件：")
    print("  • processed_texts.json     - 分块后的文本")
    print("  • entities_extracted.json  - 提取的实体")
    print("  • triplets_final.json      - 生成的三元组")
    print("\n下一步：")
    print("  python neo4j_import.py --input triplets_final.json --password your_password")
    print("=" * 60)


if __name__ == '__main__':
    demo_pipeline()
