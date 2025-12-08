"""端到端管道协调脚本（src 版本）
核心功能：整合文本分块、实体抽取（NER）、句法分析、关系抽取（RE）、倒排索引构建、Neo4j导入
支持两种运行模式：demo（离线本地演示）、llm（调用大模型在线处理），实现从纯文本到知识图谱的全流程自动化
"""
import os
import json
import subprocess
from tqdm import tqdm  # 进度条显示，提升用户体验

# 导入各模块核心函数（来自src子目录）
from src.pdf_processing import process_text_file  # 文本分块处理（复用之前的文本清洗、分块逻辑）
from src.spacy_nlp import analyze_sentence_syntax  # 句法分析（解析句子结构，辅助关系抽取）
from src.prompt_builder import build_core_prompt  # Prompt构建（为关系抽取生成大模型提示词）

# 尝试导入LLM版实体抽取函数（若导入失败则设为None，对应demo模式）
try:
    from src.ner_llm import run as ner_run
except Exception:
    ner_run = None

# 尝试导入本地demo模块（离线版NER/RE，无大模型依赖，用于演示）
try:
    import src.demo_local as demo_local
except Exception:
    demo_local = None

# 尝试导入LLM版关系抽取依赖（call_llm调用大模型，extract_json_array解析响应）
try:
    from src.relation_extraction import call_llm, extract_json_array
except Exception:
    call_llm = None
    extract_json_array = None


def build_inverted_index(triplets_list):
    """
    构建倒排索引：以实体为key，关联包含该实体的所有三元组、原文和id
    核心用途：快速查询实体相关的所有知识（如查找"城市更新"涉及的所有关系和文本）
    :param triplets_list: 包含三元组的完整数据列表（每个元素含id、text、triplets）
    :return: 倒排索引字典（格式：{实体名: [{'id': 文本块id, 'text': 原文, 'triplet': [头, 关系, 尾]}]}）
    """
    idx = {}  # 倒排索引字典
    # 遍历每个文本块的三元组数据
    for item in triplets_list:
        tid = item.get('id')  # 文本块id
        text = item.get('text')  # 文本块原文
        triples = item.get('triplets') or []  # 当前文本块的三元组列表（默认空列表）
        
        # 遍历每个三元组
        for tri in triples:
            # 过滤非法三元组（必须是列表且长度≥3：[头实体, 关系, 尾实体]）
            if not (isinstance(tri, list) and len(tri) >= 3):
                continue
            h, r, t = tri[0], tri[1], tri[2]  # 解包头实体、关系、尾实体
            
            # 为头实体和尾实体分别构建索引（确保两个实体都能关联到该三元组）
            for ent in [h, t]:
                key = str(ent).strip()  # 实体名标准化（转字符串+去首尾空格）
                if not key:  # 跳过空实体名
                    continue
                # 若实体未在索引中，初始化空列表；否则复用已有列表
                lst = idx.setdefault(key, [])
                # 添加当前实体关联的元数据
                lst.append({'id': tid, 'text': text, 'triplet': [h, r, t]})
    return idx


def call_relation_llm_for_item(text, syntax_info, core_concepts):
    """
    调用大模型进行单文本块的关系抽取（LLM模式专用）
    :param text: 待抽取关系的文本块原文
    :param syntax_info: 句法分析结果（辅助大模型理解句子结构）
    :param core_concepts: 核心概念列表（聚焦抽取与核心概念相关的关系）
    :return: 抽取的三元组列表（解析后的JSON格式）
    """
    # 构建大模型Prompt：整合原文、句法分析结果、核心概念，生成结构化任务指令
    prompt = build_core_prompt(
        text,  # 文本块原文
        para_content=text,  # 段落内容（此处与text一致，适配prompt_builder函数参数）
        syntax_info=syntax_info,  # 句法分析结果
        core_concepts=core_concepts  # 核心概念（如["城市更新"]）
    )
    
    # 检查call_llm是否可用（避免未导入成功时调用报错）
    if call_llm is None:
        raise RuntimeError('relation_extraction.call_llm 不可用，请确保正确安装openai包并配置环境变量')
    
    # 构建大模型消息列表（仅用户消息，Prompt已包含完整任务定义）
    messages = [{"role": "user", "content": prompt}]
    # 调用大模型获取响应
    resp = call_llm(messages)
    
    # 解析大模型响应为三元组列表
    try:
        triplets = extract_json_array(resp)
    except Exception:
        # 解析失败时，记录错误信息和原始响应
        triplets = {"error": 'parse_error', 'raw': resp}
    return triplets


def run_pipeline(
        input_text_path,
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
    """
    端到端知识图谱构建管道：文本分块→NER→句法分析→RE→倒排索引→Neo4j导入
    :param input_text_path: 输入纯文本文件路径（必填）
    :param processed_output: 文本分块输出JSON路径（默认：processed_texts.json）
    :param ner_output: 实体抽取（NER）输出JSON路径（默认：entities_extracted.json）
    :param triplets_output: 关系抽取（RE）输出JSON路径（默认：triplets_final.json）
    :param index_output: 倒排索引输出JSON路径（默认：index.json）
    :param mode: 运行模式（demo=离线演示，llm=调用大模型；默认demo）
    :param core_concepts: 核心概念列表（聚焦抽取相关实体/关系；默认空列表）
    :param import_neo4j: 是否导入Neo4j（默认False；True需提供数据库连接信息）
    :param neo4j_uri: Neo4j连接地址（如bolt://localhost:7687）
    :param neo4j_user: Neo4j用户名（默认None）
    :param neo4j_password: Neo4j密码（默认None）
    :param neo4j_db: Neo4j目标数据库名称（可选，默认None）
    """
    # 初始化核心概念列表（默认空列表，避免None值异常）
    core_concepts = core_concepts or []
    
    # -------------------------- 步骤1：文本分块处理 --------------------------
    print('1) 分块文本...')
    # 调用pdf_processing的process_text_file：清洗文本→句子分割→按token分块
    items = process_text_file(input_text_path, processed_output)
    print(f'  保存分块到 {processed_output} (文本块数量={len(items)})')
    
    # -------------------------- 步骤2：实体抽取（NER）--------------------------
    print('2) 运行实体抽取（NER）...')
    if mode == 'llm':
        # LLM模式：调用大模型进行实体抽取（依赖ner_llm.py）
        if ner_run is None:
            raise RuntimeError('ner_llm.run 不可用，请确保正确导入src.ner_llm模块')
        ner_run(processed_output, ner_output)  # 输入：分块文本；输出：实体结果
        print(f'  ✓ LLM版NER完成，结果保存到 {ner_output}')
    
    elif mode == 'demo':
        # Demo模式：离线处理（无大模型依赖）
        if demo_local is not None:
            # 若demo_local模块存在，调用离线版NER和RE（一次性生成结果）
            print('  运行本地DEMO版NER与RE（离线，无大模型依赖）...')
            # 离线NER：生成实体结果
            ner_results = demo_local.demo_ner(processed_output)
            with open(ner_output, 'w', encoding='utf-8') as f:
                json.dump(ner_results, f, ensure_ascii=False, indent=2)
            print(f'  ✓ NER结果保存到 {ner_output}（{len(ner_results)} 条数据）')
            
            # 离线RE：基于NER结果生成三元组
            re_results = demo_local.demo_re(ner_output)
            with open(triplets_output, 'w', encoding='utf-8') as f:
                json.dump(re_results, f, ensure_ascii=False, indent=2)
            print(f'  ✓ RE结果保存到 {triplets_output}（{len(re_results)} 条数据）')
        
        else:
            # 若demo_local模块不存在，使用占位逻辑
            if os.path.exists(ner_output):
                # 若已有NER结果文件，直接复用
                print(f'  复用已存在的NER结果：{ner_output}')
            else:
                # 无现有文件时，生成空实体占位（避免后续步骤报错）
                print('  demo_local模块未找到，生成空实体占位文件')
                # 读取分块文本，为每个文本块生成空实体结构
                with open(processed_output, 'r', encoding='utf-8') as f:
                    proc = json.load(f)
                ent_items = []
                for it in proc:
                    ent_items.append({'id': it.get('id'), 'text': it.get('text'), 'entities': {}})
                # 保存空实体文件
                with open(ner_output, 'w', encoding='utf-8') as f:
                    json.dump(ent_items, f, ensure_ascii=False, indent=2)
                print(f'  ✓ 空实体文件已保存到 {ner_output}')
    
    else:
        # 非法模式：抛出异常
        raise ValueError('未知的运行模式！仅支持 "demo"（离线）或 "llm"（调用大模型）')
    
    # -------------------------- 步骤3：句法分析 + 关系抽取（RE）--------------------------
    print('3) 句法分析并完成关系抽取（RE）...')
    # 读取NER结果文件（实体数据）
    with open(ner_output, 'r', encoding='utf-8') as f:
        ner_items = json.load(f)
    
    all_triplets = []  # 存储最终的完整结果（含id、text、syntax、entities、triplets）
    
    if mode == 'demo' and demo_local is not None and os.path.exists(triplets_output):
        # Demo模式：若已通过demo_local生成RE结果，直接读取并补充句法分析
        with open(triplets_output, 'r', encoding='utf-8') as f:
            re_items = json.load(f)
        
        # 构建实体映射（文本块id→实体字典），用于关联实体数据
        ent_map = {it.get('id'): it.get('entities') for it in ner_items}
        
        # 遍历RE结果，补充句法分析和实体数据
        for it in re_items:
            tid = it.get('id')  # 文本块id
            text = it.get('text')  # 原文
            entities = ent_map.get(tid, {})  # 关联的实体数据
            syntax = analyze_sentence_syntax(text)  # 句法分析（解析句子结构）
            triplets = it.get('triplets')  # 离线RE生成的三元组
            # 添加到最终结果列表
            all_triplets.append({
                'id': tid,
                'text': text,
                'syntax': syntax,
                'entities': entities,
                'triplets': triplets
            })
    
    else:
        # LLM模式 或 Demo模式无离线RE结果：逐文本块调用LLM进行RE
        for it in tqdm(ner_items, desc='RE处理进度'):
            tid = it.get('id')  # 文本块id
            text = it.get('text')  # 原文
            entities = it.get('entities')  # NER提取的实体
            syntax = analyze_sentence_syntax(text)  # 句法分析
            
            # 调用大模型进行关系抽取
            try:
                triplets = call_relation_llm_for_item(text, syntax, core_concepts)
            except Exception as e:
                # 抽取失败时，记录错误信息
                triplets = {'error': str(e)}
            
            # 添加到最终结果列表
            all_triplets.append({
                'id': tid,
                'text': text,
                'syntax': syntax,
                'entities': entities,
                'triplets': triplets
            })
    
    # 保存完整的RE结果（含句法分析和实体数据）
    with open(triplets_output, 'w', encoding='utf-8') as f:
        json.dump(all_triplets, f, ensure_ascii=False, indent=2)
    print(f'  ✓ 完整RE结果保存到 {triplets_output}')
    
    # -------------------------- 步骤4：构建倒排索引 --------------------------
    print('4) 构建实体倒排索引...')
    # 基于完整RE结果构建倒排索引
    idx = build_inverted_index(all_triplets)
    # 保存倒排索引文件
    with open(index_output, 'w', encoding='utf-8') as f:
        json.dump(idx, f, ensure_ascii=False, indent=2)
    print(f'  ✓ 倒排索引保存到 {index_output}')
    
    # -------------------------- 步骤5：导入Neo4j（可选）--------------------------
    if import_neo4j:
        # 校验Neo4j连接信息是否完整
        if not all([neo4j_uri, neo4j_user, neo4j_password]):
            raise RuntimeError('启用Neo4j导入功能需提供完整连接信息：--neo4j-uri/--neo4j-user/--neo4j-password')
        
        print('5) 将三元组导入Neo4j数据库...')
        # 构建调用neo4j_import.py的命令（通过子进程执行）
        cmd = [
            os.environ.get('PYTHON_EXE', 'python'),  # 优先使用环境变量中的Python解释器，默认用系统python
            'neo4j_import.py',  # Neo4j导入脚本路径（需与当前脚本在同一目录）
            '--input', triplets_output,  # 三元组输入文件
            '--uri', neo4j_uri,  # Neo4j连接地址
            '--user', neo4j_user,  # Neo4j用户名
            '--password', neo4j_password  # Neo4j密码
        ]
        # 若指定了目标数据库，添加--database参数
        if neo4j_db:
            cmd += ['--database', neo4j_db]
        
        # 执行命令（check=True：命令失败时抛出异常）
        subprocess.run(cmd, check=True)
        print('  ✓ Neo4j导入完成！')


if __name__ == '__main__':
    """程序主函数：解析命令行参数，启动端到端管道"""
    # 初始化命令行参数解析器
    import argparse
    p = argparse.ArgumentParser(description="端到端知识图谱构建管道（支持demo/llm双模式）")
    
    # 核心输入参数
    p.add_argument('--text', '-t', required=True, help='输入纯文本文件路径（必填）')
    p.add_argument('--mode', choices=['demo', 'llm'], default='demo', help='运行模式：demo（离线无大模型依赖）、llm（调用大模型，需配置API）')
    p.add_argument('--core-concepts', nargs='*', default=['城市更新'], help='核心概念列表（聚焦抽取相关实体/关系，默认：城市更新）')
    
    # Neo4j导入相关参数
    p.add_argument('--import-neo4j', action='store_true', help='是否将三元组导入Neo4j（默认不导入）')
    p.add_argument('--neo4j-uri', default=None, help='Neo4j连接地址（如bolt://localhost:7687，导入时必填）')
    p.add_argument('--neo4j-user', default=None, help='Neo4j用户名（导入时必填）')
    p.add_argument('--neo4j-password', default=None, help='Neo4j密码（导入时必填）')
    p.add_argument('--neo4j-db', default=None, help='Neo4j目标数据库名称（可选）')
    
    # 输出文件路径参数（自定义输出位置）
    p.add_argument('--processed-out', default='processed_texts.json', help='文本分块输出路径')
    p.add_argument('--ner-out', default='entities_extracted.json', help='NER实体输出路径')
    p.add_argument('--triplets-out', default='triplets_final.json', help='RE三元组输出路径')
    p.add_argument('--index-out', default='index.json', help='倒排索引输出路径')
    
    # 解析参数
    args = p.parse_args()
    
    # 启动端到端管道
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

    print('\n✅ 端到端知识图谱构建管道执行完成！')