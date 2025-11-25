"""本地演示脚本（src 版本）：模拟 NER 与 RE"""
import json


def demo_ner(input_json):
    with open(input_json, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
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
        results.append({"id": chunk['id'], "text": text, "entities": entities})
    return results


def demo_re(input_json):
    with open(input_json, 'r', encoding='utf-8') as f:
        ner_data = json.load(f)
    results = []
    for item in ner_data:
        text = item['text']
        entities = item['entities']
        triplets = []
        locations = entities.get("Location", [])
        activities = entities.get("Planned activity", [])
        functions = entities.get("Land use function", [])
        concepts = entities.get("Concept", [])
        if locations and activities:
            for loc in locations:
                for act in activities:
                    triplets.append([loc, act, "发展目标"])
        if functions and concepts:
            for func in functions:
                for concept in concepts:
                    triplets.append(["城市规划", "实现", func])
        if activities:
            for act in activities:
                triplets.append(["政府", "推进", act])
        results.append({"id": item['id'], "text": text, "triplets": triplets if triplets else [["演示", "三元组", "示例"]]})
    return results


def demo_pipeline():
    ner_results = demo_ner('processed_texts.json')
    with open('entities_extracted.json', 'w', encoding='utf-8') as f:
        json.dump(ner_results, f, ensure_ascii=False, indent=2)
    re_results = demo_re('entities_extracted.json')
    with open('triplets_final.json', 'w', encoding='utf-8') as f:
        json.dump(re_results, f, ensure_ascii=False, indent=2)


if __name__ == '__main__':
    demo_pipeline()
