# 城市规划知识图谱构建系统

一个从原始文本/PDF 到知识图谱的完整端到端系统。通过 LLM 驱动的实体识别、关系抽取、三元组清洗和补全，构建高质量的知识图谱，并支持 Neo4j 可视化和知识图谱补全 (KGC)。

## 📋 核心特性

### 1. **端到端知识图谱构建**
- ✅ PDF/文本自动分块处理
- ✅ LLM 驱动的实体识别 (NER) - 含实体归一化
- ✅ LLM 驱动的关系抽取 (RE) - 含间接关联挖掘
- ✅ 三元组清洗与标准化
- ✅ 孤岛三元组补全（提升连通性）
- ✅ Neo4j 知识图谱可视化
- ✅ 知识图谱补全 (KGC) - 嵌入学习 + 预测推理

### 2. **系统设计**
- ✅ 统一的 .env 配置管理
- ✅ 清晰的数据流向 (output 目录结构)
- ✅ 模块化的 pipeline 设计
- ✅ 详细的日志输出和错误处理

---

## 📁 项目结构

```
knowledgeProject/
├─ .env                         # 配置文件（本地）
├─ .env.example                 # 配置示例
├─ requirements.txt             # Python 依赖
├─ main.py                      # 命令行入口
├─ README.md                    # 本文档
│
├─ src/                         # 核心模块
│  ├─ config.py                # 统一配置管理
│  ├─ pdf_processing.py        # 文本/PDF 分块
│  ├─ ner_llm.py               # 实体识别 (NER)
│  ├─ relation_extraction.py   # 关系抽取 (RE)
│  ├─ neo4j_import.py          # Neo4j 导入
│  ├─ kgc_module.py            # 知识图谱补全 (KGC)
│  ├─ kgc_incremental_sync.py  # KGC 增量同步
│  └─ ... (其他模块)
│
├─ input/                       # 输入文件目录
│  └─ text1.txt                # 示例输入文本
│
├─ output/                      # 输出目录（自动创建）
│  ├─ output_pdf/              # 第1阶段输出
│  │  └─ processed_texts.json
│  ├─ output_entities/         # 第2阶段输出
│  │  └─ entities_extracted.json
│  ├─ output_triplets/         # 第3阶段输出
│  │  └─ triplets_final.json
│  ├─ output_tripletscleaned/  # 第4阶段输出
│  │  ├─ triplets_cleaned.json
│  │  └─ relation_merge_map.json
│  ├─ output_tripletscompleted/# 第5阶段输出
│  │  └─ triplets_completed.json
│  └─ output_kgc/              # 第6阶段输出
│     └─ kgc_predictions.json
│
├─ tests/                       # 单元测试
│  └─ ...
│
└─ scripts/                     # 辅助脚本
   └─ ...
```

---

## 🔧 快速开始

### 1. 克隆项目

```bash
git clone <repository-url>
cd knowledgeProject
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux/Mac
python -m venv .venv
source .venv/bin/activate
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
python -m spacy download zh_core_web_sm
```

### 4. 配置环境变量

复制 `.env.example` 为 `.env` 并修改：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填写必要的 API 密钥：

```ini
# ========== LLM API 配置 ==========
OPENAI_API_KEY=your-api-key-here

# 第三方 LLM API（可选）
GRAPHRAG_API_BASE=https://api.siliconflow.cn/v1
GRAPHRAG_CHAT_MODEL=gpt-4o

# ========== Neo4j 配置（可选） ==========
NEO4J_URI=bolt://localhost:7687
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password-here

# ========== 项目配置 ==========
OUTPUT_DIR=output
```

**配置说明：**
- `OPENAI_API_KEY`: **必需**。从 OpenAI 获取（https://platform.openai.com/api-keys）
- `GRAPHRAG_API_BASE`: 可选。使用第三方兼容 API（如硅基流动等）
- `NEO4J_*`: 可选。仅在需要导入 Neo4j 时填写
- `.env` 文件自动加载，**不要提交到 Git**

---

## 🚀 运行流程

### **方法 1：完整运行（推荐新用户）**

```bash
python main.py all --text input/text1.txt
```

这会自动执行以下阶段：
1. 文本预处理 → `output/output_pdf/processed_texts.json`
2. 实体识别 → `output/output_entities/entities_extracted.json`
3. 关系抽取 → `output/output_triplets/triplets_final.json`
4. 三元组清洗 → `output/output_tripletscleaned/triplets_cleaned.json`
5. 关联补全 → `output/output_tripletscompleted/triplets_completed.json`

**输出结果：** `output/output_tripletscompleted/triplets_completed.json`

---

### **方法 2：分阶段运行（调试/修改时使用）**

如果需要调整某个阶段的参数或中间结果，可以分开运行：

#### 阶段 1：文本预处理

```bash
python main.py data --text input/text1.txt
```

**输入：** `input/text1.txt` (纯文本文件) 或 PDF 文件  
**输出：** `output/output_pdf/processed_texts.json`  
**功能：** 文本清洗、句子分割、按 token 分块

---

#### 阶段 2：实体识别 (NER)

```bash
python main.py ner
```

**输入：** `output/output_pdf/processed_texts.json`  
**输出：** `output/output_entities/entities_extracted.json`  
**功能：** LLM 驱动的实体抽取、去重、归一化

**参数：** （可选）`--model gpt-3.5-turbo` 指定模型

---

#### 阶段 3：关系抽取 (RE)

```bash
python main.py re
```

**输入：** `output/output_entities/entities_extracted.json`  
**输出：** `output/output_triplets/triplets_final.json`  
**功能：** LLM 驱动的三元组抽取、间接关联挖掘

**参数：** （可选）`--model gpt-4o` 指定模型

---

#### 阶段 4：三元组清洗

```bash
python main.py clean
```

**输入：** `output/output_triplets/triplets_final.json`  
**输出：** 
- `output/output_tripletscleaned/triplets_cleaned.json`
- `output/output_tripletscleaned/relation_merge_map.json` (关系合并对照表)

**功能：** 去重、去噪、关系标准化

**参数：** （可选）手动指定输入输出路径

```bash
python clean_triplets.py --input custom_input.json --output custom_output.json
```

---

#### 阶段 5：关联补全（可选，解决孤岛问题）

```bash
python main.py complete
```

**输入：** `output/output_tripletscleaned/triplets_cleaned.json`  
**输出：** `output/output_tripletscompleted/triplets_completed.json`  
**功能：** 基于文本内的实体关系网络，补全合法的间接关联

**效果：** 孤岛三元组数减少 ≥40%，图谱连通性提升 ≥50%

---

#### 阶段 6：知识图谱补全 (KGC)（可选）

```bash
python main.py kgc --queries queries.json
```

**输入：** 
- `output/output_tripletscompleted/triplets_completed.json`
- `queries.json` (查询文件，格式见下方示例)

**输出：** `output/output_kgc/kgc_predictions.json`

**参数：**
- `--epochs 50` : 训练轮数（默认 50）
- `--embedding-dim 100` : 嵌入维度（默认 100）
- `--use-gcn` : 是否使用 GCN 增强（可选）

**功能：** 嵌入学习 + 关系预测 + 规则挖掘

**查询文件格式示例 (`queries.json`)：**

```json
[
  ["园艺主题", "相关于"],
  ["中国馆", "位于"],
  ["北京世园会", "包含"]
]
```

或使用完整格式：

```json
[
  {"head": "园艺主题", "relation": "相关于"},
  {"head": "中国馆", "relation": "位于"}
]
```

---

#### 阶段 7：Neo4j 导入（可选）

```bash
python main.py import
```

**输入：** `output/output_tripletscompleted/triplets_completed.json`  
**输出：** Neo4j 数据库中的图谱  
**前置条件：** Neo4j 服务正在运行，且配置了 `NEO4J_URI`、`NEO4J_PASSWORD` 等

---

### **方法 3：查看配置**

```bash
python main.py config
```

显示当前的所有配置信息和输出路径。

---

## 📊 输出格式说明

### 1. **processed_texts.json** (第1阶段输出)

```json
[
  {
    "id": 1,
    "text": "在南沙区的城市更新规划中，将核心区的工业用地改造为...",
    "source": "input/text1.txt"
  },
  ...
]
```

---

### 2. **entities_extracted.json** (第2阶段输出)

```json
[
  {
    "id": 1,
    "text": "在南沙区的城市更新规划中...",
    "entities": {
      "Location": ["南沙区", "核心区"],
      "Land use function": ["工业用地", "商业办公"],
      "Concept": ["城市更新", "海绵城市"],
      "Planned activity": ["改造", "推广"]
    },
    "entity_aliases": {
      "南沙新区": "南沙区",
      "该片区": "核心区"
    }
  },
  ...
]
```

---

### 3. **triplets_final.json** (第3阶段输出)

```json
[
  {
    "id": 1,
    "text": "在南沙区的城市更新规划中...",
    "triplets": [
      ["南沙区", "包含", "核心区"],
      ["核心区", "用作", "工业用地"],
      ["工业用地", "改造为", "商业办公"]
    ]
  },
  ...
]
```

---

### 4. **triplets_cleaned.json** (第4阶段输出)

```json
[
  {
    "id": 1,
    "text": "...",
    "triplets": [
      ["南沙区", "包含", "核心区"],
      ["核心区", "属于", "工业用地"],  # 关系已标准化
      ["工业用地", "改造", "商业办公"]
    ]
  },
  ...
]
```

**relation_merge_map.json**（关系合并对照表）:

```json
{
  "包含": {
    "merge_count": 10,
    "original_relations": {
      "包含": 8,
      "囊括": 2
    }
  },
  "属于": {
    "merge_count": 15,
    "original_relations": {
      "属于": 10,
      "归属于": 5
    }
  }
}
```

---

### 5. **triplets_completed.json** (第5阶段输出)

```json
[
  {
    "id": 1,
    "text": "...",
    "triplets": [
      ["南沙区", "包含", "核心区"],
      ["核心区", "属于", "工业用地"],
      ["工业用地", "改造", "商业办公"],
      # 新增补全的三元组（所有关联可追溯到文本）
      ["南沙区", "属于", "广东省"],
      ["核心区", "改造", "商业办公"]
    ],
    "_metadata": {
      "island_count": 2,
      "completion_count": 2
    }
  }
]
```

---

### 6. **kgc_predictions.json** (第6阶段输出)

```json
[
  {
    "head": "园艺主题",
    "relation": "相关于",
    "tail": "农耕文明",
    "confidence": 0.87,
    "rank": 1
  },
  {
    "head": "园艺主题",
    "relation": "相关于",
    "tail": "农耕智慧",
    "confidence": 0.72,
    "rank": 2
  },
  ...
]
```

---

## 🔐 环境变量详解

### 必需配置

| 变量 | 说明 | 示例 |
|------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-proj-...` |

### 可选配置

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `GRAPHRAG_API_BASE` | 第三方 LLM API 地址 | `https://api.openai.com/v1` |
| `GRAPHRAG_CHAT_MODEL` | 使用的模型 | `gpt-4o` |
| `NEO4J_URI` | Neo4j 连接地址 | `bolt://localhost:7687` |
| `NEO4J_USERNAME` | Neo4j 用户名 | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j 密码 | (无) |
| `OUTPUT_DIR` | 输出目录 | `output` |

### 获取 API 密钥

**OpenAI（官方）：**
- 注册账号: https://platform.openai.com
- 创建 API 密钥: https://platform.openai.com/api-keys
- 需要绑定信用卡并充值

**第三方兼容 API（推荐中国用户）：**
- 硅基流动: https://cloud.siliconflow.cn
- 阿里云灵积: https://dashscope.aliyun.com
- 使用方式：设置 `GRAPHRAG_API_BASE` 和 API 密钥

---

## 📝 示例流程

### 完整示例：从输入文本到知识图谱

```bash
# 1. 克隆项目
git clone <repo-url>
cd knowledgeProject

# 2. 创建虚拟环境
python -m venv .venv
.\.venv\Scripts\Activate.ps1  # Windows

# 3. 安装依赖
pip install -r requirements.txt
python -m spacy download zh_core_web_sm

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env，填写 OPENAI_API_KEY

# 5. 运行完整 pipeline
python main.py all --text input/text1.txt

# 6. 查看结果
type output\output_tripletscompleted\triplets_completed.json

# 7. （可选）进行 KGC 预测
python main.py kgc --queries queries.json

# 8. （可选）导入 Neo4j（需要 Neo4j 正在运行）
python main.py import
```

---

## 🐛 常见问题

### Q1: 提示 `OPENAI_API_KEY` 未设置

**解决方案：**
1. 确保 `.env` 文件存在且在项目根目录
2. 在 `.env` 中填写有效的 API 密钥
3. 如果使用第三方 API，同时设置 `GRAPHRAG_API_BASE`

```bash
# 检查 .env 文件
type .env

# 测试配置
python main.py config
```

### Q2: LLM API 调用超时

**解决方案：**
- 检查网络连接
- 如果使用官方 OpenAI，可能需要等待（有速率限制）
- 考虑使用第三方兼容 API（如硅基流动）
- 脚本会自动重试 5 次（指数退避）

### Q3: spaCy 模型未找到

**解决方案：**
```bash
python -m spacy download zh_core_web_sm
```

### Q4: 输出文件找不到

**解决方案：**
- 检查是否运行了前面的阶段
- 查看 `output` 目录结构
- 运行 `python main.py config` 查看配置路径

```bash
# 检查输出目录
ls -la output/
```

### Q5: Neo4j 连接失败

**解决方案：**
1. 确保 Neo4j 服务正在运行
2. 检查 `.env` 中的 `NEO4J_URI` 和 `NEO4J_PASSWORD`
3. 默认本地地址是 `bolt://localhost:7687`

```bash
# 测试 Neo4j 连接
python -c "from neo4j import GraphDatabase; driver = GraphDatabase.driver('bolt://localhost:7687', auth=('neo4j', 'password')); print('✓ 连接成功')"
```

### Q6: 内存不足（KGC 训练时）

**解决方案：**
- 减少 embedding 维度：`--embedding-dim 50`
- 减少训练轮数：`--epochs 20`
- 关闭 GCN 增强：移除 `--use-gcn` 参数
- 减小批次大小：脚本中修改 `batch_size` 参数

---

## 📚 技术架构

### 数据流向

```
输入文本
    ↓
[1] 文本分块 (pdf_processing.py)
    ↓
[2] 实体识别 + 归一化 (ner_llm.py)
    ↓
[3] 关系抽取 + 间接关联 (relation_extraction.py)
    ↓
[4] 三元组清洗 + 标准化 (clean_triplets.py)
    ↓
[5] 关联补全 (triplet_link_completion.py)
    ↓
[6] KGC 预测（可选）(generate_kgc_predictions.py)
    ↓
[7] Neo4j 导入（可选）(neo4j_import.py)
    ↓
知识图谱可视化
```

### 核心模块

| 模块 | 功能 | 输入 | 输出 |
|------|------|------|------|
| `pdf_processing.py` | 文本分块 | 原始文本/PDF | JSON 分块 |
| `ner_llm.py` | 实体识别 | 文本块 | 实体列表 |
| `relation_extraction.py` | 关系抽取 | 实体 + 文本 | 三元组 |
| `clean_triplets.py` | 三元组清洗 | 原始三元组 | 清洗后三元组 |
| `triplet_link_completion.py` | 孤岛补全 | 清洗后三元组 | 补全后三元组 |
| `generate_kgc_predictions.py` | KGC 预测 | 三元组 + 查询 | 预测结果 |
| `neo4j_import.py` | Neo4j 导入 | 三元组 | 图数据库 |

---

## 📈 性能指标

### 预期效果

- ✅ **孤岛三元组减少**：通过关联补全，预计减少 ≥40%
- ✅ **连通性提升**：最大连通分量节点数预计提升至 ≥90%
- ✅ **关系标准化率**：通过关系合并，预计达到 ≥90%
- ✅ **数据完整性**：所有新增关联可在原文中找到依据

### 处理速度

- 文本分块：～100KB/s（取决于系统和 token 估算）
- 实体识别：～10-30 个文本块/分钟（取决于 LLM 速率）
- 关系抽取：～10-30 个文本块/分钟（取决于 LLM 速率）
- 三元组清洗：～10,000 个三元组/秒

---

## 📦 依赖清单

| 包 | 版本 | 用途 |
|----|------|------|
| python-dotenv | ≥1.0.0 | 环境变量管理 |
| openai | ≥1.0.0 | LLM API |
| spacy | ≥3.4.0 | 句法分析 |
| neo4j | ≥5.0.0 | 图数据库 |
| torch | ≥2.0.0 | KGC 模块（可选） |
| torch-geometric | ≥2.3.0 | GCN（可选） |

---

## 🔜 后续开发计划

- [ ] 添加更多 LLM 模型支持（Claude、LLaMA 等）
- [ ] 优化 NLP 管道（引入更多中文 NLP 工具）
- [ ] 支持批量查询和并行处理
- [ ] 增加模型评估和性能测试工具
- [ ] 扩展 Neo4j 可视化功能
- [ ] 支持 Knowledge Graph Completion (KGC) 模型持久化

---

## 📄 许可证

本项目采用 **MIT 许可证**。详见 [LICENSE](LICENSE) 文件。

---

## 🤝 贡献

欢迎通过 Issue 或 Pull Request 贡献改进思路！

---

**最后更新**：2026 年 1 月  
**版本**：2.0（系统重构版）

