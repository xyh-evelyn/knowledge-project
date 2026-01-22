"""
知识图谱补全（KGC）模块
包含嵌入模块、动态子图构建、逻辑规则挖掘、GCN增强和LLM微调功能
"""

import json
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch_geometric.nn import GCNConv, MessagePassing
from torch_geometric.data import Data, Batch
from collections import defaultdict, Counter
from typing import List, Dict, Tuple, Set, Optional
import numpy as np
from tqdm import tqdm


class EmbeddingModule(nn.Module):
    """嵌入模块：为实体和关系生成嵌入向量"""
    
    def __init__(self, num_entities: int, num_relations: int, embedding_dim: int = 100):
        super(EmbeddingModule, self).__init__()
        self.embedding_dim = embedding_dim
        self.num_entities = num_entities
        self.num_relations = num_relations
        
        # 实体和关系的嵌入层
        self.entity_embedding = nn.Embedding(num_entities, embedding_dim)
        self.relation_embedding = nn.Embedding(num_relations, embedding_dim)
        
        # 初始化嵌入
        nn.init.xavier_uniform_(self.entity_embedding.weight)
        nn.init.xavier_uniform_(self.relation_embedding.weight)
    
    def forward(self, head_idx: torch.Tensor, relation_idx: torch.Tensor, tail_idx: torch.Tensor):
        """
        前向传播
        Args:
            head_idx: 头实体索引 [batch_size]
            relation_idx: 关系索引 [batch_size]
            tail_idx: 尾实体索引 [batch_size]
        Returns:
            head_embed, relation_embed, tail_embed: 嵌入向量
        """
        head_embed = self.entity_embedding(head_idx)
        relation_embed = self.relation_embedding(relation_idx)
        tail_embed = self.entity_embedding(tail_idx)
        return head_embed, relation_embed, tail_embed
    
    def get_entity_embedding(self, entity_idx: torch.Tensor):
        """获取实体嵌入"""
        return self.entity_embedding(entity_idx)
    
    def get_relation_embedding(self, relation_idx: torch.Tensor):
        """获取关系嵌入"""
        return self.relation_embedding(relation_idx)


class GCNLayer(nn.Module):
    """图卷积网络层，用于增强实体嵌入"""
    
    def __init__(self, in_channels: int, out_channels: int):
        super(GCNLayer, self).__init__()
        self.conv = GCNConv(in_channels, out_channels)
    
    def forward(self, x: torch.Tensor, edge_index: torch.Tensor):
        """
        前向传播
        Args:
            x: 节点特征 [num_nodes, in_channels]
            edge_index: 边索引 [2, num_edges]
        Returns:
            更新后的节点特征
        """
        return F.relu(self.conv(x, edge_index))


class GCNEnhancedEmbedding(nn.Module):
    """使用GCN增强的嵌入模块"""
    
    def __init__(self, num_entities: int, num_relations: int, embedding_dim: int = 100, num_gcn_layers: int = 2):
        super(GCNEnhancedEmbedding, self).__init__()
        self.embedding_dim = embedding_dim
        self.base_embedding = EmbeddingModule(num_entities, num_relations, embedding_dim)
        
        # GCN层
        self.gcn_layers = nn.ModuleList()
        for i in range(num_gcn_layers):
            if i == 0:
                self.gcn_layers.append(GCNLayer(embedding_dim, embedding_dim))
            else:
                self.gcn_layers.append(GCNLayer(embedding_dim, embedding_dim))
    
    def forward(self, head_idx: torch.Tensor, relation_idx: torch.Tensor, 
                tail_idx: torch.Tensor, edge_index: torch.Tensor = None):
        """
        前向传播，可选择是否使用GCN增强
        """
        head_embed, relation_embed, tail_embed = self.base_embedding(head_idx, relation_idx, tail_idx)
        
        if edge_index is not None:
            # 获取所有实体的嵌入
            all_entity_embeds = self.base_embedding.get_entity_embedding(
                torch.arange(self.base_embedding.num_entities, device=head_idx.device)
            )
            
            # 通过GCN层
            enhanced_embeds = all_entity_embeds
            for gcn_layer in self.gcn_layers:
                enhanced_embeds = gcn_layer(enhanced_embeds, edge_index)
            
            # 更新头尾实体嵌入
            head_embed = enhanced_embeds[head_idx]
            tail_embed = enhanced_embeds[tail_idx]
        
        return head_embed, relation_embed, tail_embed


class TransE(nn.Module):
    """TransE模型，用于知识图谱嵌入"""
    
    def __init__(self, embedding_module: EmbeddingModule, gamma: float = 1.0):
        super(TransE, self).__init__()
        self.embedding_module = embedding_module
        self.gamma = gamma
    
    def forward(self, head_idx: torch.Tensor, relation_idx: torch.Tensor, tail_idx: torch.Tensor):
        """计算TransE得分"""
        head_embed, relation_embed, tail_embed = self.embedding_module(head_idx, relation_idx, tail_idx)
        # TransE: h + r ≈ t
        score = -torch.norm(head_embed + relation_embed - tail_embed, p=2, dim=1)
        return score
    
    def predict(self, head_idx: torch.Tensor, relation_idx: torch.Tensor, 
                candidate_tails: torch.Tensor = None):
        """预测尾实体"""
        head_embed, relation_embed, _ = self.embedding_module(
            head_idx, relation_idx, torch.zeros_like(head_idx)
        )
        
        if candidate_tails is None:
            # 使用所有实体作为候选
            all_tail_embeds = self.embedding_module.get_entity_embedding(
                torch.arange(self.embedding_module.num_entities, device=head_idx.device)
            )
        else:
            all_tail_embeds = self.embedding_module.get_entity_embedding(candidate_tails)
        
        # 计算得分
        target_embed = head_embed + relation_embed
        scores = -torch.norm(target_embed.unsqueeze(1) - all_tail_embeds.unsqueeze(0), p=2, dim=2)
        return scores


class SubgraphBuilder:
    """动态子图构建器"""
    
    def __init__(self, triplets: List[List[str]]):
        """
        初始化子图构建器
        Args:
            triplets: 三元组列表，格式为 [[subject, relation, object], ...]
        """
        self.triplets = triplets
        self.entity_to_triplets = defaultdict(list)
        self._build_index()
    
    def _build_index(self):
        """构建实体到三元组的索引"""
        for idx, triplet in enumerate(self.triplets):
            subject, relation, obj = triplet
            self.entity_to_triplets[subject].append((idx, triplet))
            self.entity_to_triplets[obj].append((idx, triplet))
    
    def get_related_triplets(self, entity: str, max_depth: int = 2, max_triplets: int = 50) -> List[List[str]]:
        """
        获取与实体相关的三元组（构建子图）
        Args:
            entity: 查询实体
            max_depth: 最大深度（跳数）
            max_triplets: 最大三元组数量
        Returns:
            相关的三元组列表
        """
        visited_entities = {entity}
        related_triplets = []
        current_entities = [entity]
        
        for depth in range(max_depth):
            next_entities = set()
            for ent in current_entities:
                if ent in self.entity_to_triplets:
                    for _, triplet in self.entity_to_triplets[ent]:
                        if triplet not in related_triplets:
                            related_triplets.append(triplet)
                            # 添加新发现的实体
                            if triplet[0] not in visited_entities:
                                next_entities.add(triplet[0])
                            if triplet[2] not in visited_entities:
                                next_entities.add(triplet[2])
            
            if len(related_triplets) >= max_triplets:
                break
            
            visited_entities.update(next_entities)
            current_entities = list(next_entities)
        
        return related_triplets[:max_triplets]
    
    def get_subgraph_for_query(self, head: str, relation: str, max_triplets: int = 30) -> List[List[str]]:
        """
        为查询 (head, relation, ?) 构建子图
        Args:
            head: 头实体
            relation: 关系
            max_triplets: 最大三元组数量
        Returns:
            子图三元组列表
        """
        # 获取与头实体相关的三元组
        subgraph = self.get_related_triplets(head, max_depth=2, max_triplets=max_triplets)
        
        # 优先包含相同关系的三元组
        same_relation_triplets = [t for t in subgraph if t[1] == relation]
        other_triplets = [t for t in subgraph if t[1] != relation]
        
        # 重新排序：相同关系的在前
        return same_relation_triplets + other_triplets[:max_triplets - len(same_relation_triplets)]


class RuleMiner:
    """逻辑规则挖掘器"""
    
    def __init__(self, triplets: List[List[str]]):
        """
        初始化规则挖掘器
        Args:
            triplets: 三元组列表
        """
        self.triplets = triplets
        self.relation_patterns = defaultdict(list)
        self._mine_patterns()
    
    def _mine_patterns(self):
        """挖掘关系模式"""
        # 统计关系对的出现频率
        relation_pairs = defaultdict(int)
        entity_relation_map = defaultdict(set)
        
        for triplet in self.triplets:
            subject, relation, obj = triplet
            entity_relation_map[subject].add(relation)
            entity_relation_map[obj].add(relation)
        
        # 挖掘关系链模式
        for triplet in self.triplets:
            subject, relation1, obj = triplet
            # 查找从obj出发的其他关系
            for other_triplet in self.triplets:
                if other_triplet[0] == obj:
                    relation2 = other_triplet[1]
                    relation_pairs[(relation1, relation2)] += 1
    
    def mine_rules(self, min_support: int = 2) -> List[Dict]:
        """
        挖掘逻辑规则
        Args:
            min_support: 最小支持度
        Returns:
            规则列表，格式为 [{"premise": [r1, r2], "conclusion": r3, "support": count}, ...]
        """
        rules = []
        relation_sequences = defaultdict(int)
        
        # 构建实体关系图
        entity_relations = defaultdict(list)
        for triplet in self.triplets:
            subject, relation, obj = triplet
            entity_relations[subject].append((relation, obj))
        
        # 挖掘关系序列模式
        for entity, relations in entity_relations.items():
            if len(relations) >= 2:
                # 生成关系对
                for i, (r1, e1) in enumerate(relations):
                    for j, (r2, e2) in enumerate(relations):
                        if i != j:
                            relation_sequences[(r1, r2)] += 1
        
        # 生成规则
        for (r1, r2), support in relation_sequences.items():
            if support >= min_support:
                rules.append({
                    "premise": [r1],
                    "conclusion": r2,
                    "support": support,
                    "confidence": support / max(1, sum(1 for t in self.triplets if t[1] == r1))
                })
        
        return sorted(rules, key=lambda x: x["support"], reverse=True)
    
    def apply_rules(self, head: str, relation: str, rules: List[Dict]) -> List[str]:
        """
        应用规则进行推理
        Args:
            head: 头实体
            relation: 查询关系
            rules: 规则列表
        Returns:
            候选实体列表
        """
        candidates = []
        
        # 查找与head相关的三元组
        head_triplets = [t for t in self.triplets if t[0] == head]
        
        for rule in rules:
            premise_relation = rule["premise"][0]
            conclusion_relation = rule["conclusion"]
            
            if conclusion_relation == relation:
                # 查找满足前提的三元组
                for triplet in head_triplets:
                    if triplet[1] == premise_relation:
                        # 查找从中间实体出发的结论关系
                        intermediate_entity = triplet[2]
                        for other_triplet in self.triplets:
                            if other_triplet[0] == intermediate_entity and other_triplet[1] == conclusion_relation:
                                candidates.append(other_triplet[2])
        
        return list(set(candidates))


class LLMPromptGenerator:
    """LLM提示生成器，用于微调和推理"""
    
    def __init__(self, entity_types: Dict[str, List[str]] = None):
        """
        初始化提示生成器
        Args:
            entity_types: 实体类型字典
        """
        self.entity_types = entity_types or {}
    
    def generate_completion_prompt(self, query_entity: str, relation: str, 
                                   subgraph_triplets: List[List[str]],
                                   candidate_entities: List[str] = None,
                                   entity_embeddings: Dict[str, torch.Tensor] = None) -> str:
        """
        生成知识图谱补全的提示
        Args:
            query_entity: 查询实体
            relation: 查询关系
            subgraph_triplets: 子图三元组
            candidate_entities: 候选实体列表
            entity_embeddings: 实体嵌入字典（可选）
        Returns:
            生成的提示文本
        """
        prompt = f"""你是一个知识图谱专家。给定以下信息，预测缺失的实体。

查询：({query_entity}, {relation}, ?)

相关上下文（子图）：
"""
        # 添加子图信息
        for i, triplet in enumerate(subgraph_triplets[:10], 1):  # 限制前10个
            prompt += f"{i}. {triplet[0]} --[{triplet[1]}]--> {triplet[2]}\n"
        
        if candidate_entities:
            prompt += f"\n候选实体列表：\n"
            for i, candidate in enumerate(candidate_entities[:20], 1):  # 限制前20个
                entity_type = self._get_entity_type(candidate)
                type_info = f" ({entity_type})" if entity_type else ""
                prompt += f"{i}. {candidate}{type_info}\n"
        
        prompt += f"\n请基于上下文信息，预测 ({query_entity}, {relation}, ?) 中最可能的尾实体。"
        
        return prompt
    
    def generate_embedding_prompt(self, query_entity: str, relation: str,
                                  entity_embed: torch.Tensor,
                                  relation_embed: torch.Tensor,
                                  candidate_entities: List[str],
                                  candidate_embeddings: Dict[str, torch.Tensor]) -> str:
        """
        生成包含嵌入信息的提示
        Args:
            query_entity: 查询实体
            relation: 查询关系
            entity_embed: 实体嵌入向量
            relation_embed: 关系嵌入向量
            candidate_entities: 候选实体列表
            candidate_embeddings: 候选实体嵌入字典
        Returns:
            生成的提示文本
        """
        prompt = f"""基于嵌入向量的知识图谱补全：

查询实体：{query_entity}
查询关系：{relation}

实体嵌入向量（前10维）：{entity_embed[:10].tolist()}
关系嵌入向量（前10维）：{relation_embed[:10].tolist()}

候选实体及其嵌入（前10维）：
"""
        for candidate in candidate_entities[:10]:
            if candidate in candidate_embeddings:
                embed = candidate_embeddings[candidate][:10].tolist()
                prompt += f"- {candidate}: {embed}\n"
        
        prompt += "\n请基于嵌入向量的相似性，预测最可能的尾实体。"
        return prompt
    
    def _get_entity_type(self, entity: str) -> str:
        """获取实体类型"""
        for entity_type, entities in self.entity_types.items():
            if entity in entities:
                return entity_type
        return ""


class KGCModule:
    """知识图谱补全主模块，整合所有功能"""
    
    def __init__(self, json_data: List[Dict], embedding_dim: int = 100, use_gcn: bool = True):
        """
        初始化KGC模块
        Args:
            json_data: JSON数据列表，每个元素包含 id, text, triplets, entities
            embedding_dim: 嵌入维度
            use_gcn: 是否使用GCN增强
        """
        self.json_data = json_data
        self.embedding_dim = embedding_dim
        self.use_gcn = use_gcn
        
        # 提取所有三元组
        self.all_triplets = []
        self.all_entities = set()
        self.all_relations = set()
        self.entity_types = {}
        
        self._extract_data()
        
        # 构建索引映射
        self.entity_to_idx = {entity: idx for idx, entity in enumerate(sorted(self.all_entities))}
        self.idx_to_entity = {idx: entity for entity, idx in self.entity_to_idx.items()}
        self.relation_to_idx = {relation: idx for idx, relation in enumerate(sorted(self.all_relations))}
        self.idx_to_relation = {idx: relation for relation, idx in self.relation_to_idx.items()}
        
        # 初始化组件
        if use_gcn:
            self.embedding_module = GCNEnhancedEmbedding(
                len(self.all_entities), len(self.all_relations), embedding_dim
            )
        else:
            self.embedding_module = EmbeddingModule(
                len(self.all_entities), len(self.all_relations), embedding_dim
            )
        
        self.transe_model = TransE(self.embedding_module.base_embedding if use_gcn else self.embedding_module)
        self.subgraph_builder = SubgraphBuilder(self.all_triplets)
        self.rule_miner = RuleMiner(self.all_triplets)
        self.prompt_generator = LLMPromptGenerator(self.entity_types)
        
        # 构建图结构（用于GCN）
        self.edge_index = self._build_edge_index()
    
    def _extract_data(self):
        """从JSON数据中提取三元组、实体和关系"""
        for item in self.json_data:
            # 提取三元组
            if "triplets" in item:
                for triplet in item["triplets"]:
                    if len(triplet) == 3:
                        self.all_triplets.append(triplet)
                        self.all_entities.add(triplet[0])
                        self.all_entities.add(triplet[2])
                        self.all_relations.add(triplet[1])
            
            # 提取实体类型信息
            if "entities" in item:
                for entity_type, entities in item["entities"].items():
                    if entity_type not in self.entity_types:
                        self.entity_types[entity_type] = []
                    self.entity_types[entity_type].extend(entities)
    
    def _build_edge_index(self) -> torch.Tensor:
        """构建边索引（用于GCN）"""
        edges = []
        for triplet in self.all_triplets:
            head_idx = self.entity_to_idx[triplet[0]]
            tail_idx = self.entity_to_idx[triplet[2]]
            edges.append([head_idx, tail_idx])
            # 添加反向边（无向图）
            edges.append([tail_idx, head_idx])
        
        if len(edges) == 0:
            return torch.empty((2, 0), dtype=torch.long)
        
        edge_index = torch.tensor(edges, dtype=torch.long).t().contiguous()
        return edge_index
    
    def train(self, epochs: int = 50, batch_size: int = 32, learning_rate: float = 0.01):
        """训练嵌入模型"""
        optimizer = torch.optim.Adam(self.embedding_module.parameters(), lr=learning_rate)
        
        # 准备训练数据
        train_data = []
        for triplet in self.all_triplets:
            head_idx = self.entity_to_idx[triplet[0]]
            relation_idx = self.relation_to_idx[triplet[1]]
            tail_idx = self.entity_to_idx[triplet[2]]
            train_data.append((head_idx, relation_idx, tail_idx))
        
        print(f"开始训练，共 {len(train_data)} 个三元组，{epochs} 个epochs")
        
        for epoch in range(epochs):
            total_loss = 0
            # 随机打乱数据
            np.random.shuffle(train_data)
            
            for i in range(0, len(train_data), batch_size):
                batch = train_data[i:i+batch_size]
                if len(batch) == 0:
                    continue
                
                head_indices = torch.tensor([x[0] for x in batch], dtype=torch.long)
                relation_indices = torch.tensor([x[1] for x in batch], dtype=torch.long)
                tail_indices = torch.tensor([x[2] for x in batch], dtype=torch.long)
                
                # 生成负样本
                neg_tail_indices = torch.randint(0, len(self.all_entities), (len(batch),))
                
                optimizer.zero_grad()
                
                # 正样本得分
                pos_scores = self.transe_model(head_indices, relation_indices, tail_indices)
                
                # 负样本得分
                neg_scores = self.transe_model(head_indices, relation_indices, neg_tail_indices)
                
                # TransE损失：最大化正样本得分，最小化负样本得分
                loss = F.relu(self.transe_model.gamma - pos_scores + neg_scores).mean()
                
                loss.backward()
                optimizer.step()
                
                total_loss += loss.item()
            
            if (epoch + 1) % 10 == 0:
                avg_loss = total_loss / (len(train_data) // batch_size + 1)
                print(f"Epoch {epoch+1}/{epochs}, 平均损失: {avg_loss:.4f}")
    
    def predict(self, head: str, relation: str, top_k: int = 10, 
                use_subgraph: bool = True, use_rules: bool = True) -> List[Tuple[str, float]]:
        """
        预测尾实体
        Args:
            head: 头实体
            relation: 关系
            top_k: 返回前k个结果
            use_subgraph: 是否使用子图信息
            use_rules: 是否使用规则推理
        Returns:
            [(实体, 得分), ...] 列表
        """
        if head not in self.entity_to_idx or relation not in self.relation_to_idx:
            return []
        
        head_idx = torch.tensor([self.entity_to_idx[head]], dtype=torch.long)
        relation_idx = torch.tensor([self.relation_to_idx[relation]], dtype=torch.long)
        
        # 使用TransE模型预测
        with torch.no_grad():
            if self.use_gcn and self.edge_index.numel() > 0:
                edge_index = self.edge_index
            else:
                edge_index = None
            
            scores = self.transe_model.predict(head_idx, relation_idx)
            scores = scores[0]  # 取第一个（也是唯一的）查询的结果
        
        # 获取候选实体
        candidate_scores = []
        for idx, score in enumerate(scores):
            entity = self.idx_to_entity[idx]
            candidate_scores.append((entity, score.item()))
        
        # 按得分排序
        candidate_scores.sort(key=lambda x: x[1], reverse=True)
        
        # 应用规则过滤和增强
        if use_rules:
            rules = self.rule_miner.mine_rules(min_support=2)
            rule_candidates = self.rule_miner.apply_rules(head, relation, rules)
            # 提升规则推导出的候选实体得分
            rule_candidates_set = set(rule_candidates)
            for i, (entity, score) in enumerate(candidate_scores):
                if entity in rule_candidates_set:
                    candidate_scores[i] = (entity, score + 0.5)  # 增加得分
            candidate_scores.sort(key=lambda x: x[1], reverse=True)
        
        return candidate_scores[:top_k]
    
    def generate_llm_prompt(self, head: str, relation: str, top_k_candidates: int = 20) -> str:
        """
        生成LLM提示
        Args:
            head: 头实体
            relation: 关系
            top_k_candidates: 候选实体数量
        Returns:
            生成的提示文本
        """
        # 获取子图
        subgraph = self.subgraph_builder.get_subgraph_for_query(head, relation)
        
        # 获取预测结果
        predictions = self.predict(head, relation, top_k=top_k_candidates)
        candidate_entities = [pred[0] for pred in predictions]
        
        # 获取嵌入向量（如果可用）
        entity_embeddings = {}
        if head in self.entity_to_idx:
            head_idx = torch.tensor([self.entity_to_idx[head]], dtype=torch.long)
            # 兼容GCN增强和普通嵌入模块
            base_embedding = getattr(self.embedding_module, 'base_embedding', self.embedding_module)
            head_embed = base_embedding.get_entity_embedding(head_idx)[0]
            entity_embeddings[head] = head_embed
        
        relation_embeddings = None
        if relation in self.relation_to_idx:
            relation_idx = torch.tensor([self.relation_to_idx[relation]], dtype=torch.long)
            # 兼容GCN增强和普通嵌入模块
            base_embedding = getattr(self.embedding_module, 'base_embedding', self.embedding_module)
            relation_embed = base_embedding.get_relation_embedding(relation_idx)[0]
            relation_embeddings = relation_embed
        
        # 生成提示
        prompt = self.prompt_generator.generate_completion_prompt(
            head, relation, subgraph, candidate_entities, entity_embeddings
        )
        
        return prompt
    
    def get_mined_rules(self, min_support: int = 2, top_k: int = 20) -> List[Dict]:
        """获取挖掘的规则"""
        rules = self.rule_miner.mine_rules(min_support=min_support)
        return rules[:top_k]


def load_json_data(file_path: str) -> List[Dict]:
    """加载JSON数据"""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


if __name__ == "__main__":
    # 示例用法
    print("KGC模块已加载，请使用 KGCModule 类进行知识图谱补全。")
