"""PDF 或纯文本 -> 清洗文本 -> 分块（支持 token 估算）

用法示例:
    python -m src.pdf_processing --text input/text1.txt
    python -m src.pdf_processing --input plan.pdf

依赖: pdfplumber, tiktoken (可选)
"""
import argparse
import json
import re
import os
import sys
import pdfplumber
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import tiktoken
except Exception:
    tiktoken = None

from src.config import PROCESSED_TEXTS_PATH, ensure_output_dirs


def extract_text_from_pdf(path):
    """
PDF 或纯文本 -> 清洗文本 -> 分块（支持 token 估算）
核心功能：将PDF或纯文本文件转换为结构化的文本块（JSON格式），便于后续实体抽取和关系抽取
- 处理流程：读取文件 → 提取文本 → 清洗降噪 → 句子分割 → 按token限制分块 → 保存结果

用法示例:
    python src/pdf_processing.py --input plan.pdf --output processed_texts.json  # 处理PDF文件
    python src/pdf_processing.py --text input/text1.txt --output processed_texts.json  # 处理纯文本文件

依赖: pdfplumber (PDF文本提取), tiktoken (可选，用于精确token估算), tqdm (无显式使用，可能为依赖传递)
"""
import argparse  # 解析命令行参数
import json  # 处理JSON格式输出
import re  # 正则表达式，用于文本清洗和分割
import os  # 文件路径处理
import pdfplumber  # 读取PDF文件并提取文本（核心依赖）

# 尝试导入tiktoken（OpenAI的token计算库），若导入失败则设为None（降级使用字符长度估算）
try:
    import tiktoken
except Exception:
    tiktoken = None


def extract_text_from_pdf(path):
    # """
    # 从PDF文件中提取纯文本
    # :param path: PDF文件路径
    # :return: 提取后的完整纯文本（所有页面拼接，页面间用换行分隔）
    # """
    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text() or ""
            pages.append(txt)
    return "\n".join(pages)


def clean_text(text):
    # """
    # 文本清洗：去除无用信息，保留有效内容
    # 清洗规则：空行、纯数字（可能是页码/序号）、页码标识（如"Page 1"）
    # :param text: 原始文本（可能含噪声）
    # :return: 清洗后的干净文本
    # """
    lines = text.splitlines()
    clean_lines = []
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        if re.fullmatch(r'\d{1,4}', s):
            continue
        if re.match(r'page\s*\d+', s, re.I):
            continue
        clean_lines.append(s)
    return '\n'.join(clean_lines)


def split_sentences(text):
    # 句子分割：将清洗后的文本按中文/英文句末标点分割为独立句子
    # 支持的句末标点：中文（。！？）、英文（.!?）
    # :param text: 清洗后的连贯文本
    # :return: 分割后的句子列表（已去除空句子）
    pattern = r'(?<=[。！？!?\.!])\s*'
    parts = re.split(pattern, text)
    parts = [p.strip() for p in parts if p.strip()]
    return parts


def estimate_tokens(s):
    if tiktoken:
        try:
            enc = tiktoken.get_encoding("cl100k_base")
            return len(enc.encode(s))
        except Exception:
            pass
    return max(1, len(s) // 2)


def chunk_sentences(sentences, max_tokens=256):
    chunks = []
    cur = []
    cur_tokens = 0
    for s in sentences:
        t = estimate_tokens(s)
        if cur and cur_tokens + t > max_tokens:
            chunks.append(''.join(cur))
            cur = [s]
            cur_tokens = t
        else:
            cur.append(s)
            cur_tokens += t
    if cur:
        chunks.append(''.join(cur))
    return chunks


def process_text_file(input_path, output_path, max_tokens=256):
    # """
    # 处理纯文本文件的完整流程：读取 → 清洗 → 分割 → 分块 → 保存
    # :param input_path: 纯文本文件路径
    # :param output_path: 输出JSON文件路径
    # :param max_tokens: 每个文本块的最大token数
    # :return: 结构化的文本块列表（与输出JSON内容一致）
    # """
    with open(input_path, 'r', encoding='utf-8') as f:
        raw = f.read()
    cleaned = clean_text(raw)
    sents = split_sentences(cleaned)
    chunks = chunk_sentences(sents, max_tokens=max_tokens)
    out = []
    for i, c in enumerate(chunks, 1):
        out.append({"id": i, "text": c, "source": input_path})
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out


def process_pdf(input_path, output_path, max_tokens=256):
    # """
    # 处理PDF文件的完整流程：提取文本 → 清洗 → 分割 → 分块 → 保存
    # 流程与纯文本处理一致，仅多一步PDF文本提取
    # :param input_path: PDF文件路径
    # :param output_path: 输出JSON文件路径
    # :param max_tokens: 每个文本块的最大token数
    # :return: 结构化的文本块列表（与输出JSON内容一致）
    # """
    raw = extract_text_from_pdf(input_path)
    cleaned = clean_text(raw)
    sents = split_sentences(cleaned)
    chunks = chunk_sentences(sents, max_tokens=max_tokens)
    out = []
    for i, c in enumerate(chunks, 1):
        out.append({"id": i, "text": c, "source": input_path})
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    return out


def main():
    p = argparse.ArgumentParser(description="文本预处理：PDF/纯文本 → JSON 分块")
    p.add_argument('--input', '-i', default=None, help='输入 PDF 文件路径')
    p.add_argument('--text', '-t', default=None, help='输入纯文本文件路径')
    p.add_argument('--output', '-o', default=None, help='输出 JSON 路径（可选，默认自动生成）')
    p.add_argument('--max-tokens', type=int, default=256, help='每个文本块的最大 token 数')
    args = p.parse_args()
    
    # 确保输出目录存在
    ensure_output_dirs()
    
    # 确定输出路径
    output_path = args.output or str(PROCESSED_TEXTS_PATH)
    
    if args.text:
        print(f"📄 处理纯文本文件: {args.text}")
        if not os.path.exists(args.text):
            print(f"❌ 错误：文件不存在 {args.text}")
            sys.exit(1)
        items = process_text_file(args.text, output_path, max_tokens=args.max_tokens)
    elif args.input:
        print(f"📄 处理 PDF 文件: {args.input}")
        if not os.path.exists(args.input):
            print(f"❌ 错误：文件不存在 {args.input}")
            sys.exit(1)
        items = process_pdf(args.input, output_path, max_tokens=args.max_tokens)
    else:
        print("❌ 错误：请提供 --input (PDF) 或 --text (纯文本文件) 参数")
        sys.exit(1)
    
    print(f"✓ 成功处理 {len(items)} 个文本块")
    print(f"✓ 输出文件: {output_path}")


if __name__ == '__main__':
    main()
