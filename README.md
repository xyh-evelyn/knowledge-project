# Knowledge Project — 城市规划知识图谱复现与发布指南

本仓库演示城市规划领域知识图谱从原始文本到 Neo4j 可视化的完整工程，涵盖 PDF/文本预处理、LLM 驱动的命名实体识别（NER）、关系抽取（RE）、三元组清洗（`clean_triplets.py`）以及 Neo4j 导入。README 已整合各脚本的职责、运行顺序、Neo4j 首次/增量导入方式及 GitHub 发布流程，确保团队成员或外部贡献者一键复刻。

---

## 1. 仓库目录 & 脚本说明

```
knowledgeProject/
├─ input/                   # 自备文本或 PDF（示例：input/text1.txt）
├─ run_output/              # 运行产物（建议忽略）
├─ src/                     # 核心模块（可复用）
│  ├─ pdf_processing.py     # 文本/PDF 分块
│  ├─ ner_llm.py(.new)      # LLM 驱动 NER
│  ├─ relation_extraction.py(.new) # LLM 驱动关系抽取
│  ├─ prompt_builder.py     # 统一 prompt 构造
│  ├─ spacy_nlp.py          # 句法特征抽取
│  ├─ pipeline_orchestrator.py # 端到端 orchestrator
│  └─ neo4j_import.py       # Neo4j 接口（可与根目录同名脚本互换）
├─ clean_triplets.py        # 三元组清洗与统计
├─ pdf_processing.py / neo4j_import.py 等 # 根目录便捷入口
├─ main.py                  # 多阶段 CLI（data/ner/re/import/all）
├─ pipeline_orchestrator.py # 根目录版本，含 demo/llm 模式
├─ requirements.txt
├─ README.md
└─ scripts/, archive/, tests/  # 辅助脚本、归档版本与测试
```

> `.new` 后缀脚本用于更轻量的 GraphRAG/OpenAI 适配，可按需切换；根目录与 `src/` 中的脚本保持逻辑一致，方便在不同入口被调用。

---

## 2. 环境准备（Windows PowerShell 示例）

1. **克隆与进入目录**
   ```powershell
   git clone https://github.com/<your-org>/knowledgeProject.git
   cd knowledgeProject
   ```

2. **创建虚拟环境并激活**
   ```powershell
   python -m venv .venv
   & .\.venv\Scripts\Activate.ps1
   ```

3. **安装依赖**
   ```powershell
   pip install -r requirements.txt
   ```

4. **（可选）安装 spaCy 中文模型**
   ```powershell
   python -m spacy download zh_core_web_sm
   ```

5. **设置 LLM / Neo4j 环境变量（示例）**
   ```powershell
   $env:OPENAI_API_KEY="sk-xxxx"
   $env:GRAPHRAG_API_BASE="https://api.siliconflow.cn/v1"
   $env:GRAPHRAG_CHAT_MODEL="Qwen/Qwen3-32B"
   $env:NEO4J_PASSWORD="your_password"
   ```

> Python 3.8+、Neo4j 4.x/5.x（默认 `bolt://localhost:7687`）即可运行；若使用 Aura 或远程数据库，可将 `--uri` 指向 `bolt+ssc://` 地址。

---

## 3. 端到端运行流程（含 `clean_triplets.py`）

### 3.1 单阶段 CLI（`main.py`）

```powershell
# 1) 数据预处理：PDF/纯文本 -> processed_texts.json
python main.py data --text input\text1.txt

# 2) 命名实体识别（需已配置 LLM）
python main.py ner

# 3) 关系抽取
python main.py re

# 4) 清洗三元组（新增步骤）
python clean_triplets.py --input triplets_final.json --output triplets_cleaned.json

# 5) 导入 Neo4j（首次导入推荐使用 triplets_cleaned.json）
python main.py import --neo4j-password $env:NEO4J_PASSWORD
```

### 3.2 一键全流程

```powershell
# 自动串联 data -> ner -> re -> import（默认导入 triplets_final.json）
# 推荐在 import 前手动运行 clean_triplets.py 并将输出替换
python main.py all --text input\text1.txt --neo4j-password $env:NEO4J_PASSWORD
```

### 3.3 Orchestrator（demo / llm）

```powershell
# 离线 demo（无需外部 LLM），可附加 --import-neo4j
python pipeline_orchestrator.py --text input\text1.txt --mode demo

# 真实 LLM 调用
python pipeline_orchestrator.py --text input\text1.txt --mode llm `
  --import-neo4j `
  --neo4j-uri bolt://localhost:7687 `
  --neo4j-user neo4j `
  --neo4j-password $env:NEO4J_PASSWORD

# demo/llm 均会输出：
# processed_texts.json -> entities_extracted.json -> triplets_final.json -> index.json
# 完成后运行：
python clean_triplets.py --input triplets_final.json --output triplets_cleaned.json
```

---

## 4. 核心脚本一览

| 脚本 | 作用 | 关键参数/说明 |
| --- | --- | --- |
| `pdf_processing.py` / `src/pdf_processing.py` | PDF/文本切分为 512 token 左右的句子块；支持滑窗 | `--input <pdf>` 或 `--text <txt>`；输出 `processed_texts.json` |
| `src/ner_llm.py` / `ner_llm_new.py` | 调用 OpenAI/GraphRAG 接口做 NER | 环境变量 `OPENAI_API_KEY` 或 GraphRAG 变量；输出 `entities_extracted.json` |
| `src/relation_extraction.py` / `relation_extraction_new.py` | 构造 prompt 并抽取三元组 | 输入 NER 结果，输出 `triplets_final.json` |
| `clean_triplets.py` | 清洗/归一化三元组，统计删除原因 | `--input` 默认 `triplets_final.json`，输出 `triplets_cleaned.json` |
| `pipeline_orchestrator.py` | 串联分块、NER、RE、索引、Neo4j 导入 | 支持 `--mode demo/llm`，可直接 `--import-neo4j` |
| `neo4j_import.py` / `src/neo4j_import.py` | 将 JSON 三元组写入 Neo4j | `--input triplets_cleaned.json`、`--uri`、`--user`、`--password`、`--database` |
| `main.py` | 在 Windows 上快速按阶段运行 | `python main.py <stage>`，stage∈`data/ner/re/import/all` |
| `demo_local.py` | demo 模式下的伪造 NER/RE 结果 | 便于离线演示 |
| `scripts/*.py` | 生成/检查中间结果 | 例如 `scripts/show_triplets.py` |

---

## 5. Neo4j 导入指令（首次 vs 后续）

### 5.1 首次导入（建议使用清洗后的三元组，确保图谱“干净”）

```powershell
python clean_triplets.py --input triplets_final.json --output triplets_cleaned.json
python neo4j_import.py --input triplets_cleaned.json `
  --uri bolt://localhost:7687 `
  --user neo4j `
  --password $env:NEO4J_PASSWORD
```

> 首次导入会 `MERGE` 节点与关系，不会重复创建；如需指定数据库，附加 `--database neo4j`。

### 5.2 二次或多次导入（新 JSON 增量）

```powershell
# 假设又跑了一次 LLM -> 生成新的 triplets_final_v2.json
python clean_triplets.py --input triplets_final_v2.json --output triplets_cleaned_v2.json
python neo4j_import.py --input triplets_cleaned_v2.json `
  --uri bolt://localhost:7687 `
  --user neo4j `
  --password $env:NEO4J_PASSWORD `
  --database neo4j
```

- `neo4j_import.py` 中的 Cypher 使用 `MERGE`，因此重复的实体/关系会被更新为单条，适合多次导入。
- 如果采用 `pipeline_orchestrator.py --import-neo4j`，可通过 `--triplets-out triplets_cleaned.json` 先行指定清洗结果，再由 Orchestrator 统一导入。

---

## 6. GitHub 发布与更新

### 6.1 首次上传到 GitHub

```powershell
# 1) 初始化 Git（若尚未）
git init
git add .
git commit -m "feat: initialize knowledge graph pipeline"

# 2) 关联远程仓库（示例）
git remote add origin https://github.com/<your-org>/knowledgeProject.git

# 3) 推送
git push -u origin main
```

> 若当前分支非 `main`，请先 `git branch -M main`；第一次推送需提供 GitHub Token/账号权限。

### 6.2 更新代码后再次上传

```powershell
# 1) 查看变更
git status
git add README.md src/... clean_triplets.py
git commit -m "docs: update pipeline readme and add cleaning stage"

# 2) 推送到远程
git push
```

若需提交拉取请求，请在新分支上开发：

```powershell
git checkout -b feature/add-clean-stage
...修改...
git push -u origin feature/add-clean-stage
```

---

## 7. 常见问题 & 建议

- **Neo4j 未运行**：确保 `neo4j start` 或 Docker/Aura 服务可访问；远程 Aura 建议使用 `bolt+ssc://...` 并在命令中指定 `--database neo4j`.
- **LLM 401/429**：检查 API Key、Model 名称与流控限制；GraphRAG 需要 `GRAPHRAG_CHAT_API_KEY/BASE/MODEL`.
- **spaCy 句法模型未安装**：执行 `python -m spacy download zh_core_web_sm`。
- **长文档分块策略**：可调整 `pdf_processing.py` 中的窗口大小或 `scripts/generate_processed_texts.py` 进行批处理。
- **结果复现性**：建议在重要场景下保存 `run_output/<timestamp>`，并在 README 中标注具体配置。

---

## 8. 下一步

- 根据业务需要拓展 `clean_triplets.py` 规则或引入评估脚本；
- 在 `tests/` 中补充更多单元测试，保障预处理与清洗稳定性；
- 结合 Neo4j Bloom 或 Graph Data Science 做更丰富的可视化与计算分析。

如需进一步集成 CI/CD、Docker 化部署或 LLAMAIndex/GraphRAG 方案，可在此 README 基础上扩展章节。欢迎通过 Issue/PR 贡献改进思路！