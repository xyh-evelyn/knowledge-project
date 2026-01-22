"""
知识图谱补全（KGC）示例程序
演示如何使用KGC模块进行知识图谱补全
"""

import json
import sys
import os
from pathlib import Path

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.kgc_module import KGCModule, load_json_data


def main():
    """主函数：演示KGC模块的使用"""
    
    # 1. 加载数据
    print("=" * 60)
    print("步骤1: 加载数据")
    print("=" * 60)
    
    json_file = "triplets_completed.json"
    if not os.path.exists(json_file):
        print(f"错误: 找不到文件 {json_file}")
        return
    
    print(f"正在加载 {json_file}...")
    json_data = load_json_data(json_file)
    print(f"成功加载 {len(json_data)} 条数据")
    
    # 显示第一条数据示例
    if json_data:
        print("\n数据示例（第一条）:")
        print(f"ID: {json_data[0].get('id')}")
        print(f"文本: {json_data[0].get('text', '')[:100]}...")
        print(f"三元组数量: {len(json_data[0].get('triplets', []))}")
        if json_data[0].get('triplets'):
            print(f"示例三元组: {json_data[0]['triplets'][0]}")
    
    # 2. 初始化KGC模块
    print("\n" + "=" * 60)
    print("步骤2: 初始化KGC模块")
    print("=" * 60)
    
    print("正在初始化KGC模块（使用GCN增强）...")
    kgc = KGCModule(json_data, embedding_dim=100, use_gcn=True)
    
    print(f"实体数量: {len(kgc.all_entities)}")
    print(f"关系数量: {len(kgc.all_relations)}")
    print(f"三元组数量: {len(kgc.all_triplets)}")
    print(f"\n实体类型: {list(kgc.entity_types.keys())}")
    
    # 显示一些实体和关系示例
    print(f"\n实体示例（前10个）: {list(kgc.all_entities)[:10]}")
    print(f"关系示例（前10个）: {list(kgc.all_relations)[:10]}")
    
    # 3. 训练嵌入模型
    print("\n" + "=" * 60)
    print("步骤3: 训练嵌入模型")
    print("=" * 60)
    
    print("开始训练嵌入模型（这可能需要一些时间）...")
    print("提示: 可以使用较少的epochs进行快速测试")
    
    # 使用较少的epochs进行演示
    kgc.train(epochs=20, batch_size=32, learning_rate=0.01)
    print("训练完成！")
    
    # 4. 知识图谱补全预测
    print("\n" + "=" * 60)
    print("步骤4: 知识图谱补全预测")
    print("=" * 60)
    
    # 选择一些测试查询
    test_queries = [
        ("园艺主题", "相关于"),
        ("妫汭湖", "包含"),
        ("中国馆", "位于"),
    ]
    
    for head, relation in test_queries:
        if head not in kgc.all_entities or relation not in kgc.all_relations:
            print(f"\n跳过查询 ({head}, {relation}, ?): 实体或关系不存在")
            continue
        
        print(f"\n查询: ({head}, {relation}, ?)")
        predictions = kgc.predict(head, relation, top_k=10, use_subgraph=True, use_rules=True)
        
        if predictions:
            print("预测结果（Top 10）:")
            for i, (entity, score) in enumerate(predictions, 1):
                print(f"  {i}. {entity} (得分: {score:.4f})")
        else:
            print("  未找到预测结果")
    
    # 5. 规则挖掘
    print("\n" + "=" * 60)
    print("步骤5: 逻辑规则挖掘")
    print("=" * 60)
    
    print("正在挖掘逻辑规则...")
    rules = kgc.get_mined_rules(min_support=2, top_k=10)
    
    if rules:
        print(f"发现 {len(rules)} 条规则（显示前10条）:")
        for i, rule in enumerate(rules, 1):
            print(f"\n规则 {i}:")
            print(f"  前提: {rule['premise']}")
            print(f"  结论: {rule['conclusion']}")
            print(f"  支持度: {rule['support']}")
            print(f"  置信度: {rule.get('confidence', 0):.4f}")
    else:
        print("未发现规则（可能需要降低min_support或增加数据）")
    
    # 6. 生成LLM提示
    print("\n" + "=" * 60)
    print("步骤6: 生成LLM提示")
    print("=" * 60)
    
    # 选择一个查询生成提示
    test_head = "园艺主题"
    test_relation = "相关于"
    
    if test_head in kgc.all_entities and test_relation in kgc.all_relations:
        print(f"为查询 ({test_head}, {test_relation}, ?) 生成LLM提示:")
        prompt = kgc.generate_llm_prompt(test_head, test_relation, top_k_candidates=20)
        print("\n" + "-" * 60)
        print(prompt)
        print("-" * 60)
    else:
        print(f"查询 ({test_head}, {test_relation}, ?) 的实体或关系不存在")
    
    # 7. 子图构建示例
    print("\n" + "=" * 60)
    print("步骤7: 动态子图构建示例")
    print("=" * 60)
    
    test_entity = "园艺主题"
    if test_entity in kgc.all_entities:
        print(f"为实体 '{test_entity}' 构建子图:")
        subgraph = kgc.subgraph_builder.get_related_triplets(test_entity, max_depth=2, max_triplets=10)
        print(f"子图包含 {len(subgraph)} 个三元组:")
        for i, triplet in enumerate(subgraph, 1):
            print(f"  {i}. {triplet[0]} --[{triplet[1]}]--> {triplet[2]}")
    else:
        print(f"实体 '{test_entity}' 不存在")
    
    print("\n" + "=" * 60)
    print("演示完成！")
    print("=" * 60)


if __name__ == "__main__":
    main()
