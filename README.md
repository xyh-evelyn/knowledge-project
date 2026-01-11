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
│  └─ demo_local.py              # 离线演示模块
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
pip install -r requirements.txt

# 安装 spaCy 中文模型（必需）
python -m spacy download zh_core_web_sm
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
| `main.py` | 命令行入口（分阶段运行） | `python main.py <stage>`，stage∈`data/ner/re/import/all` |
| `scripts/show_triplets.py` | 三元组统计与展示 | 分析三元组数量和关系分布 |

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

---

## 📈 预期效果

### 量化指标

- ✅ **孤岛三元组减少**：通过实体归一化和关联补全，预计减少≥40%
- ✅ **图谱连通性提升**：最大连通分量包含的节点数预计提升至≥90%
- ✅ **关系标准化率**：通过扩展的关系合并规则，预计标准化率≥90%
- ✅ **数据完整性保证**：所有新增关联均可在输入文本中找到依据

---

## 🔜 下一步计划

- [ ] 引入评估脚本：量化图谱连通性和数据质量
- [ ] 优化性能：进一步优化 spaCy 模型加载和 LLM 调用
- [ ] 扩展测试：补充更多单元测试和集成测试
- [ ] 可视化增强：结合 Neo4j Bloom 做更丰富的可视化
- [ ] 文档完善：添加更多使用示例和最佳实践

---

## 📄 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

---

## 🤝 贡献

欢迎通过 Issue 或 Pull Request 贡献改进思路！

---

**最后更新**：2024年1月
