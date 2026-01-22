"""
KGC 结果回写 + Neo4j 增量同步模块

功能：
1. 将 KGC 推理得到的新增三元组增量合并回 triplets_completed.json
2. 将新增三元组以增量方式写入 Neo4j
3. 全流程不重复、不破坏原始数据、可追踪来源
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Tuple, Set, Optional
from tqdm import tqdm
from neo4j import GraphDatabase


def sanitize_rel(rel: str) -> str:
    """
    关系类型清洗：将原始关系谓词转换为 Neo4j 支持的合法关系类型
    Neo4j 关系类型规则：只能包含字母、数字、下划线，且必须以字母开头
    """
    s = re.sub(r"\W+", "_", str(rel)).strip('_')
    if not s:
        s = 'REL'
    if not re.match(r'^[A-Za-z]', s):
        s = 'R_' + s
    return s.upper()


class KGCIncrementalSync:
    """KGC 增量同步主类"""
    
    def __init__(self, 
                 input_json: str = "triplets_completed.json",
                 output_json: str = "triplets_completed_augmented.json",
                 neo4j_uri: str = "bolt+ssc://01093ec9.databases.neo4j.io",
                 neo4j_user: str = "neo4j",
                 neo4j_password: str = "z1coGZt4IPa-kWQ6ENK0tLjvOy47mIuySYXfxWSwtRQ",
                 neo4j_database: str = "neo4j",
                 dry_run: bool = False):
        """
        初始化增量同步模块
        
        Args:
            input_json: 输入JSON文件路径
            output_json: 输出JSON文件路径
            neo4j_uri: Neo4j连接地址
            neo4j_user: Neo4j用户名
            neo4j_password: Neo4j密码
            neo4j_database: Neo4j数据库名称（可选）
            dry_run: 是否为干运行模式（仅打印，不写入）
        """
        self.input_json = input_json
        self.output_json = output_json
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.neo4j_database = neo4j_database
        self.dry_run = dry_run
        
        # 统计信息
        self.stats = {
            "total_kgc_triplets": 0,
            "added_to_json": 0,
            "skipped_duplicate": 0,
            "entities_added": 0,
            "neo4j_nodes_created": 0,
            "neo4j_nodes_merged": 0,
            "neo4j_rels_created": 0,
            "neo4j_rels_merged": 0,
            "entries_enhanced": 0
        }
        
        # 日志列表
        self.logs = []
    
    def _log(self, message: str, level: str = "INFO"):
        """记录日志"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}"
        self.logs.append(log_entry)
        print(log_entry)
    
    def _normalize_triplet(self, triplet: Tuple[str, str, str]) -> Tuple[str, str, str]:
        """标准化三元组（去除空白字符）"""
        return (triplet[0].strip(), triplet[1].strip(), triplet[2].strip())
    
    def _triplet_exists(self, triplet: Tuple[str, str, str], existing_triplets: List[List[str]]) -> bool:
        """检查三元组是否已存在"""
        normalized = self._normalize_triplet(triplet)
        for existing in existing_triplets:
            if len(existing) >= 3:
                existing_normalized = self._normalize_triplet((existing[0], existing[1], existing[2]))
                if normalized == existing_normalized:
                    return True
        return False
    
    def _has_entity_overlap(self, triplet: Tuple[str, str, str], 
                            text: str, entities: Dict[str, List[str]]) -> bool:
        """
        判断三元组是否与entry有实体重叠
        
        Args:
            triplet: 三元组 (head, relation, tail)
            text: 文本内容
            entities: 实体字典
            
        Returns:
            是否有重叠
        """
        head, relation, tail = triplet
        
        # 检查实体是否在文本中
        if head in text or tail in text:
            return True
        
        # 检查实体是否在entities中
        all_entities = []
        for entity_list in entities.values():
            all_entities.extend(entity_list)
        
        if head in all_entities or tail in all_entities:
            return True
        
        # 检查部分匹配（实体包含关系）
        for entity in all_entities:
            if head in entity or entity in head:
                return True
            if tail in entity or entity in tail:
                return True
        
        return False
    
    def _add_entity_to_dict(self, entity: str, entities: Dict[str, List[str]], 
                           entity_type: str = "Inferred"):
        """将实体添加到entities字典"""
        if entity_type not in entities:
            entities[entity_type] = []
        
        # 检查是否已存在
        if entity not in entities[entity_type]:
            entities[entity_type].append(entity)
            self.stats["entities_added"] += 1
            return True
        return False
    
    def merge_kgc_triplets_to_json(self, kgc_triplets: List[Tuple[str, str, str]], 
                                   confidences: Optional[List[float]] = None) -> Dict:
        """
        将KGC三元组增量合并到JSON数据
        
        Args:
            kgc_triplets: KGC预测的三元组列表，格式为 [(head, relation, tail), ...]
            confidences: 对应的置信度列表（可选）
            
        Returns:
            更新后的数据字典
        """
        self._log(f"开始合并 {len(kgc_triplets)} 条KGC三元组到JSON")
        
        # 加载原始数据
        with open(self.input_json, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        self.stats["total_kgc_triplets"] = len(kgc_triplets)
        
        # 如果没有提供置信度，默认使用0.8
        if confidences is None:
            confidences = [0.8] * len(kgc_triplets)
        elif len(confidences) != len(kgc_triplets):
            self._log(f"警告：置信度数量({len(confidences)})与三元组数量({len(kgc_triplets)})不匹配，使用默认值", "WARN")
            confidences = [0.8] * len(kgc_triplets)
        
        # 获取当前时间戳
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        # 遍历每个entry
        for entry in tqdm(data, desc="合并KGC三元组"):
            entry_id = entry.get("id", "unknown")
            text = entry.get("text", "")
            triplets = entry.get("triplets", [])
            entities = entry.get("entities", {})
            
            # 初始化kgc_triplets字段（如果不存在）
            if "kgc_triplets" not in entry:
                entry["kgc_triplets"] = []
            
            entry_enhanced = False
            
            # 遍历KGC三元组
            for idx, kgc_triplet in enumerate(kgc_triplets):
                head, relation, tail = kgc_triplet
                
                # 检查是否与当前entry相关
                if not self._has_entity_overlap(kgc_triplet, text, entities):
                    continue
                
                # 检查是否已存在（去重）
                if self._triplet_exists(kgc_triplet, triplets):
                    self.stats["skipped_duplicate"] += 1
                    self._log(f"Entry {entry_id}: 跳过重复三元组 {kgc_triplet}", "DEBUG")
                    continue
                
                # 检查kgc_triplets中是否已存在
                kgc_exists = False
                for existing_kgc in entry["kgc_triplets"]:
                    existing_triple = existing_kgc.get("triple", [])
                    if len(existing_triple) >= 3:
                        if self._normalize_triplet(kgc_triplet) == self._normalize_triplet(
                            (existing_triple[0], existing_triple[1], existing_triple[2])
                        ):
                            kgc_exists = True
                            break
                
                if kgc_exists:
                    self.stats["skipped_duplicate"] += 1
                    continue
                
                # 添加新的KGC三元组
                kgc_entry = {
                    "triple": list(kgc_triplet),
                    "source": "KGC",
                    "confidence": confidences[idx],
                    "timestamp": timestamp
                }
                entry["kgc_triplets"].append(kgc_entry)
                self.stats["added_to_json"] += 1
                entry_enhanced = True
                
                # 更新entities
                # 检查head是否在entities中
                head_found = False
                for entity_list in entities.values():
                    if head in entity_list:
                        head_found = True
                        break
                
                if not head_found:
                    self._add_entity_to_dict(head, entities, "Inferred")
                
                # 检查tail是否在entities中
                tail_found = False
                for entity_list in entities.values():
                    if tail in entity_list:
                        tail_found = True
                        break
                
                if not tail_found:
                    self._add_entity_to_dict(tail, entities, "Inferred")
            
            if entry_enhanced:
                self.stats["entries_enhanced"] += 1
                entry["entities"] = entities  # 更新entities
        
        # 保存更新后的数据
        if not self.dry_run:
            with open(self.output_json, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self._log(f"已保存更新后的数据到 {self.output_json}")
        else:
            self._log(f"[DRY RUN] 将保存更新后的数据到 {self.output_json}")
        
        return data
    
    def sync_to_neo4j(self, kgc_triplets: List[Tuple[str, str, str]], 
                      confidences: Optional[List[float]] = None):
        """
        将KGC三元组增量同步到Neo4j
        
        Args:
            kgc_triplets: KGC预测的三元组列表
            confidences: 对应的置信度列表（可选）
        """
        if self.dry_run:
            self._log("[DRY RUN] 跳过Neo4j同步")
            return
        
        if not self.neo4j_password:
            self._log("未提供Neo4j密码，跳过Neo4j同步", "WARN")
            return
        
        self._log(f"开始同步 {len(kgc_triplets)} 条KGC三元组到Neo4j")
        
        # 如果没有提供置信度，默认使用0.8
        if confidences is None:
            confidences = [0.8] * len(kgc_triplets)
        elif len(confidences) != len(kgc_triplets):
            self._log(f"警告：置信度数量不匹配，使用默认值", "WARN")
            confidences = [0.8] * len(kgc_triplets)
        
        # 初始化Neo4j驱动
        driver = GraphDatabase.driver(self.neo4j_uri, auth=(self.neo4j_user, self.neo4j_password))
        
        timestamp = datetime.now().strftime("%Y-%m-%d")
        
        def sync_batch(tx):
            """批量同步函数"""
            for idx, triplet in enumerate(tqdm(kgc_triplets, desc="同步到Neo4j")):
                head, relation, tail = triplet
                confidence = confidences[idx]
                
                # 清洗关系类型
                rel_type = sanitize_rel(relation)
                
                # 检查关系是否已存在（检查是否有source='KGC'的关系）
                check_cypher = (
                    f"MATCH (h:Entity {{name: $head}})-[r:{rel_type}]->(t:Entity {{name: $tail}}) "
                    f"WHERE r.source = 'KGC' "
                    f"RETURN r"
                )
                result = tx.run(check_cypher, head=head, tail=tail)
                
                if result.single():
                    # 关系已存在，跳过
                    self.stats["neo4j_rels_merged"] += 1
                    continue
                
                # 创建或合并节点和关系
                # 使用MERGE确保节点存在，但只在创建时设置type
                # 如果节点已存在但type为空，也更新为Inferred（可选）
                cypher = (
                    f"MERGE (h:Entity {{name: $head}}) "
                    f"ON CREATE SET h.type = COALESCE(h.type, 'Inferred') "
                    f"MERGE (t:Entity {{name: $tail}}) "
                    f"ON CREATE SET t.type = COALESCE(t.type, 'Inferred') "
                    f"WITH h, t "
                    f"MERGE (h)-[r:{rel_type}]->(t) "
                    f"ON CREATE SET "
                    f"  r.source = 'KGC', "
                    f"  r.confidence = $confidence, "
                    f"  r.timestamp = $timestamp, "
                    f"  r.name = $relation"
                )
                
                result = tx.run(cypher, 
                              head=head, 
                              tail=tail, 
                              relation=relation,
                              confidence=confidence,
                              timestamp=timestamp)
                
                # 检查是否创建了新关系
                # 由于使用了ON CREATE，如果关系已存在但source不是KGC，不会更新
                # 这里简化处理，假设执行成功就是创建了
                self.stats["neo4j_rels_created"] += 1
        
        # 执行同步
        try:
            if self.neo4j_database:
                with driver.session(database=self.neo4j_database) as session:
                    session.execute_write(sync_batch)
            else:
                with driver.session() as session:
                    session.execute_write(sync_batch)
            self._log("Neo4j同步完成")
        except Exception as e:
            self._log(f"Neo4j同步失败: {str(e)}", "ERROR")
            raise
        finally:
            driver.close()
    
    def process(self, kgc_triplets: List[Tuple[str, str, str]], 
                confidences: Optional[List[float]] = None):
        """
        完整处理流程：合并JSON + 同步Neo4j
        
        Args:
            kgc_triplets: KGC预测的三元组列表
            confidences: 对应的置信度列表（可选）
        """
        self._log("=" * 60)
        self._log("开始KGC增量同步流程")
        self._log("=" * 60)
        
        # 步骤1：合并到JSON
        self._log("\n步骤1: 合并KGC三元组到JSON")
        updated_data = self.merge_kgc_triplets_to_json(kgc_triplets, confidences)
        
        # 步骤2：同步到Neo4j
        self._log("\n步骤2: 同步KGC三元组到Neo4j")
        self.sync_to_neo4j(kgc_triplets, confidences)
        
        # 打印统计信息
        self._log("\n" + "=" * 60)
        self._log("处理完成！统计信息：")
        self._log("=" * 60)
        self._log(f"KGC三元组总数: {self.stats['total_kgc_triplets']}")
        self._log(f"添加到JSON: {self.stats['added_to_json']}")
        self._log(f"跳过重复: {self.stats['skipped_duplicate']}")
        self._log(f"新增实体: {self.stats['entities_added']}")
        self._log(f"增强的Entry数: {self.stats['entries_enhanced']}")
        self._log(f"Neo4j关系创建: {self.stats['neo4j_rels_created']}")
        self._log(f"Neo4j关系合并: {self.stats['neo4j_rels_merged']}")
        self._log("=" * 60)
        
        return updated_data
    
    def save_logs(self, log_file: str = "kgc_sync_log.txt"):
        """保存日志到文件"""
        with open(log_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(self.logs))
        self._log(f"日志已保存到 {log_file}")


def load_kgc_predictions(predictions_file: str) -> Tuple[List[Tuple[str, str, str]], List[float]]:
    """
    加载KGC预测结果
    
    支持格式：
    1. JSON格式: [{"head": "...", "relation": "...", "tail": "...", "confidence": 0.87}, ...]
    2. 简单列表格式: [["head", "relation", "tail"], ...]
    3. 元组格式: [("head", "relation", "tail"), ...]
    
    Args:
        predictions_file: 预测结果文件路径
        
    Returns:
        (三元组列表, 置信度列表)
    """
    with open(predictions_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    triplets = []
    confidences = []
    
    for item in data:
        if isinstance(item, list) and len(item) >= 3:
            # 简单列表格式
            triplets.append((item[0], item[1], item[2]))
            confidences.append(item[3] if len(item) > 3 else 0.8)
        elif isinstance(item, dict):
            # JSON对象格式
            head = item.get("head") or item.get("subject") or item.get("head_entity")
            relation = item.get("relation") or item.get("predicate")
            tail = item.get("tail") or item.get("object") or item.get("tail_entity")
            confidence = item.get("confidence", 0.8)
            
            if head and relation and tail:
                triplets.append((head, relation, tail))
                confidences.append(confidence)
        elif isinstance(item, tuple) and len(item) >= 3:
            # 元组格式
            triplets.append(item)
            confidences.append(0.8)
    
    return triplets, confidences


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="KGC增量同步工具")
    parser.add_argument("--kgc-predictions", "-k", required=True, 
                       help="KGC预测结果文件路径（JSON格式）")
    parser.add_argument("--input", "-i", default="triplets_completed.json",
                       help="输入JSON文件路径（默认: triplets_completed.json）")
    parser.add_argument("--output", "-o", default="triplets_completed_augmented.json",
                       help="输出JSON文件路径（默认: triplets_completed_augmented.json）")
    parser.add_argument("--neo4j-uri", default="bolt+ssc://01093ec9.databases.neo4j.io",
                       help="Neo4j连接地址（默认: bolt+ssc://01093ec9.databases.neo4j.io）")
    parser.add_argument("--neo4j-user", default="neo4j",
                       help="Neo4j用户名（默认: neo4j）")
    parser.add_argument("--neo4j-password", 
                       help="Neo4j密码（从环境变量读取或命令行提供）")
    parser.add_argument("--neo4j-database", default="neo4j",
                       help="Neo4j数据库名称（可选）")
    parser.add_argument("--dry-run", action="store_true",
                       help="干运行模式（仅打印，不写入）")
    parser.add_argument("--log-file", default="kgc_sync_log.txt",
                       help="日志文件路径（默认: kgc_sync_log.txt）")
    
    args = parser.parse_args()
    
    # 从环境变量读取密码（如果未提供）
    if not args.neo4j_password:
        import os
        args.neo4j_password = os.getenv("NEO4J_PASSWORD")
    
    # 加载KGC预测结果
    print(f"加载KGC预测结果: {args.kgc_predictions}")
    kgc_triplets, confidences = load_kgc_predictions(args.kgc_predictions)
    print(f"加载了 {len(kgc_triplets)} 条三元组")
    
    # 创建同步对象
    sync = KGCIncrementalSync(
        input_json=args.input,
        output_json=args.output,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        neo4j_database=args.neo4j_database,
        dry_run=args.dry_run
    )
    
    # 执行处理
    sync.process(kgc_triplets, confidences)
    
    # 保存日志
    sync.save_logs(args.log_file)
