# Knowledge Project — 城市规划知识图谱复现

这是一个用于演示城市规划领域知识图谱构建的示例工程，包含数据预处理、命名实体识别（NER）、关系抽取（RE）及 Neo4j 导入的完整管道。

主要特性：
- 支持从纯文本或 PDF 提取并分块（约 512 tokens）
- LLM 驱动的 NER / RE（支持 GraphRag / OpenAI 风格 API）
- 本地 `demo` 模式用于离线演示
- 将三元组导入 Neo4j 进行可视化

目录结构（重构后）：

```
knowledgeProject/
  ├─ src/                      # 核心模块
  ├─ main.py                   # CLI 入口（保留在根目录）
  ├─ input/                    # 输入文本文件
  ├─ run_output/               # 运行产物（不纳入仓库）
  ├─ archive/                  # 归档的旧脚本
  ├─ requirements.txt
  └─ README.md
```

快速开始（Windows, PowerShell）：

1. 克隆仓库

```powershell
git clone https://github.com/xyh-evelyn/knowledge-project.git
cd knowledge-project
```

2. 创建并激活虚拟环境

```powershell
python -m venv .venv
& .\.venv\Scripts\Activate.ps1
```

3. 安装依赖

```powershell
pip install -r requirements.txt
```

4. （可选）下载 spaCy 中文模型

```powershell
python -m spacy download zh_core_web_sm
```

5. 把输入文本放入 `input/`，例如 `input/text1.txt`。

6. 运行完整管道（需要 Neo4j 密码与 LLM key）

```powershell
# 设置环境变量（示例：GraphRag）
$env:GRAPHRAG_API_BASE='https://api.siliconflow.cn/v1'
$env:GRAPHRAG_CHAT_API_KEY='your_chat_api_key'
$env:GRAPHRAG_CHAT_MODEL='Qwen/Qwen3-32B'

python main.py all --text input\text1.txt --neo4j-password "<your_neo4j_password>"
```

7. 离线演示模式（不依赖外部 LLM，也不必提供 Neo4j 密码）

```powershell
python main.py data --text input\text1.txt
python main.py ner   # if you want to run ner with configured LLM
# or use pipeline_orchestrator.py demo mode
python src\pipeline_orchestrator.py --text input\text1.txt --mode demo --import-neo4j --neo4j-uri bolt+ssc://... --neo4j-user neo4j --neo4j-password <pwd>
```

常见问题：
- 如果 Neo4j 本地未启动，请提供远程 Aura bolt+ssc URI 或启动本地 neo4j 服务（默认 bolt://localhost:7687）。
- 若 LLM 报 401/认证错误，请确认 API key 与 `GRAPHRAG_API_BASE`/`GRAPHRAG_CHAT_MODEL` 匹配。

许可证：请根据需要添加 LICENSE 文件。
# 城市规划知识图谱复现步骤

先决条件:

- Python 3.8+
- Neo4j 本地运行 (bolt://localhost:7687)
- 设置 `OPENAI_API_KEY` 环境变量

安装依赖 (PowerShell):

```powershell
python -m pip install -r requirements.txt
```

示例流程:

1. 数据准备（从 PDF 提取并分块）

```powershell
python pdf_processing.py --input plan.pdf --output processed_texts.json
```

2. 实体抽取（NER）

```powershell
$env:OPENAI_API_KEY = "你的_api_key"
python ner_llm.py --input processed_texts.json --output entities_extracted.json
```

3. 关系抽取（RE）

```powershell
python relation_extraction.py --input entities_extracted.json --output triplets_final.json
```

4. 导入 Neo4j

```powershell
python neo4j_import.py --input triplets_final.json --password your_password
```

工具说明:

- `pdf_processing.py`：使用 `pdfplumber` 读取 PDF，清洗并按句子滑动窗口分块。
- `ner_llm.py`：调用 OpenAI 兼容 API（使用 `OPENAI_API_KEY`）做 few-shot NER，输出 JSON。
- `relation_extraction.py`：根据实体判断三元组（S-P-O），输出 JSON。
- `neo4j_import.py`：使用 `neo4j` 驱动把三元组写入 Neo4j，节点标签为 `Entity`。

说明与建议:

- 若使用其他 LLM（例如 Qwen），请调整 `ner_llm.py` 与 `relation_extraction.py` 中的 API 调用。
- 对关键结果建议人工抽样校验以提高准确率。
