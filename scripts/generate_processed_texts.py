"""读取 input/*.txt，清洗并按约 512 tokens 切分为 chunks，输出 processed_texts.json

用法:
    python scripts/generate_processed_texts.py --input_dir input --output processed_texts.json --max-tokens 512
"""
import argparse
import json
import os
import re
from glob import glob
import importlib.util
import sys

# 动态加载上层目录的 pdf_processing 模块（确保在 scripts 子目录运行也能找到）
root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if root not in sys.path:
    sys.path.insert(0, root)
try:
    from pdf_processing import clean_text as base_clean_text, split_sentences, chunk_sentences
except Exception:
    # 兜底：按路径直接加载模块
    spec = importlib.util.spec_from_file_location('pdf_processing', os.path.join(root, 'pdf_processing.py'))
    pdf_processing = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pdf_processing)
    base_clean_text = pdf_processing.clean_text
    split_sentences = pdf_processing.split_sentences
    chunk_sentences = pdf_processing.chunk_sentences


def clean_text_extra(raw: str) -> str:
    # 基于 pdf_processing.clean_text 的额外清洗：去掉页眉页脚常见模式
    t = base_clean_text(raw)
    lines = []
    for ln in t.splitlines():
        s = ln.strip()
        if not s:
            continue
        # 常见页码样式：第 1 页 / 第1页
        if re.fullmatch(r'第\s*\d+\s*页', s):
            continue
        # 连续短横线或星号分隔行
        if re.fullmatch(r'[-*_]{3,}', s):
            continue
        # 英文 Page 1 / 页码样式已在 base_clean_text 里处理，这里补充中文
        lines.append(s)
    # 合并多重空行为单个换行
    txt = '\n'.join(lines)
    txt = re.sub(r'\n{2,}', '\n\n', txt)
    return txt


def process_all_txt(input_dir: str, output_path: str, max_tokens: int = 512):
    files = sorted(glob(os.path.join(input_dir, '*.txt')))
    all_chunks = []
    gid = 1
    for fp in files:
        with open(fp, 'r', encoding='utf-8') as f:
            raw = f.read()
        cleaned = clean_text_extra(raw)
        sents = split_sentences(cleaned)
        chunks = chunk_sentences(sents, max_tokens=max_tokens)
        for i, c in enumerate(chunks, 1):
            item = {
                'id': gid,
                'file': os.path.basename(fp),
                'chunk_index': i,
                'text': c
            }
            all_chunks.append(item)
            gid += 1
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    return all_chunks


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input_dir', default='input')
    p.add_argument('--output', default='processed_texts.json')
    p.add_argument('--max-tokens', type=int, default=512)
    args = p.parse_args()
    chunks = process_all_txt(args.input_dir, args.output, max_tokens=args.max_tokens)
    print(f'Found {len(chunks)} chunks from {args.input_dir}, saved to {args.output}')


if __name__ == '__main__':
    main()
