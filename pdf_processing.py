"""PDF 或纯文本 -> 清洗文本 -> 分块（支持 token 估算）

用法示例:
    python pdf_processing.py --input plan.pdf --output processed_texts.json
    python pdf_processing.py --text input/text1.txt --output processed_texts.json

依赖: pdfplumber, tiktoken (可选), tqdm
"""
import argparse
import json
import re
import os
import pdfplumber

try:
    import tiktoken
except Exception:
    tiktoken = None


def extract_text_from_pdf(path):
    pages = []
    with pdfplumber.open(path) as pdf:
        for p in pdf.pages:
            txt = p.extract_text() or ""
            pages.append(txt)
    return "\n".join(pages)


def clean_text(text):
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


def chunk_sentences(sentences, max_tokens=512):
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


def process_text_file(input_path, output_path, max_tokens=512):
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


def process_pdf(input_path, output_path, max_tokens=512):
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
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', default=None)
    p.add_argument('--text', '-t', default=None, help='纯文本文件路径')
    p.add_argument('--output', '-o', default='processed_texts.json')
    p.add_argument('--max-tokens', type=int, default=512)
    args = p.parse_args()
    if args.text:
        print('Processing text file:', args.text)
        items = process_text_file(args.text, args.output, max_tokens=args.max_tokens)
    elif args.input:
        print('Processing PDF:', args.input)
        items = process_pdf(args.input, args.output, max_tokens=args.max_tokens)
    else:
        raise SystemExit('请提供 --input (PDF) 或 --text (纯文本文件) 参数')
    print(f'Saved {len(items)} chunks to', args.output)


if __name__ == '__main__':
    main()
