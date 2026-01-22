# 城市规划知识图谱构建系统

本仓库实现了从原始文本到 Neo4j 知识图谱的完整流程，涵盖文本预处理、LLM 驱动的命名实体识别（NER）、关系抽取（RE）、三元组清洗优化以及 Neo4j 可视化。系统特别针对**孤岛三元组问题**进行了优化，通过实体归一化、间接关联挖掘和关联补全等技术，显著提升图谱连通性。

---

## 📋 目录

- [核心特性](#核心特性)
- [项目结构](#项目结构)
- [环境准备](#环境准备)
- [快速开始](#快速开始)
- [完整流程](#完整流程)
- [核心改进](#核心改进)
- [脚本说明](#脚本说明)
- [Neo4j 导入](#neo4j-导入)
- [GitHub 发布](#github-发布)
- [常见问题](#常见问题)

---

## ✨ 核心特性

### 1. **端到端知识图谱构建**
- PDF/文本预处理与分块
- LLM 驱动的实体识别（NER）
- LLM 驱动的关系抽取（RE）
- 三元组清洗与标准化
- Neo4j 知识图谱可视化

### 2. **孤岛问题优化**（核心改进）
- ✅ **实体归一化**：文本内同义合并与指代消解，解决"同体异名"问题
- ✅ **间接关联挖掘**：基于文本上下文挖掘隐含关联，提升图谱连通性
- ✅ **关系谓词标准化**：统一同义关系，减少路径碎片化
- ✅ **关联补全**：基于实体关系网络自动补全合法的间接关联

### 3. **严格文本边界约束**
- 所有实体/关系完全来自输入文本，无外部知识库引入
- 所有新增关联可追溯到文本中的具体句子
- 保留原始数据，支持验证和回滚

### 4. **知识图谱补全（KGC）**（新增功能）
- ✅ **嵌入学习**：使用 TransE 模型学习实体和关系的嵌入向量
- ✅ **GCN 增强**：可选使用图卷积网络（GCN）增强实体嵌入
- ✅ **动态子图构建**：为每个查询动态构建相关子图
- ✅ **逻辑规则挖掘**：自动从三元组中挖掘关系模式用于推理
- ✅ **LLM 集成**：生成包含嵌入和子图信息的 LLM 提示，支持微调和推理

---

## 📁 项目结构

```
knowledgeProject/
├─ src/                          # 核心模块（可复用）
│  ├─ pdf_processing.py          # 文本/PDF 分块处理
│  ├─ ner_llm.py                 # LLM 驱动实体识别（含实体归一化）
│  ├─ relation_extraction.py     # LLM 驱动关系抽取（支持间接关联）
│  ├─ prompt_builder.py          # 统一 prompt 构造
│  ├─ spacy_nlp.py               # 句法特征抽取（性能优化）
│  ├─ pipeline_orchestrator.py   # 端到端管道协调器
│  ├─ neo4j_import.py            # Neo4j 导入接口
│  ├─ demo_local.py              # 离线演示模块
│  └─ kgc_module.py              # 知识图谱补全模块（KGC）
│
├─ scripts/                      # 辅助脚本
│  ├─ show_triplets.py           # 三元组统计与展示
│  ├─ generate_processed_texts.py # 批量文本处理
│  └─ inspect_processed.py       # 中间结果检查
│
├─ tests/                        # 单元测试
│  ├─ test_spacy_nlp.py
│  └─ test_spacy_nlp_extra.py
│
├─ input/                        # 输入文件目录
│  └─ text1.txt                  # 示例文本文件
│
├─ clean_triplets.py             # 三元组清洗与标准化
├─ triplet_link_completion.py    # 关联补全脚本（解决孤岛问题）
├─ kgc_example.py                # KGC 模块使用示例
├─ main.py                       # 命令行入口（分阶段运行）
├─ requirements.txt              # 依赖列表
├─ README.md                     # 本文档
└─ .gitignore                    # Git 忽略规则
```

---

## 🔧 环境准备

### 1. **克隆仓库**

```powershell
git clone https://github.com/<your-username>/knowledgeProject.git
cd knowledgeProject
```

### 2. **创建虚拟环境**

```powershell
# Windows PowerShell
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/Mac
python -m venv .venv
source .venv/bin/activate
```

### 3. **安装依赖**

```powershell
# 安装 Python 依赖包
pip install -r requirements.txt

# 安装 spaCy 中文模型（必需）
python -m spacy download zh_core_web_sm

# 注意：KGC 模块需要 PyTorch 和 PyTorch Geometric
# 如果安装失败，可以单独安装：
# pip install torch torch-geometric numpy
```

### 4. **配置环境变量**

```powershell
# LLM API 配置（OpenAI 或兼容接口）
$env:OPENAI_API_KEY="your-api-key"
$env:GRAPHRAG_API_BASE="https://api.siliconflow.cn/v1"  # 可选
$env:GRAPHRAG_CHAT_MODEL="gpt-4o"  # 可选

# Neo4j 配置（可选，导入时使用）
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USERNAME="neo4j"
$env:NEO4J_PASSWORD="your-password"
```

---

## 🚀 快速开始

### 完整运行流程（带详细注释）

以下是完整的运行流程，包含所有步骤和详细注释：

```powershell
# ============================================
# 步骤 0：环境准备
# ============================================

# 激活虚拟环境（如果使用）
.\.venv\Scripts\Activate.ps1

# 安装依赖（首次运行）
pip install -r requirements.txt

# 安装 spaCy 中文模型（必需）
python -m spacy download zh_core_web_sm

# 配置环境变量（LLM API，必需）
$env:OPENAI_API_KEY="your-api-key-here"
# 可选：使用第三方 API
$env:GRAPHRAG_API_BASE="https://api.siliconflow.cn/v1"
$env:GRAPHRAG_CHAT_MODEL="gpt-4o"

# 配置 Neo4j 环境变量（可选，导入时使用）
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_USERNAME="neo4j"
$env:NEO4J_PASSWORD="your-neo4j-password"

# ============================================
# 步骤 1：数据预处理
# ============================================
# 功能：将原始文本文件分块处理，生成 processed_texts.json
# 输入：input/text1.txt（或其他文本文件）
# 输出：processed_texts.json（分块后的文本数据）

python main.py data --text input\text1.txt

# 或者直接使用模块：
# python -m src.pdf_processing --text input\text1.txt --output processed_texts.json

# ============================================
# 步骤 2：实体识别（NER）
# ============================================
# 功能：使用 LLM 识别文本中的实体，并进行归一化处理
# 输入：processed_texts.json
# 输出：entities_extracted.json（包含实体和别名映射）
# 注意：需要配置 OPENAI_API_KEY 环境变量

python main.py ner

# 或者直接使用模块：
# python -m src.ner_llm --input processed_texts.json --output entities_extracted.json

# ============================================
# 步骤 3：关系抽取（RE）
# ============================================
# 功能：使用 LLM 抽取实体之间的关系，支持间接关联挖掘
# 输入：entities_extracted.json
# 输出：triplets_final.json（三元组数据）
# 注意：需要配置 OPENAI_API_KEY 环境变量

python main.py re

# 或者直接使用模块：
# python -m src.relation_extraction --input entities_extracted.json --output triplets_final.json

# ============================================
# 步骤 4：三元组清洗
# ============================================
# 功能：清洗和标准化三元组，合并同义关系
# 输入：triplets_final.json
# 输出：triplets_cleaned.json（清洗后的三元组）
#        relation_merge_map.json（关系合并对照表）

python clean_triplets.py --input triplets_final.json --output triplets_cleaned.json

# ============================================
# 步骤 5：关联补全（可选）
# ============================================
# 功能：补全孤岛三元组，提升图谱连通性
# 输入：triplets_cleaned.json
# 输出：triplets_completed.json（补全后的三元组）
# 说明：此步骤可以解决孤岛问题，建议运行

python triplet_link_completion.py --input triplets_cleaned.json --output triplets_completed.json

# ============================================
# 步骤 6：导入 Neo4j（可选）
# ============================================
# 功能：将三元组导入 Neo4j 数据库进行可视化
# 输入：triplets_completed.json
# 输出：Neo4j 知识图谱
# 注意：需要 Neo4j 服务正在运行，并配置环境变量

python main.py import --neo4j-password $env:NEO4J_PASSWORD

# 或者直接使用模块：
# python -m src.neo4j_import --input triplets_completed.json `
#   --uri bolt://localhost:7687 `
#   --user neo4j `
#   --password $env:NEO4J_PASSWORD

# ============================================
# 步骤 7：知识图谱补全（KGC，可选）
# ============================================
# 功能：使用嵌入学习和 GCN 进行知识图谱补全
# 输入：triplets_completed.json
# 输出：训练好的模型、预测结果、规则、LLM 提示
# 说明：此步骤需要 PyTorch 和 PyTorch Geometric

# 方式一：运行完整示例（推荐）
python kgc_example.py

# 方式二：在 Python 代码中使用（见下方详细说明）
```

### 方式一：分阶段运行（推荐）

```powershell
# 1. 数据预处理
python main.py data --text input\text1.txt

# 2. 实体识别（需配置 LLM）
python main.py ner

# 3. 关系抽取
python main.py re

# 4. 三元组清洗
python clean_triplets.py --input triplets_final.json --output triplets_cleaned.json

# 5. 关联补全（可选，解决孤岛问题）
python triplet_link_completion.py --input triplets_cleaned.json --output triplets_completed.json

# 6. 导入 Neo4j
python main.py import --neo4j-password $env:NEO4J_PASSWORD

# 7. 知识图谱补全（KGC，可选）
python kgc_example.py
```

### 方式二：一键全流程

```powershell
# 自动执行 data -> ner -> re -> import
python main.py all --text input\text1.txt --neo4j-password $env:NEO4J_PASSWORD
```

### 方式三：使用 Pipeline Orchestrator

```powershell
# 离线演示模式（无需 LLM）
python -m src.pipeline_orchestrator --text input\text1.txt --mode demo

# LLM 模式（需配置 API）
python -m src.pipeline_orchestrator --text input\text1.txt --mode llm `
  --import-neo4j `
  --neo4j-uri bolt://localhost:7687 `
  --neo4j-user neo4j `
  --neo4j-password $env:NEO4J_PASSWORD
```

---

## 🔄 完整流程

### 流程概览

```
原始文本 (input/text1.txt)
    ↓
[1] 文本分块 (processed_texts.json)
    ↓
[2] 实体识别 + 归一化 (entities_extracted.json)
    ↓
[3] 关系抽取 + 间接关联挖掘 (triplets_final.json)
    ↓
[4] 三元组清洗 + 关系标准化 (triplets_cleaned.json)
    ↓
[5] 关联补全（可选）(triplets_completed.json)
    ↓
[6] Neo4j 导入
    ↓
知识图谱可视化
    ↓
[7] 知识图谱补全（KGC，可选）
    ↓
嵌入学习 + 预测 + LLM 推理
```

### 详细步骤说明

#### 步骤 1：文本预处理

```powershell
python -m src.pdf_processing --text input\text1.txt --output processed_texts.json
```

- 输入：原始文本文件（.txt）或 PDF 文件
- 输出：分块后的 JSON 文件（每块约 512 tokens）
- 功能：文本清洗、句子分割、按 token 分块

#### 步骤 2：实体识别（含归一化）

```powershell
python -m src.ner_llm --input processed_texts.json --output entities_extracted.json
```

- 输入：分块文本 JSON
- 输出：实体抽取结果 JSON（含 `entity_aliases` 字段）
- **核心改进**：
  - 实体归一化：文本内同义合并（如"南沙新区"→"南沙区"）
  - 指代消解：识别"该区"、"该片区"等指代性实体
  - 输出别名映射，便于后续关系抽取使用

#### 步骤 3：关系抽取（支持间接关联）

```powershell
python -m src.relation_extraction --input entities_extracted.json --output triplets_final.json
```

- 输入：实体抽取结果 JSON
- 输出：三元组 JSON 文件
- **核心改进**：
  - 间接关联挖掘：提取"A的B"隐含的包含关系
  - 链式关联：基于已有关联推断间接路径
  - 共现关联：谨慎使用，仅用于连通节点

#### 步骤 4：三元组清洗

```powershell
python clean_triplets.py --input triplets_final.json --output triplets_cleaned.json --merge-map relation_merge_map.json
```

- 输入：原始三元组 JSON
- 输出：清洗后的三元组 JSON + 关系合并对照表
- **核心改进**：
  - 关系谓词标准化：合并同义关系（如"改造为"→"改造"）
  - 最大化保留有效三元组（包括孤点实体）
  - 仅剔除明显无效数据（占位、乱码等）

#### 步骤 5：关联补全（可选）

```powershell
python triplet_link_completion.py --input triplets_cleaned.json --output triplets_completed.json
```

- 输入：清洗后的三元组 JSON
- 输出：补全后的三元组 JSON
- **核心改进**：
  - 识别孤岛三元组（仅2个实体+1条关系）
  - 基于实体关系图补全合法的间接关联
  - 所有补全关联可追溯到文本来源

#### 步骤 6：Neo4j 导入

```powershell
python -m src.neo4j_import --input triplets_completed.json `
  --uri bolt://localhost:7687 `
  --user neo4j `
  --password $env:NEO4J_PASSWORD
```

- 输入：最终三元组 JSON
- 输出：Neo4j 知识图谱
- 功能：创建节点和关系，支持 MERGE 操作（避免重复）

#### 步骤 7：知识图谱补全（KGC，可选）

```powershell
# 方式一：运行完整示例（推荐）
python kgc_example.py

# 方式二：在代码中使用 KGC 模块
python -c "
from src.kgc_module import KGCModule, load_json_data

# 加载数据
data = load_json_data('triplets_completed.json')

# 初始化 KGC 模块（使用 GCN 增强）
kgc = KGCModule(data, embedding_dim=100, use_gcn=True)

# 训练嵌入模型
kgc.train(epochs=50, batch_size=32, learning_rate=0.01)

# 进行预测
predictions = kgc.predict('园艺主题', '相关于', top_k=10)
print('预测结果:', predictions)

# 生成 LLM 提示
prompt = kgc.generate_llm_prompt('园艺主题', '相关于')
print('LLM 提示:', prompt)
"
```

- 输入：`triplets_completed.json`（包含三元组和实体信息）
- 输出：
  - 训练好的嵌入模型
  - 预测结果（候选实体及得分）
  - 挖掘的逻辑规则
  - LLM 提示文本
- **核心功能**：
  - **嵌入学习**：使用 TransE 模型学习实体和关系的向量表示
  - **GCN 增强**：可选使用图卷积网络增强嵌入（考虑邻居信息）
  - **动态子图**：为每个查询构建相关子图，提供上下文信息
  - **规则挖掘**：自动挖掘关系模式（如：A→R1→B, B→R2→C 可推导出 A→R3→C）
  - **LLM 集成**：生成包含嵌入向量和子图信息的提示，用于 LLM 推理

---

## 🎯 核心改进

### 改进目标

解决 Neo4j 中大量**孤岛三元组**（仅2个实体+1条关系）、节点无法联通的问题。

### 改进策略

#### 1. **实体层归一化** (`src/ner_llm.py`)

**问题**：同一实体的不同表述被识别为不同节点（如"南沙新区"vs"南沙区"）。

**解决方案**：
- 新增 `normalize_entity_names()` 函数：基于文本上下文进行同义合并
- 新增 `_is_same_entity()` 函数：判断两个实体是否指向同一对象
- 新增 `_resolve_reference()` 函数：指代消解（"该区"→"核心区"）
- 输出 `entity_aliases` 字段：记录别名映射

**效果**：同一文本内"同体异名"实体数减少≥80%

#### 2. **关系抽取层扩展** (`src/relation_extraction.py`)

**问题**：仅提取直接显性关系，未挖掘文本内间接关联。

**解决方案**：
- 扩展 `SYSTEM_PROMPT`：新增规则8-10，支持间接关联挖掘
  - **规则8**：允许提取通过上下文隐含的间接关联（如"A的B"→A包含B）
  - **规则9**：支持提取链式关联（A-R1-B、B-R2-C→补充A-R3-C）
  - **规则10**：共现实体的弱关联（谨慎使用，需标注）

**效果**：单文本内三元组的"链式关联数"提升≥50%

#### 3. **关系谓词标准化** (`clean_triplets.py`)

**问题**：语义等价的关系未统一（如"归属于"vs"属于"），导致路径碎片化。

**解决方案**：
- 扩展 `RELATION_MERGE_MAP`：覆盖更多城市规划领域的同义关系
- 合并语义完全相同的关系（强制合并）
- 合并语义相近的关系（可选合并）

**效果**：关系谓词标准化率≥90%

#### 4. **关联补全脚本** (`triplet_link_completion.py`)

**问题**：孤立的三元组无法与其他节点连通。

**解决方案**：
- 构建实体关系图：基于已有三元组构建关联网络
- 识别孤岛三元组：找出只出现一次的实体
- 补全间接关联：通过实体关系图找到合法的间接路径
- 记录来源句子：所有补全关联可追溯到文本

**效果**：孤岛三元组数减少≥40%，连通分量数减少≥60%

### 改进约束

✅ **严格遵守文本边界**：
- 所有实体/关系完全来自输入文本
- 不引入外部知识库（百度百科、词典等）
- 所有新增关联可追溯到文本中的具体句子

✅ **可回滚机制**：
- 保留原始三元组
- 补全三元组与原始三元组分离存储
- 可一键关闭"间接关联挖掘"

---

## 📚 脚本说明

| 脚本 | 作用 | 关键参数/说明 |
|------|------|--------------|
| `src/pdf_processing.py` | PDF/文本切分为句子块 | `--text <txt>` 或 `--input <pdf>`；输出 `processed_texts.json` |
| `src/ner_llm.py` | LLM 驱动实体识别（含归一化） | 环境变量 `OPENAI_API_KEY`；输出 `entities_extracted.json` |
| `src/relation_extraction.py` | LLM 驱动关系抽取（支持间接关联） | 输入 NER 结果；输出 `triplets_final.json` |
| `clean_triplets.py` | 三元组清洗与关系标准化 | `--input` 默认 `triplets_final.json`；输出 `triplets_cleaned.json` |
| `triplet_link_completion.py` | 关联补全（解决孤岛问题） | `--input triplets_cleaned.json`；输出 `triplets_completed.json` |
| `src/pipeline_orchestrator.py` | 端到端管道协调器 | 支持 `--mode demo/llm`，可直接 `--import-neo4j` |
| `src/neo4j_import.py` | Neo4j 导入接口 | `--input`、`--uri`、`--user`、`--password`、`--database` |
| `src/kgc_module.py` | 知识图谱补全模块 | 嵌入学习、GCN 增强、规则挖掘、LLM 提示生成 |
| `src/kgc_incremental_sync.py` | KGC 增量同步模块 | KGC 结果回写、JSON 增量合并、Neo4j 增量同步 |
| `kgc_example.py` | KGC 使用示例 | 演示完整的 KGC 工作流程 |
| `kgc_sync_example.py` | KGC 增量同步示例 | 演示 KGC 结果回写和同步流程 |
| `generate_kgc_predictions.py` | KGC 预测生成工具 | 从 KGC 模块批量生成预测结果 |
| `main.py` | 命令行入口（分阶段运行） | `python main.py <stage>`，stage∈`data/ner/re/import/all` |
| `scripts/show_triplets.py` | 三元组统计与展示 | 分析三元组数量和关系分布 |

---

## 🧠 知识图谱补全（KGC）模块

### 功能概述

KGC 模块提供了完整的知识图谱补全功能，包括嵌入学习、图神经网络增强、规则挖掘和 LLM 集成。

### 核心组件

1. **EmbeddingModule**: 基础嵌入模块，为实体和关系生成向量表示
2. **GCNEnhancedEmbedding**: 使用图卷积网络增强的嵌入模块
3. **TransE**: TransE 模型，用于知识图谱嵌入和补全预测
4. **SubgraphBuilder**: 动态子图构建器，为查询构建相关上下文
5. **RuleMiner**: 逻辑规则挖掘器，从三元组中挖掘关系模式
6. **LLMPromptGenerator**: LLM 提示生成器，生成包含嵌入和子图信息的提示
7. **KGCModule**: 主模块，整合所有功能

### 完整使用步骤

#### 步骤 1：准备数据

确保已有 `triplets_completed.json` 文件（包含三元组和实体信息）：

```powershell
# 如果没有，先运行前面的步骤生成
python clean_triplets.py --input triplets_final.json --output triplets_cleaned.json
python triplet_link_completion.py --input triplets_cleaned.json --output triplets_completed.json
```

#### 步骤 2：运行 KGC 示例

```powershell
# 运行完整示例（包含训练、预测、规则挖掘、LLM 提示生成）
python kgc_example.py
```

**示例输出**：
- 数据加载信息
- 模型初始化信息（实体数、关系数、三元组数）
- 训练过程（损失值变化）
- 预测结果（Top-K 候选实体）
- 挖掘的规则
- 生成的 LLM 提示

#### 步骤 3：在代码中使用 KGC 模块

```python
from src.kgc_module import KGCModule, load_json_data

# 1. 加载数据
data = load_json_data("triplets_completed.json")

# 2. 初始化 KGC 模块
# embedding_dim: 嵌入维度（默认 100）
# use_gcn: 是否使用 GCN 增强（默认 True）
kgc = KGCModule(data, embedding_dim=100, use_gcn=True)

# 3. 训练嵌入模型
# epochs: 训练轮数（默认 50，示例中可用 20 进行快速测试）
# batch_size: 批次大小（默认 32）
# learning_rate: 学习率（默认 0.01）
kgc.train(epochs=50, batch_size=32, learning_rate=0.01)

# 4. 进行知识图谱补全预测
# head: 头实体
# relation: 关系
# top_k: 返回前 K 个结果（默认 10）
# use_subgraph: 是否使用子图信息（默认 True）
# use_rules: 是否使用规则推理（默认 True）
predictions = kgc.predict("园艺主题", "相关于", top_k=10, use_subgraph=True, use_rules=True)
print("预测结果:", predictions)
# 输出: [("农耕文明", 0.85), ("梯田", 0.72), ...]

# 5. 获取挖掘的规则
# min_support: 最小支持度（默认 2）
# top_k: 返回前 K 条规则（默认 20）
rules = kgc.get_mined_rules(min_support=2, top_k=10)
for rule in rules:
    print(f"规则: {rule['premise']} -> {rule['conclusion']} (支持度: {rule['support']})")

# 6. 生成 LLM 提示
# 生成包含子图、候选实体和嵌入信息的提示，可用于 LLM 推理
prompt = kgc.generate_llm_prompt("园艺主题", "相关于", top_k_candidates=20)
print("LLM 提示:", prompt)

# 7. 构建子图（单独使用）
subgraph = kgc.subgraph_builder.get_related_triplets("园艺主题", max_depth=2, max_triplets=10)
print("相关三元组:", subgraph)
```

### 参数说明

#### KGCModule 初始化参数

- `json_data`: JSON 数据列表，每个元素包含 `id`, `text`, `triplets`, `entities`
- `embedding_dim`: 嵌入维度，默认 100（可调整为 50, 128, 256 等）
- `use_gcn`: 是否使用 GCN 增强，默认 `True`（设为 `False` 可加快训练速度）

#### train() 方法参数

- `epochs`: 训练轮数，默认 50（快速测试可用 20）
- `batch_size`: 批次大小，默认 32（根据内存调整）
- `learning_rate`: 学习率，默认 0.01（可尝试 0.001, 0.005 等）

#### predict() 方法参数

- `head`: 头实体（字符串）
- `relation`: 关系（字符串）
- `top_k`: 返回前 K 个结果，默认 10
- `use_subgraph`: 是否使用子图信息，默认 `True`
- `use_rules`: 是否使用规则推理，默认 `True`

### 性能优化建议

1. **快速测试**：使用较小的 `embedding_dim`（如 50）和较少的 `epochs`（如 20）
2. **内存优化**：如果内存不足，减小 `batch_size`（如 16 或 8）
3. **速度优化**：如果不需要 GCN 增强，设置 `use_gcn=False`
4. **精度优化**：增加 `embedding_dim`（如 128 或 256）和 `epochs`（如 100）

### 输出文件

KGC 模块主要输出到控制台，如需保存结果，可以在代码中添加：

```python
# 保存预测结果
import json
predictions = kgc.predict("园艺主题", "相关于", top_k=10)
with open("predictions.json", "w", encoding="utf-8") as f:
    json.dump(predictions, f, ensure_ascii=False, indent=2)

# 保存规则
rules = kgc.get_mined_rules(min_support=2, top_k=20)
with open("mined_rules.json", "w", encoding="utf-8") as f:
    json.dump(rules, f, ensure_ascii=False, indent=2)

# 保存 LLM 提示
prompt = kgc.generate_llm_prompt("园艺主题", "相关于")
with open("llm_prompt.txt", "w", encoding="utf-8") as f:
    f.write(prompt)
```

---

## 🗄️ Neo4j 导入

### 首次导入

```powershell
# 1. 清洗三元组
python clean_triplets.py --input triplets_final.json --output triplets_cleaned.json

# 2. 可选：关联补全
python triplet_link_completion.py --input triplets_cleaned.json --output triplets_completed.json

# 3. 导入 Neo4j（建议使用清洗后的文件）
python -m src.neo4j_import --input triplets_completed.json `
  --uri bolt://localhost:7687 `
  --user neo4j `
  --password $env:NEO4J_PASSWORD
```

### 增量导入

```powershell
# 假设有新数据 triplets_final_v2.json
python clean_triplets.py --input triplets_final_v2.json --output triplets_cleaned_v2.json
python -m src.neo4j_import --input triplets_cleaned_v2.json `
  --uri bolt://localhost:7687 `
  --user neo4j `
  --password $env:NEO4J_PASSWORD `
  --database neo4j
```

**说明**：`neo4j_import.py` 使用 `MERGE` 操作，重复的实体/关系会被自动合并，适合多次导入。

---

## 🔄 KGC 增量同步模块

### 功能概述

KGC 增量同步模块用于将 KGC 推理得到的新增三元组回写到 JSON 数据集，并增量同步到 Neo4j 数据库。

**核心特性**：
- ✅ **增量合并**：将 KGC 预测结果增量合并到 `triplets_completed.json`，不破坏原始数据
- ✅ **严格去重**：自动检测并跳过已存在的三元组
- ✅ **实体维护**：自动更新 `entities` 字段，新增实体标记为 "Inferred"
- ✅ **来源追踪**：所有 KGC 三元组带有 `source="KGC"` 标记和置信度信息
- ✅ **Neo4j 同步**：增量写入 Neo4j，关系带来源和置信度属性
- ✅ **干运行模式**：支持 `dry_run` 模式，仅打印不写入

### 数据格式

#### 输入：KGC 预测结果

支持多种格式：

```json
// 格式1：JSON对象列表（推荐）
[
  {"head": "园艺主题", "relation": "体现", "tail": "农耕智慧", "confidence": 0.87},
  {"head": "中国馆", "relation": "连接", "tail": "妫汭湖", "confidence": 0.82}
]

// 格式2：简单列表
[
  ["园艺主题", "体现", "农耕智慧", 0.87],
  ["中国馆", "连接", "妫汭湖", 0.82]
]
```

#### 输出：增强后的 JSON

新增字段 `kgc_triplets`（原始 `triplets` 字段不变）：

```json
{
  "id": 1,
  "text": "...",
  "triplets": [
    ["园艺主题", "相关于", "农耕文明"]
  ],
  "entities": {
    "Location": ["北京世园会"],
    "Inferred": ["农耕智慧"]  // 新增实体
  },
  "kgc_triplets": [  // 新增字段
    {
      "triple": ["园艺主题", "体现", "农耕智慧"],
      "source": "KGC",
      "confidence": 0.87,
      "timestamp": "2026-01-22"
    }
  ]
}
```

### 使用方法

#### 方式一：命令行使用

```powershell
# 基本用法
python -m src.kgc_incremental_sync `
  --kgc-predictions kgc_predictions.json `
  --input triplets_completed.json `
  --output triplets_completed_augmented.json `
  --neo4j-password $env:NEO4J_PASSWORD

# 干运行模式（仅打印，不写入）
python -m src.kgc_incremental_sync `
  --kgc-predictions kgc_predictions.json `
  --dry-run

# 完整参数
python -m src.kgc_incremental_sync `
  --kgc-predictions kgc_predictions.json `
  --input triplets_completed.json `
  --output triplets_completed_augmented.json `
  --neo4j-uri bolt://localhost:7687 `
  --neo4j-user neo4j `
  --neo4j-password $env:NEO4J_PASSWORD `
  --neo4j-database neo4j `
  --log-file kgc_sync_log.txt
```

#### 方式二：在代码中使用

```python
from src.kgc_incremental_sync import KGCIncrementalSync, load_kgc_predictions

# 1. 加载KGC预测结果
kgc_triplets, confidences = load_kgc_predictions("kgc_predictions.json")

# 2. 创建同步对象
sync = KGCIncrementalSync(
    input_json="triplets_completed.json",
    output_json="triplets_completed_augmented.json",
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password=os.getenv("NEO4J_PASSWORD"),
    dry_run=False  # 实际写入
)

# 3. 执行同步
sync.process(kgc_triplets, confidences)

# 4. 保存日志
sync.save_logs("kgc_sync_log.txt")
```

#### 方式三：从 KGC 模块生成预测并同步

```powershell
# 步骤1：生成KGC预测结果
python generate_kgc_predictions.py `
  --input triplets_completed.json `
  --queries queries.json `
  --output kgc_predictions.json `
  --epochs 50

# 步骤2：增量同步
python -m src.kgc_incremental_sync `
  --kgc-predictions kgc_predictions.json `
  --output triplets_completed_augmented.json `
  --neo4j-password $env:NEO4J_PASSWORD
```

### 完整工作流程

```powershell
# ============================================
# 步骤 1：生成 KGC 预测结果
# ============================================

# 方式A：使用 generate_kgc_predictions.py（推荐）
python generate_kgc_predictions.py `
  --input triplets_completed.json `
  --queries queries.json `
  --output kgc_predictions.json `
  --epochs 50 `
  --top-k 5

# 方式B：在代码中生成
python kgc_sync_example.py --example 2

# ============================================
# 步骤 2：增量同步到 JSON 和 Neo4j
# ============================================

# 干运行（先检查）
python -m src.kgc_incremental_sync `
  --kgc-predictions kgc_predictions.json `
  --dry-run

# 实际执行
python -m src.kgc_incremental_sync `
  --kgc-predictions kgc_predictions.json `
  --output triplets_completed_augmented.json `
  --neo4j-password $env:NEO4J_PASSWORD
```

### Neo4j 写入规则

#### 节点规则

```cypher
MERGE (h:Entity {name: $head})
ON CREATE SET h.type = 'Inferred'
```

- 所有实体统一使用 `Entity` 标签
- 新创建的节点设置 `type = 'Inferred'`
- 使用 `MERGE` 避免重复创建

#### 关系规则

```cypher
MERGE (h:Entity {name: $head})-[r:RELATION_TYPE]->(t:Entity {name: $tail})
ON CREATE SET
  r.source = 'KGC',
  r.confidence = $confidence,
  r.timestamp = $timestamp,
  r.name = $relation
```

- 关系类型自动清洗（符合 Neo4j 规范）
- 所有 KGC 关系带有 `source='KGC'` 属性
- 包含置信度和时间戳信息
- 使用 `MERGE` 避免重复创建

### 验证要求

✅ **数据完整性**：
- 原始 `triplets` 字段完全不变
- 所有 KGC 三元组存储在 `kgc_triplets` 字段
- 新增实体自动添加到 `entities` 字段

✅ **去重保证**：
- 同一三元组不会被写入两次
- 重跑脚本不会导致数据膨胀
- 自动检测并跳过重复项

✅ **来源追踪**：
- 所有 KGC 三元组带有 `source="KGC"` 标记
- Neo4j 关系带有来源、置信度、时间戳属性
- 日志文件记录所有操作

### 统计信息

执行完成后会输出统计信息：

```
处理完成！统计信息：
============================================================
KGC三元组总数: 50
添加到JSON: 45
跳过重复: 5
新增实体: 12
增强的Entry数: 30
Neo4j关系创建: 45
Neo4j关系合并: 0
============================================================
```

### 示例程序

运行示例程序查看完整用法：

```powershell
# 示例1：基本同步流程（干运行）
python kgc_sync_example.py --example 1

# 示例2：从KGC模块生成预测并同步
python kgc_sync_example.py --example 2

# 示例3：完整同步（包含Neo4j）
python kgc_sync_example.py --example 3

# 示例4：从文件加载预测结果
python kgc_sync_example.py --example 4
```

---

## 📤 GitHub 发布

### 首次上传

```powershell
# 1. 初始化 Git（若尚未）
git init
git add .
git commit -m "feat: initialize knowledge graph pipeline with island triplet optimization"

# 2. 关联远程仓库
git remote add origin https://github.com/<your-username>/knowledgeProject.git

# 3. 推送到远程
git branch -M main
git push -u origin main
```

### 更新代码

```powershell
# 1. 查看变更
git status

# 2. 添加变更文件
git add README.md src/ clean_triplets.py triplet_link_completion.py
git commit -m "docs: update README and add island triplet optimization features"

# 3. 推送到远程
git push
```

### 创建新分支（推荐）

```powershell
# 创建功能分支
git checkout -b feature/add-link-completion

# 修改代码...
git add .
git commit -m "feat: add triplet link completion module"

# 推送到远程并创建 Pull Request
git push -u origin feature/add-link-completion
```

---

## ❓ 常见问题

### 1. **LLM API 调用失败**

- **检查 API Key**：确保 `OPENAI_API_KEY` 或 `GRAPHRAG_CHAT_API_KEY` 已设置
- **检查 API Base**：如果使用第三方服务，确保 `GRAPHRAG_API_BASE` 正确
- **检查流控限制**：注意 API 调用频率限制，脚本已实现指数退避重试

### 2. **Neo4j 连接失败**

- **检查 Neo4j 服务**：确保 Neo4j 正在运行（`neo4j start` 或 Docker）
- **检查连接地址**：本地使用 `bolt://localhost:7687`，远程使用 `bolt+ssc://...`
- **检查认证信息**：确保用户名和密码正确

### 3. **spaCy 模型未找到**

```powershell
# 安装中文模型
python -m spacy download zh_core_web_sm

# 或使用其他中文模型
python -m spacy download zh_core_web_trf
```

### 4. **实体归一化效果不佳**

- **检查文本质量**：确保文本中有足够的上下文信息
- **调整归一化规则**：可在 `src/ner_llm.py` 中调整 `_is_same_entity()` 函数的匹配规则
- **查看别名映射**：检查输出的 `entity_aliases` 字段，验证归一化结果

### 5. **孤岛三元组仍然很多**

- **启用关联补全**：运行 `triplet_link_completion.py`
- **检查文本分块**：如果分块过细，可能导致跨片段的关联丢失
- **调整关系抽取 Prompt**：在 `src/relation_extraction.py` 中优化 `SYSTEM_PROMPT`

### 6. **KGC 模块相关问题**

#### PyTorch 安装失败

```powershell
# Windows (CPU 版本)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# Windows (GPU 版本，需要 CUDA)
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 安装 PyTorch Geometric
pip install torch-geometric
```

#### 训练速度慢

- **减少嵌入维度**：将 `embedding_dim` 从 100 降到 50
- **减少训练轮数**：将 `epochs` 从 50 降到 20（快速测试）
- **关闭 GCN**：设置 `use_gcn=False`
- **减小批次大小**：将 `batch_size` 从 32 降到 16

#### 预测结果不准确

- **增加训练轮数**：将 `epochs` 增加到 100 或更多
- **增加嵌入维度**：将 `embedding_dim` 增加到 128 或 256
- **启用 GCN**：设置 `use_gcn=True`（如果之前关闭了）
- **检查数据质量**：确保 `triplets_completed.json` 中的三元组质量良好

#### 内存不足

- **减小批次大小**：将 `batch_size` 从 32 降到 8 或 16
- **减少嵌入维度**：将 `embedding_dim` 从 100 降到 50
- **分批处理**：如果数据量很大，可以分批加载和处理

---

## 📈 预期效果

### 量化指标

- ✅ **孤岛三元组减少**：通过实体归一化和关联补全，预计减少≥40%
- ✅ **图谱连通性提升**：最大连通分量包含的节点数预计提升至≥90%
- ✅ **关系标准化率**：通过扩展的关系合并规则，预计标准化率≥90%
- ✅ **数据完整性保证**：所有新增关联均可在输入文本中找到依据

---

## 🔜 下一步计划

- [x] 知识图谱补全（KGC）模块：嵌入学习、GCN 增强、规则挖掘、LLM 集成
- [x] KGC 增量同步模块：KGC 结果回写、JSON 增量合并、Neo4j 增量同步
- [ ] 引入评估脚本：量化图谱连通性和数据质量
- [ ] 优化性能：进一步优化 spaCy 模型加载和 LLM 调用
- [ ] 扩展测试：补充更多单元测试和集成测试（包括 KGC 模块测试）
- [ ] 可视化增强：结合 Neo4j Bloom 做更丰富的可视化
- [ ] 文档完善：添加更多使用示例和最佳实践
- [ ] KGC 模型持久化：支持保存和加载训练好的嵌入模型
- [ ] 批量预测：支持批量查询和预测

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 🤝 贡献

欢迎通过 Issue 或 Pull Request 贡献改进思路！

---

**最后更新**：2025年1月（新增 KGC 模块）
