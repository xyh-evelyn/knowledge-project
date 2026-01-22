# KGC 增量同步模块使用指南

## 📋 概述

KGC 增量同步模块用于将 KGC（知识图谱补全）推理得到的新增三元组回写到 JSON 数据集，并增量同步到 Neo4j 数据库。

## 🚀 快速开始

### 完整流程（3步）

```powershell
# 步骤1：生成KGC预测结果
python generate_kgc_predictions.py `
  --input triplets_completed.json `
  --queries queries_example.json `
  --output kgc_predictions.json `
  --epochs 50

# 步骤2：干运行检查（推荐）
python -m src.kgc_incremental_sync `
  --kgc-predictions kgc_predictions.json `
  --dry-run

# 步骤3：实际执行
python -m src.kgc_incremental_sync `
  --kgc-predictions kgc_predictions.json `
  --output triplets_completed_augmented.json `
  --neo4j-password $env:NEO4J_PASSWORD
```

## 📝 输入格式

### KGC 预测结果文件格式

支持三种格式：

#### 格式1：JSON对象列表（推荐）

```json
[
  {
    "head": "园艺主题",
    "relation": "体现",
    "tail": "农耕智慧",
    "confidence": 0.87
  },
  {
    "head": "中国馆",
    "relation": "连接",
    "tail": "妫汭湖",
    "confidence": 0.82
  }
]
```

#### 格式2：简单列表

```json
[
  ["园艺主题", "体现", "农耕智慧", 0.87],
  ["中国馆", "连接", "妫汭湖", 0.82]
]
```

#### 格式3：元组格式（Python代码）

```python
kgc_triplets = [
    ("园艺主题", "体现", "农耕智慧"),
    ("中国馆", "连接", "妫汭湖")
]
confidences = [0.87, 0.82]
```

## 📤 输出格式

### 增强后的 JSON 文件

原始字段保持不变，新增 `kgc_triplets` 字段：

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

## 🔧 命令行参数

### kgc_incremental_sync.py

```powershell
python -m src.kgc_incremental_sync [参数]

必需参数：
  --kgc-predictions, -k     KGC预测结果文件路径

可选参数：
  --input, -i               输入JSON文件（默认: triplets_completed.json）
  --output, -o              输出JSON文件（默认: triplets_completed_augmented.json）
  --neo4j-uri               Neo4j连接地址（默认: bolt://localhost:7687）
  --neo4j-user              Neo4j用户名（默认: neo4j）
  --neo4j-password          Neo4j密码（从环境变量读取或命令行提供）
  --neo4j-database          Neo4j数据库名称（可选）
  --dry-run                 干运行模式（仅打印，不写入）
  --log-file                日志文件路径（默认: kgc_sync_log.txt）
```

### generate_kgc_predictions.py

```powershell
python generate_kgc_predictions.py [参数]

必需参数：
  --queries, -q             查询文件路径

可选参数：
  --input, -i               输入JSON文件（默认: triplets_completed.json）
  --output, -o              输出预测结果文件（默认: kgc_predictions.json）
  --embedding-dim           嵌入维度（默认: 100）
  --use-gcn                 使用GCN增强
  --epochs                   训练轮数（默认: 50）
  --batch-size               批次大小（默认: 32）
  --learning-rate            学习率（默认: 0.01）
  --top-k                    每个查询返回前K个结果（默认: 5）
  --min-confidence           最小置信度阈值（默认: 0.5）
  --skip-training            跳过训练（如果模型已训练）
```

## 💻 代码示例

### 示例1：基本使用

```python
from src.kgc_incremental_sync import KGCIncrementalSync, load_kgc_predictions

# 加载预测结果
kgc_triplets, confidences = load_kgc_predictions("kgc_predictions.json")

# 创建同步对象
sync = KGCIncrementalSync(
    input_json="triplets_completed.json",
    output_json="triplets_completed_augmented.json",
    neo4j_password=os.getenv("NEO4J_PASSWORD"),
    dry_run=False
)

# 执行同步
sync.process(kgc_triplets, confidences)

# 保存日志
sync.save_logs("kgc_sync_log.txt")
```

### 示例2：手动指定三元组

```python
from src.kgc_incremental_sync import KGCIncrementalSync

# 手动定义三元组
kgc_triplets = [
    ("园艺主题", "体现", "农耕智慧"),
    ("中国馆", "连接", "妫汭湖"),
]
confidences = [0.87, 0.82]

# 执行同步
sync = KGCIncrementalSync(dry_run=True)
sync.process(kgc_triplets, confidences)
```

## 🔍 验证和检查

### 检查统计信息

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

### 验证数据完整性

1. **检查原始数据**：确认 `triplets` 字段未改变
2. **检查新增数据**：确认 `kgc_triplets` 字段存在
3. **检查实体**：确认新增实体在 `entities` 中
4. **检查Neo4j**：查询 `MATCH ()-[r]->() WHERE r.source='KGC' RETURN count(r)`

### 验证去重

```powershell
# 重跑脚本，应该显示"跳过重复"数量增加
python -m src.kgc_incremental_sync `
  --kgc-predictions kgc_predictions.json `
  --dry-run
```

## 🐛 常见问题

### 1. Neo4j 连接失败

```powershell
# 检查Neo4j服务是否运行
# 检查连接信息
$env:NEO4J_URI="bolt://localhost:7687"
$env:NEO4J_PASSWORD="your-password"
```

### 2. 预测结果格式错误

确保预测结果文件是有效的JSON格式，且包含 `head`, `relation`, `tail` 字段。

### 3. 内存不足

如果数据量很大，可以：
- 减小 `batch_size`
- 分批处理预测结果
- 使用 `dry_run` 模式先检查

### 4. 重复写入

模块自动去重，但确保：
- 使用相同的输入文件
- 不要手动修改 `kgc_triplets` 字段
- 重跑时使用相同的预测结果文件

## 📊 最佳实践

1. **先干运行**：使用 `--dry-run` 检查结果
2. **备份数据**：执行前备份 `triplets_completed.json`
3. **分批处理**：如果预测结果很多，分批处理
4. **检查日志**：查看日志文件了解详细过程
5. **验证结果**：执行后检查统计信息和输出文件

## 🔗 相关文件

- `src/kgc_incremental_sync.py` - 核心同步模块
- `kgc_sync_example.py` - 示例程序
- `generate_kgc_predictions.py` - 预测生成工具
- `queries_example.json` - 查询文件示例

## 📚 更多信息

详细文档请参考主 README.md 文件中的 "KGC 增量同步模块" 章节。
