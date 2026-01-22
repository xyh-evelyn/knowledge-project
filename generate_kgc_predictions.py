"""
从KGC模块批量生成预测结果

该脚本用于：
1. 加载训练好的KGC模块
2. 对指定的查询列表进行预测
3. 将预测结果保存为JSON文件，供增量同步模块使用
"""

import json
import sys
import argparse
from pathlib import Path
from typing import List, Tuple

# 添加src目录到路径
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.kgc_module import KGCModule, load_json_data


def generate_predictions_from_queries(kgc_module: KGCModule,
                                      queries: List[Tuple[str, str]],
                                      top_k: int = 5,
                                      min_confidence: float = 0.5) -> List[dict]:
    """
    从查询列表生成预测结果
    
    Args:
        kgc_module: 训练好的KGC模块
        queries: 查询列表，格式为 [(head, relation), ...]
        top_k: 每个查询返回前K个结果
        min_confidence: 最小置信度阈值
        
    Returns:
        预测结果列表，格式为 [{"head": ..., "relation": ..., "tail": ..., "confidence": ...}, ...]
    """
    predictions = []
    
    print(f"开始生成预测，共 {len(queries)} 个查询...")
    
    for idx, (head, relation) in enumerate(queries, 1):
        print(f"\n[{idx}/{len(queries)}] 查询: ({head}, {relation}, ?)")
        
        try:
            # 进行预测
            pred_results = kgc_module.predict(
                head, relation, 
                top_k=top_k,
                use_subgraph=True, 
                use_rules=True
            )
            
            if not pred_results:
                print(f"  未找到预测结果")
                continue
            
            # 转换为标准格式
            for entity, score in pred_results:
                # 将得分转换为置信度（TransE得分通常是负数，需要归一化）
                # 这里简单处理：如果score > 0，直接使用；否则转换为0-1范围
                if score > 0:
                    confidence = min(1.0, score / 10.0)  # 简单归一化
                else:
                    confidence = max(0.0, 1.0 + score / 10.0)  # 将负数映射到0-1
                
                # 应用最小置信度阈值
                if confidence < min_confidence:
                    continue
                
                predictions.append({
                    "head": head,
                    "relation": relation,
                    "tail": entity,
                    "confidence": round(confidence, 4)
                })
                print(f"  -> {entity} (置信度: {confidence:.4f})")
                
        except Exception as e:
            print(f"  错误: {str(e)}")
            continue
    
    print(f"\n生成完成，共 {len(predictions)} 条预测结果")
    return predictions


def load_queries_from_file(queries_file: str) -> List[Tuple[str, str]]:
    """
    从文件加载查询列表
    
    支持格式：
    1. JSON格式: [{"head": "...", "relation": "..."}, ...]
    2. 简单列表格式: [["head", "relation"], ...]
    3. 每行一个查询: head,relation
    """
    queries = []
    
    with open(queries_file, 'r', encoding='utf-8') as f:
        # 尝试作为JSON加载
        try:
            data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, list) and len(item) >= 2:
                        queries.append((item[0], item[1]))
                    elif isinstance(item, dict):
                        head = item.get("head") or item.get("subject")
                        relation = item.get("relation") or item.get("predicate")
                        if head and relation:
                            queries.append((head, relation))
        except json.JSONDecodeError:
            # 如果不是JSON，按行读取
            f.seek(0)
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                parts = line.split(',')
                if len(parts) >= 2:
                    queries.append((parts[0].strip(), parts[1].strip()))
    
    return queries


def main():
    parser = argparse.ArgumentParser(description="从KGC模块生成预测结果")
    parser.add_argument("--input", "-i", default="triplets_completed.json",
                       help="输入JSON文件路径（默认: triplets_completed.json）")
    parser.add_argument("--queries", "-q", required=True,
                       help="查询文件路径（JSON或文本格式）")
    parser.add_argument("--output", "-o", default="kgc_predictions.json",
                       help="输出预测结果文件路径（默认: kgc_predictions.json）")
    parser.add_argument("--embedding-dim", type=int, default=100,
                       help="嵌入维度（默认: 100）")
    parser.add_argument("--use-gcn", action="store_true",
                       help="使用GCN增强（默认: False）")
    parser.add_argument("--epochs", type=int, default=50,
                       help="训练轮数（默认: 50）")
    parser.add_argument("--batch-size", type=int, default=32,
                       help="批次大小（默认: 32）")
    parser.add_argument("--learning-rate", type=float, default=0.01,
                       help="学习率（默认: 0.01）")
    parser.add_argument("--top-k", type=int, default=5,
                       help="每个查询返回前K个结果（默认: 5）")
    parser.add_argument("--min-confidence", type=float, default=0.5,
                       help="最小置信度阈值（默认: 0.5）")
    parser.add_argument("--skip-training", action="store_true",
                       help="跳过训练（如果模型已训练）")
    
    args = parser.parse_args()
    
    # 1. 加载数据
    print(f"加载数据: {args.input}")
    data = load_json_data(args.input)
    print(f"加载了 {len(data)} 条数据")
    
    # 2. 初始化KGC模块
    print(f"\n初始化KGC模块 (embedding_dim={args.embedding_dim}, use_gcn={args.use_gcn})...")
    kgc = KGCModule(data, embedding_dim=args.embedding_dim, use_gcn=args.use_gcn)
    
    # 3. 训练模型（如果需要）
    if not args.skip_training:
        print(f"\n训练模型 (epochs={args.epochs}, batch_size={args.batch_size}, lr={args.learning_rate})...")
        kgc.train(epochs=args.epochs, batch_size=args.batch_size, learning_rate=args.learning_rate)
    else:
        print("\n跳过训练（使用已训练的模型）")
    
    # 4. 加载查询
    print(f"\n加载查询: {args.queries}")
    queries = load_queries_from_file(args.queries)
    print(f"加载了 {len(queries)} 个查询")
    
    # 5. 生成预测
    predictions = generate_predictions_from_queries(
        kgc, queries, 
        top_k=args.top_k,
        min_confidence=args.min_confidence
    )
    
    # 6. 保存预测结果
    print(f"\n保存预测结果到: {args.output}")
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(predictions, f, ensure_ascii=False, indent=2)
    
    print(f"\n完成！共生成 {len(predictions)} 条预测结果")


if __name__ == "__main__":
    main()
