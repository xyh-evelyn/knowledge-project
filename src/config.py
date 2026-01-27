"""
统一配置管理模块
所有路径、环境变量在此集中管理，确保项目配置的一致性和可维护性
"""
import os
import json
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# ========== 基础路径配置 ==========
PROJECT_ROOT = Path(__file__).parent
INPUT_DIR = PROJECT_ROOT / "input"
OUTPUT_DIR = PROJECT_ROOT / os.getenv("OUTPUT_DIR", "output")

# ========== 输出子目录 ==========
OUTPUT_PDF_DIR = OUTPUT_DIR / "output_pdf"
OUTPUT_ENTITIES_DIR = OUTPUT_DIR / "output_entities"
OUTPUT_TRIPLETS_DIR = OUTPUT_DIR / "output_triplets"
OUTPUT_TRIPLETS_CLEANED_DIR = OUTPUT_DIR / "output_tripletscleaned"
OUTPUT_TRIPLETS_COMPLETED_DIR = OUTPUT_DIR / "output_tripletscompleted"
OUTPUT_KGC_DIR = OUTPUT_DIR / "output_kgc"

# ========== 输出文件路径 ==========
PROCESSED_TEXTS_PATH = OUTPUT_PDF_DIR / "processed_texts.json"
ENTITIES_EXTRACTED_PATH = OUTPUT_ENTITIES_DIR / "entities_extracted.json"
TRIPLETS_FINAL_PATH = OUTPUT_TRIPLETS_DIR / "triplets_final.json"
TRIPLETS_CLEANED_PATH = OUTPUT_TRIPLETS_CLEANED_DIR / "triplets_cleaned.json"
RELATION_MERGE_MAP_PATH = OUTPUT_TRIPLETS_CLEANED_DIR / "relation_merge_map.json"
TRIPLETS_COMPLETED_PATH = OUTPUT_TRIPLETS_COMPLETED_DIR / "triplets_completed.json"
KGC_PREDICTIONS_PATH = OUTPUT_KGC_DIR / "kgc_predictions.json"
TRIPLETS_COMPLETED_AUGMENTED_PATH = OUTPUT_KGC_DIR / "triplets_completed_augmented.json"

# ========== LLM 配置 ==========
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GRAPHRAG_API_BASE = os.getenv("GRAPHRAG_API_BASE")
GRAPHRAG_CHAT_MODEL = os.getenv("GRAPHRAG_CHAT_MODEL", "gpt-4o")

# ========== Neo4j 配置 ==========
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# ========== 验证必需配置 ==========
def validate_config():
    """验证关键配置是否设置"""
    if not OPENAI_API_KEY:
        raise ValueError(
            "❌ 错误：OPENAI_API_KEY 未设置。\n"
            "请在 .env 文件中设置：OPENAI_API_KEY=your-key\n"
            "或运行：export OPENAI_API_KEY='your-key'"
        )

def ensure_output_dirs():
    """确保所有输出目录存在"""
    for dir_path in [
        OUTPUT_PDF_DIR,
        OUTPUT_ENTITIES_DIR,
        OUTPUT_TRIPLETS_DIR,
        OUTPUT_TRIPLETS_CLEANED_DIR,
        OUTPUT_TRIPLETS_COMPLETED_DIR,
        OUTPUT_KGC_DIR,
    ]:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"✓ 输出目录: {dir_path}")

# ========== 工具函数 ==========
def load_json(path: Path) -> list:
    """安全加载 JSON 文件"""
    if not path.exists():
        raise FileNotFoundError(f"❌ 输入文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(data: list, path: Path, pretty=True) -> None:
    """安全保存 JSON 文件"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        if pretty:
            json.dump(data, f, ensure_ascii=False, indent=2)
        else:
            json.dump(data, f, ensure_ascii=False)
    print(f"✓ 保存文件: {path}")

def print_config():
    """打印当前配置（用于调试）"""
    print("\n" + "="*60)
    print("📋 项目配置信息")
    print("="*60)
    print(f"PROJECT_ROOT:              {PROJECT_ROOT}")
    print(f"OUTPUT_DIR:                {OUTPUT_DIR}")
    print(f"PROCESSED_TEXTS_PATH:      {PROCESSED_TEXTS_PATH}")
    print(f"ENTITIES_EXTRACTED_PATH:   {ENTITIES_EXTRACTED_PATH}")
    print(f"TRIPLETS_FINAL_PATH:       {TRIPLETS_FINAL_PATH}")
    print(f"TRIPLETS_CLEANED_PATH:     {TRIPLETS_CLEANED_PATH}")
    print(f"TRIPLETS_COMPLETED_PATH:   {TRIPLETS_COMPLETED_PATH}")
    print(f"KGC_PREDICTIONS_PATH:      {KGC_PREDICTIONS_PATH}")
    print(f"LLM_MODEL:                 {GRAPHRAG_CHAT_MODEL}")
    print(f"NEO4J_URI:                 {NEO4J_URI}")
    print("="*60 + "\n")

if __name__ == "__main__":
    print_config()
    ensure_output_dirs()
