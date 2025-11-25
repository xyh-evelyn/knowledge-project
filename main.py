"""命令行入口：按阶段运行数据准备、实体抽取、关系抽取与 Neo4j 导入。"""
import argparse
import subprocess
import sys
import os


def run_cmd(args_list, cwd=None):
    cwd = cwd or os.path.dirname(__file__)
    cmd = [sys.executable] + args_list
    print('Running:', ' '.join(cmd))
    subprocess.run(cmd, check=True, cwd=cwd)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('stage', choices=['data', 'ner', 're', 'import', 'all'])
    p.add_argument('--pdf', default=None, help='输入 PDF 文件 (data 阶段)')
    p.add_argument('--text', default=None, help='输入纯文本文件 (data 阶段)')
    p.add_argument('--neo4j-password', default=None, help='Neo4j 密码 (import 阶段)')
    args = p.parse_args()

    if args.stage == 'data':
        if args.text:
            run_cmd(['src\\pdf_processing.py', '--text', args.text, '--output', 'processed_texts.json'])
        elif args.pdf:
            run_cmd(['src\\pdf_processing.py', '--input', args.pdf, '--output', 'processed_texts.json'])
        else:
            raise SystemExit('请提供 --pdf 或 --text 参数')

    elif args.stage == 'ner':
        run_cmd(['src\\ner_llm.py', '--input', 'processed_texts.json', '--output', 'entities_extracted.json'])

    elif args.stage == 're':
        run_cmd(['src\\relation_extraction.py', '--input', 'entities_extracted.json', '--output', 'triplets_final.json'])

    elif args.stage == 'import':
        pwd = args.neo4j_password or os.getenv('NEO4J_PASSWORD')
        if not pwd:
            raise SystemExit('请通过 --neo4j-password 或环境变量 NEO4J_PASSWORD 提供 Neo4j 密码')
        run_cmd(['src\\neo4j_import.py', '--input', 'triplets_final.json', '--password', pwd])

    elif args.stage == 'all':
        if args.text:
            run_cmd(['src\\pdf_processing.py', '--text', args.text, '--output', 'processed_texts.json'])
        elif args.pdf:
            run_cmd(['src\\pdf_processing.py', '--input', args.pdf, '--output', 'processed_texts.json'])
        else:
            raise SystemExit('请提供 --pdf 或 --text 参数以运行 all')
        pwd = args.neo4j_password or os.getenv('NEO4J_PASSWORD')
        if not pwd:
            raise SystemExit('请通过 --neo4j-password 或环境变量 NEO4J_PASSWORD 提供 Neo4j 密码')
        run_cmd(['src\\ner_llm.py', '--input', 'processed_texts.json', '--output', 'entities_extracted.json'])
        run_cmd(['src\\relation_extraction.py', '--input', 'entities_extracted.json', '--output', 'triplets_final.json'])
        run_cmd(['src\\neo4j_import.py', '--input', 'triplets_final.json', '--password', pwd])


if __name__ == '__main__':
    main()
