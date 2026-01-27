"""
命令行入口：按阶段运行整个 pipeline
支持的阶段：data, ner, re, clean, complete, kgc, import, all

用法示例：
    python main.py data --text input/text1.txt
    python main.py ner
    python main.py re
    python main.py clean
    python main.py complete
    python main.py kgc --queries queries.json
    python main.py all --text input/text1.txt
"""
import argparse
import subprocess
import sys
import os
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent))

from src.config import validate_config, ensure_output_dirs, print_config


def run_cmd(module_args, cwd=None, description=""):
    """执行 Python 子模块"""
    cwd = cwd or os.path.dirname(__file__)
    cmd = [sys.executable, "-m"] + module_args
    
    print("\n" + "="*70)
    if description:
        print(f"📍 {description}")
    print(f"⚙️  运行: {' '.join(cmd)}")
    print("="*70)
    
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        print(f"\n❌ 错误：命令执行失败 (返回码: {result.returncode})")
        sys.exit(1)
    print(f"✓ 完成")


def main():
    parser = argparse.ArgumentParser(
        description="城市规划知识图谱构建 Pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法：
  # 完整流程
  python main.py all --text input/text1.txt

  # 分阶段运行
  python main.py data --text input/text1.txt
  python main.py ner
  python main.py re
  python main.py clean
  python main.py complete
  python main.py kgc --queries queries.json
  python main.py import

  # 查看配置
  python main.py config
        """
    )
    
    parser.add_argument(
        'stage',
        choices=['data', 'ner', 're', 'clean', 'complete', 'kgc', 'import', 'all', 'config'],
        help='执行的流程阶段'
    )
    parser.add_argument('--text', '-t', default=None, help='输入纯文本文件路径 (data 阶段)')
    parser.add_argument('--pdf', '-p', default=None, help='输入 PDF 文件路径 (data 阶段)')
    parser.add_argument('--queries', '-q', default=None, help='查询文件路径 (kgc 阶段)')
    parser.add_argument('--epochs', type=int, default=50, help='KGC 训练轮数（默认: 50）')
    parser.add_argument('--show-config', action='store_true', help='显示配置信息')
    
    args = parser.parse_args()
    
    # 初始化配置
    try:
        if args.stage != 'config':
            ensure_output_dirs()
            validate_config()
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)
    
    if args.show_config or args.stage == 'config':
        print_config()
        return
    
    # ======================== 阶段 1：data（文本预处理）========================
    if args.stage == 'data':
        if args.text:
            run_cmd(
                ['src.pdf_processing', '--text', args.text],
                description="阶段 1/6：文本预处理"
            )
        elif args.pdf:
            run_cmd(
                ['src.pdf_processing', '--input', args.pdf],
                description="阶段 1/6：文本预处理"
            )
        else:
            print("❌ 错误：请提供 --text 或 --pdf 参数")
            sys.exit(1)
    
    # ======================== 阶段 2：ner（实体识别）========================
    elif args.stage == 'ner':
        run_cmd(
            ['src.ner_llm'],
            description="阶段 2/6：命名实体识别 (NER)"
        )
    
    # ======================== 阶段 3：re（关系抽取）========================
    elif args.stage == 're':
        run_cmd(
            ['src.relation_extraction'],
            description="阶段 3/6：关系抽取 (RE)"
        )
    
    # ======================== 阶段 4：clean（三元组清洗）========================
    elif args.stage == 'clean':
        run_cmd(
            ['clean_triplets'],
            description="阶段 4/6：三元组清洗"
        )
    
    # ======================== 阶段 5：complete（关联补全）========================
    elif args.stage == 'complete':
        run_cmd(
            ['triplet_link_completion'],
            description="阶段 5/6：关联补全（解决孤岛问题）"
        )
    
    # ======================== 阶段 6：kgc（知识图谱补全）========================
    elif args.stage == 'kgc':
        if not args.queries:
            print("❌ 错误：KGC 阶段需要提供 --queries 参数（查询文件路径）")
            sys.exit(1)
        
        cmd_args = ['generate_kgc_predictions', '--queries', args.queries]
        if args.epochs != 50:
            cmd_args.extend(['--epochs', str(args.epochs)])
        
        run_cmd(
            cmd_args,
            description="可选阶段：知识图谱补全 (KGC)"
        )
    
    # ======================== 阶段 7：import（Neo4j 导入）========================
    elif args.stage == 'import':
        run_cmd(
            ['src.neo4j_import'],
            description="可选阶段：Neo4j 导入"
        )
    
    # ======================== 完整流程：all========================
    elif args.stage == 'all':
        if args.text:
            run_cmd(['src.pdf_processing', '--text', args.text],
                   description="阶段 1/5：文本预处理")
        elif args.pdf:
            run_cmd(['src.pdf_processing', '--input', args.pdf],
                   description="阶段 1/5：文本预处理")
        else:
            print("❌ 错误：请提供 --text 或 --pdf 参数")
            sys.exit(1)
        
        run_cmd(['src.ner_llm'], description="阶段 2/5：实体识别")
        run_cmd(['src.relation_extraction'], description="阶段 3/5：关系抽取")
        run_cmd(['clean_triplets'], description="阶段 4/5：三元组清洗")
        run_cmd(['triplet_link_completion'], description="阶段 5/5：关联补全")
        
        print("\n" + "="*70)
        print("✅ Pipeline 运行完成！")
        print("="*70)
        print("\n下一步操作：")
        print("  1. 查看三元组结果: output/output_tripletscompleted/triplets_completed.json")
        print("  2. （可选）进行 KGC 预测: python main.py kgc --queries queries.json")
        print("  3. （可选）导入 Neo4j: python main.py import")


if __name__ == '__main__':
    main()
