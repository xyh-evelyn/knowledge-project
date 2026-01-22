"""
KGC增量同步示例程序

演示如何使用KGC增量同步模块将KGC预测结果回写到JSON并同步到Neo4j
"""

import json
import sys
from pathlib import Path
from typing import List

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.kgc_incremental_sync import KGCIncrementalSync, load_kgc_predictions
from src.kgc_module import KGCModule, load_json_data


def generate_kgc_predictions(kgc_module: KGCModule, 
                              queries: List[tuple],
                              output_file: str = "kgc_predictions.json"):
    """
    使用KGC模块生成预测结果
    
    Args:
        kgc_module: 训练好的KGC模块实例
        queries: 查询列表，格式为 [(head, relation), ...]
        output_file: 输出文件路径
    """
    print(f"生成KGC预测结果，共 {len(queries)} 个查询...")
    
    predictions = []
    
    for head, relation in queries:
        try:
            # 进行预测
            pred_results = kgc_module.predict(head, relation, top_k=5, 
                                             use_subgraph=True, use_rules=True)
            
            # 转换为标准格式
            for entity, score in pred_results:
                predictions.append({
                    "head": head,
                    "relation": relation,
                    "tail": entity,
                    "confidence": float(score)
                })
        except Exception as e:
            print(f"警告：查询 ({head}, {relation}) 失败: {str(e)}")
            continue
    
    # 保存预测结果
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)
    
    print(f"预测结果已保存到 {output_file}，共 {len(predictions)} 条")
    return predictions


def example_1_basic_sync():
    """示例1：基本同步流程"""
    print("=" * 60)
    print("示例1：基本同步流程")
    print("=" * 60)
    
    # 1. 准备KGC预测结果（示例数据）
    kgc_predictions = [
        ("园艺主题", "体现", "农耕智慧"),
        ("中国馆", "连接", "妫汭湖"),
        ("梯田", "体现", "传统智慧"),
        ("水院空间", "体现", "四水归堂"),
    ]
    
    confidences = [0.87, 0.82, 0.79, 0.85]
    
    # 2. 创建同步对象（干运行模式）
    sync = KGCIncrementalSync(
        input_json="triplets_completed.json",
        output_json="triplets_completed_augmented.json",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password=None,  # 设置为None跳过Neo4j同步
        dry_run=True  # 干运行模式
    )
    
    # 3. 执行同步
    sync.process(kgc_predictions, confidences)
    
    # 4. 保存日志
    sync.save_logs("kgc_sync_log_example1.txt")


def example_2_from_kgc_module():
    """示例2：从KGC模块生成预测并同步"""
    print("=" * 60)
    print("示例2：从KGC模块生成预测并同步")
    print("=" * 60)
    
    # 1. 加载数据并初始化KGC模块
    print("加载数据...")
    data = load_json_data("triplets_completed.json")
    
    print("初始化KGC模块...")
    kgc = KGCModule(data, embedding_dim=100, use_gcn=False)  # 使用较小配置快速测试
    
    # 2. 训练模型（快速测试用较少epochs）
    print("训练模型（快速测试，20个epochs）...")
    kgc.train(epochs=20, batch_size=32, learning_rate=0.01)
    
    # 3. 定义查询
    queries = [
        ("园艺主题", "相关于"),
        ("妫汭湖", "包含"),
        ("中国馆", "位于"),
    ]
    
    # 4. 生成预测
    predictions = generate_kgc_predictions(kgc, queries, "kgc_predictions.json")
    
    # 5. 转换为三元组格式
    kgc_triplets = [(p["head"], p["relation"], p["tail"]) for p in predictions]
    confidences = [p["confidence"] for p in predictions]
    
    # 6. 执行同步
    sync = KGCIncrementalSync(
        input_json="triplets_completed.json",
        output_json="triplets_completed_augmented.json",
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password=None,  # 从环境变量读取或设置为None跳过
        dry_run=True
    )
    
    sync.process(kgc_triplets, confidences)
    sync.save_logs("kgc_sync_log_example2.txt")


def example_3_full_sync_with_neo4j():
    """示例3：完整同步（包含Neo4j）"""
    print("=" * 60)
    print("示例3：完整同步（包含Neo4j）")
    print("=" * 60)
    
    import os
    
    # 1. 加载KGC预测结果文件
    predictions_file = "kgc_predictions.json"
    if not os.path.exists(predictions_file):
        print(f"错误：找不到预测结果文件 {predictions_file}")
        print("请先运行示例2生成预测结果，或手动创建预测结果文件")
        return
    
    kgc_triplets, confidences = load_kgc_predictions(predictions_file)
    
    # 2. 创建同步对象（实际写入模式）
    sync = KGCIncrementalSync(
        input_json="triplets_completed.json",
        output_json="triplets_completed_augmented.json",
        neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
        neo4j_user=os.getenv("NEO4J_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_PASSWORD"),  # 从环境变量读取
        neo4j_database=os.getenv("NEO4J_DATABASE"),
        dry_run=False  # 实际写入
    )
    
    # 3. 执行同步
    sync.process(kgc_triplets, confidences)
    
    # 4. 保存日志
    sync.save_logs("kgc_sync_log_example3.txt")
    
    print("\n同步完成！")
    print(f"- JSON文件: {sync.output_json}")
    print(f"- 日志文件: kgc_sync_log_example3.txt")


def example_4_load_from_file():
    """示例4：从文件加载预测结果并同步"""
    print("=" * 60)
    print("示例4：从文件加载预测结果并同步")
    print("=" * 60)
    
    # 创建示例预测结果文件
    sample_predictions = [
        {"head": "园艺主题", "relation": "体现", "tail": "农耕智慧", "confidence": 0.87},
        {"head": "中国馆", "relation": "连接", "tail": "妫汭湖", "confidence": 0.82},
        {"head": "梯田", "relation": "体现", "tail": "传统智慧", "confidence": 0.79},
    ]
    
    with open("sample_kgc_predictions.json", 'w', encoding='utf-8') as f:
        json.dump(sample_predictions, f, ensure_ascii=False, indent=2)
    
    print("已创建示例预测结果文件: sample_kgc_predictions.json")
    
    # 加载预测结果
    kgc_triplets, confidences = load_kgc_predictions("sample_kgc_predictions.json")
    print(f"加载了 {len(kgc_triplets)} 条三元组")
    
    # 执行同步（干运行）
    sync = KGCIncrementalSync(
        input_json="triplets_completed.json",
        output_json="triplets_completed_augmented.json",
        dry_run=True
    )
    
    sync.process(kgc_triplets, confidences)
    sync.save_logs("kgc_sync_log_example4.txt")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="KGC增量同步示例程序")
    parser.add_argument("--example", "-e", type=int, default=1,
                       choices=[1, 2, 3, 4],
                       help="选择示例 (1: 基本同步, 2: 从KGC模块, 3: 完整同步, 4: 从文件加载)")
    
    args = parser.parse_args()
    
    if args.example == 1:
        example_1_basic_sync()
    elif args.example == 2:
        example_2_from_kgc_module()
    elif args.example == 3:
        example_3_full_sync_with_neo4j()
    elif args.example == 4:
        example_4_load_from_file()
    
    print("\n示例运行完成！")
