"""端到端管道协调脚本（src 版本）"""
import os
import json
import subprocess
from tqdm import tqdm

from src.pdf_processing import process_text_file
from src.spacy_nlp import analyze_sentence_syntax
from src.prompt_builder import build_core_prompt

try:
    from src.ner_llm import run as ner_run
except Exception:
    ner_run = None

try:
    import src.demo_local as demo_local
except Exception:
    demo_local = None

try:
    from src.relation_extraction import call_llm, extract_json_array
except Exception:
    call_llm = None
    extract_json_array = None


def build_inverted_index(triplets_list):
    idx = {}
    for item in triplets_list:
        tid = item.get('id')
        text = item.get('text')
        triples = item.get('triplets') or []
        for tri in triples:
            if not (isinstance(tri, list) and len(tri) >= 3):
                continue
            h, r, t = tri[0], tri[1], tri[2]
            for ent in [h, t]:
                key = str(ent).strip()
                if not key:
                    continue
                lst = idx.setdefault(key, [])
                lst.append({'id': tid, 'text': text, 'triplet': [h, r, t]})
    return idx


def call_relation_llm_for_item(text, syntax_info, core_concepts):
    prompt = build_core_prompt(text, para_content=text, syntax_info=syntax_info, core_concepts=core_concepts)
    if call_llm is None:
        raise RuntimeError('relation_extraction.call_llm 不可用')
    messages = [{"role": "user", "content": prompt}]
    resp = call_llm(messages)
    try:
        triplets = extract_json_array(resp)
    except Exception:
        triplets = {"error": 'parse_error', 'raw': resp}
    return triplets


def run_pipeline(input_text_path,
                 processed_output='processed_texts.json',
                 ner_output='entities_extracted.json',
                 triplets_output='triplets_final.json',
                 index_output='index.json',
                 mode='demo',
                 core_concepts=None,
                 import_neo4j=False,
                 neo4j_uri=None,
                 neo4j_user=None,
                 neo4j_password=None,
                 neo4j_db=None):

    core_concepts = core_concepts or []
    print('1) 分块文本...')
    items = process_text_file(input_text_path, processed_output)
    print(f'  保存分块到 {processed_output} (chunks={len(items)})')
    if mode == 'llm':
        if ner_run is None:
            raise RuntimeError('ner_llm.run 不可用')
        print('2) 运行 NER (LLM)...')
        ner_run(processed_output, ner_output)
    elif mode == 'demo':
        if demo_local is None:
            if os.path.exists(ner_output):
                print('2) 使用已存在的 NER 输出:', ner_output)
            else:
                print('2) demo_local 未找到，使用空实体占位')
                with open(processed_output, 'r', encoding='utf-8') as f:
                    proc = json.load(f)
                ent_items = []
                for it in proc:
                    ent_items.append({'id': it.get('id'), 'text': it.get('text'), 'entities': {}})
                with open(ner_output, 'w', encoding='utf-8') as f:
                    json.dump(ent_items, f, ensure_ascii=False, indent=2)
        else:
            print('2) 运行本地 DEMO NER 与 RE（离线）...')
            ner_results = demo_local.demo_ner(processed_output)
            with open(ner_output, 'w', encoding='utf-8') as f:
                json.dump(ner_results, f, ensure_ascii=False, indent=2)
            print(f'  ✓ {ner_output} 已生成（{len(ner_results)} 条数据）')
            re_results = demo_local.demo_re(ner_output)
            with open(triplets_output, 'w', encoding='utf-8') as f:
                json.dump(re_results, f, ensure_ascii=False, indent=2)
            print(f'  ✓ {triplets_output} 已生成（{len(re_results)} 条数据）')
    else:
        raise ValueError('未知 mode, 支持 demo 或 llm')
    print('3) 句法分析并调用 RE...')
    with open(ner_output, 'r', encoding='utf-8') as f:
        ner_items = json.load(f)
    all_triplets = []
    if mode == 'demo' and demo_local is not None and os.path.exists(triplets_output):
        with open(triplets_output, 'r', encoding='utf-8') as f:
            re_items = json.load(f)
        ent_map = {it.get('id'): it.get('entities') for it in ner_items}
        for it in re_items:
            tid = it.get('id')
            text = it.get('text')
            entities = ent_map.get(tid, {})
            syntax = analyze_sentence_syntax(text)
            triplets = it.get('triplets')
            all_triplets.append({'id': tid, 'text': text, 'syntax': syntax, 'entities': entities, 'triplets': triplets})
    else:
        for it in tqdm(ner_items, desc='Processing'):
            tid = it.get('id')
            text = it.get('text')
            entities = it.get('entities')
            syntax = analyze_sentence_syntax(text)
            try:
                triplets = call_relation_llm_for_item(text, syntax, core_concepts)
            except Exception as e:
                triplets = {'error': str(e)}
            all_triplets.append({'id': tid, 'text': text, 'syntax': syntax, 'entities': entities, 'triplets': triplets})
    with open(triplets_output, 'w', encoding='utf-8') as f:
        json.dump(all_triplets, f, ensure_ascii=False, indent=2)
    print('Saved triplets to', triplets_output)
    print('4) 构建倒排索引...')
    idx = build_inverted_index(all_triplets)
    with open(index_output, 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print('Saved index to', index_output)
    if import_neo4j:
        if not all([neo4j_uri, neo4j_user, neo4j_password]):
            raise RuntimeError('导入 Neo4j 需要提供 --neo4j-uri/--neo4j-user/--neo4j-password')
        print('5) 将三元组导入 Neo4j...')
        cmd = [
            os.environ.get('PYTHON_EXE', 'python'), 'neo4j_import.py', '--input', triplets_output,
            '--uri', neo4j_uri, '--user', neo4j_user, '--password', neo4j_password
        ]
        if neo4j_db:
            cmd += ['--database', neo4j_db]
        subprocess.run(cmd, check=True)


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--text', '-t', required=True, help='输入纯文本文件')
    p.add_argument('--mode', choices=['demo', 'llm'], default='demo')
    p.add_argument('--core-concepts', nargs='*', default=['城市更新'])
    p.add_argument('--import-neo4j', action='store_true')
    p.add_argument('--neo4j-uri', default=None)
    p.add_argument('--neo4j-user', default=None)
    p.add_argument('--neo4j-password', default=None)
    p.add_argument('--neo4j-db', default=None)
    p.add_argument('--processed-out', default='processed_texts.json')
    p.add_argument('--ner-out', default='entities_extracted.json')
    p.add_argument('--triplets-out', default='triplets_final.json')
    p.add_argument('--index-out', default='index.json')
    args = p.parse_args()
    run_pipeline(
        input_text_path=args.text,
        processed_output=args.processed_out,
        ner_output=args.ner_out,
        triplets_output=args.triplets_out,
        index_output=args.index_out,
        mode=args.mode,
        core_concepts=args.core_concepts,
        import_neo4j=args.import_neo4j,
        neo4j_uri=args.neo4j_uri,
        neo4j_user=args.neo4j_user,
        neo4j_password=args.neo4j_password,
        neo4j_db=args.neo4j_db,
    )
