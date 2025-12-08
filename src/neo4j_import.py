"""Neo4j 导入模块（src 版本）。
核心功能：将关系抽取生成的三元组（triplets_final.json）导入 Neo4j 数据库，
构建实体-关系-实体的知识图谱，支持自定义数据库连接配置和数据清洗。
"""
import json
import re
from tqdm import tqdm  # 进度条显示，直观展示导入进度
from neo4j import GraphDatabase  # Neo4j 官方Python驱动，用于连接和操作数据库


def sanitize_rel(rel):
    """
    关系类型清洗：将原始关系谓词转换为 Neo4j 支持的合法关系类型
    Neo4j 关系类型规则：只能包含字母、数字、下划线，且必须以字母开头，建议大写
    :param rel: 原始关系谓词（如"相关于"、"促进"、"属于"）
    :return: 清洗后的合法关系类型（如"相关于"→"相关于"，"a-b"→"A_B"，"123"→"R_123"）
    """
    # 1. 替换所有非字母数字的字符为下划线（\W+ 匹配非字母数字下划线，这里用_替换）
    # 2. 去除首尾多余的下划线
    s = re.sub(r"\W+", "_", str(rel)).strip('_')
    # 3. 若清洗后为空字符串（如原始关系是纯特殊字符），默认设为"REL"
    if not s:
        s = 'REL'
    # 4. 若清洗后以非字母开头（如数字、下划线），添加前缀"R_"确保符合Neo4j规则
    if not re.match(r'^[A-Za-z]', s):
        s = 'R_' + s
    # 5. 转换为全大写（Neo4j关系类型惯例，增强可读性）
    return s.upper()


def import_triplets(uri, user, password, input_json, database=None):
    """
    核心导入函数：读取三元组JSON文件，批量导入Neo4j数据库
    :param uri: Neo4j 连接地址（默认bolt协议，格式：bolt://localhost:7687）
    :param user: Neo4j 用户名（默认"neo4j"）
    :param password: Neo4j 密码（必填，用于身份验证）
    :param input_json: 三元组输入文件路径（默认triplets_final.json）
    :param database: 目标数据库名称（可选，默认使用Neo4j默认数据库）
    """
    # 1. 初始化Neo4j驱动（建立与数据库的连接通道）
    driver = GraphDatabase.driver(uri, auth=(user, password))
    
    # 2. 读取三元组JSON文件：加载包含id、text、triplets的列表数据
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # 3. 计算总三元组数量（用于进度条初始化）
    total = 0
    for item in data:
        # 获取当前文本块的三元组列表（默认空列表避免KeyError）
        t = item.get('triplets', [])
        if isinstance(t, list):  # 确保是列表类型（避免数据格式异常）
            total += len(t)

    # 4. 初始化进度条（总进度为三元组总数）
    pbar = tqdm(total=total, desc='Importing to Neo4j')

    # 5. 分两种情况导入：指定数据库 / 使用默认数据库
    if database:
        # 连接指定名称的Neo4j数据库（适用于Neo4j 4.0+多数据库功能）
        with driver.session(database=database) as session:
            # 定义批量导入函数（用于事务执行，提升导入效率）
            def import_batch(tx):
                # 遍历每个文本块的数据
                for item in data:
                    triplets = item.get('triplets', [])
                    if not isinstance(triplets, list):  # 过滤非列表格式的三元组数据
                        continue
                    # 遍历当前文本块的每个三元组
                    for tri in triplets:
                        # 过滤非法三元组（必须是列表且长度≥3：[头实体, 关系, 尾实体]）
                        if not (isinstance(tri, list) and len(tri) >= 3):
                            pbar.update(1)  # 进度条计数+1（跳过非法数据）
                            continue
                        # 解包三元组：头实体、原始关系、尾实体
                        head, rel, tail = tri[0], tri[1], tri[2]
                        # 清洗关系类型，确保符合Neo4j规则
                        rel_type = sanitize_rel(rel)
                        # 构建Cypher语句（Neo4j查询语言）
                        cypher = (
                            f"MERGE (a:Entity {{name: $head}}) "  # 合并头实体：存在则复用，不存在则创建（标签为Entity，属性name为头实体名）
                            f"MERGE (b:Entity {{name: $tail}}) "  # 合并尾实体：同上
                            f"MERGE (a)-[r:{rel_type}]->(b) SET r.name = $rel"  # 合并关系：存在则复用，不存在则创建；设置关系属性name为原始关系名
                        )
                        # 执行Cypher语句，传入参数（避免SQL注入风险，提升效率）
                        tx.run(cypher, head=head, tail=tail, rel=str(rel))
                        pbar.update(1)  # 进度条计数+1（成功处理一个三元组）
            # 执行写入事务（批量处理，减少数据库交互次数，提升性能）
            session.execute_write(import_batch)
    else:
        # 连接Neo4j默认数据库（不指定数据库名称）
        with driver.session() as session:
            # 遍历每个文本块的数据（逻辑与指定数据库一致，仅无批量事务封装）
            for item in data:
                triplets = item.get('triplets', [])
                if not isinstance(triplets, list):
                    continue
                for tri in triplets:
                    if not (isinstance(tri, list) and len(tri) >= 3):
                        pbar.update(1)
                        continue
                    head, rel, tail = tri[0], tri[1], tri[2]
                    rel_type = sanitize_rel(rel)
                    # 构建Cypher语句（与上面一致）
                    cypher = (
                        f"MERGE (a:Entity {{name: $head}}) "
                        f"MERGE (b:Entity {{name: $tail}}) "
                        f"MERGE (a)-[r:{rel_type}]->(b) SET r.name = $rel"
                    )
                    # 执行Cypher语句
                    session.run(cypher, head=head, tail=tail, rel=str(rel))
                    pbar.update(1)

    # 6. 导入完成：关闭进度条和Neo4j驱动（释放资源）
    pbar.close()
    driver.close()


if __name__ == '__main__':
    """程序主函数：解析命令行参数，启动Neo4j导入流程"""
    # 初始化命令行参数解析器
    import argparse
    p = argparse.ArgumentParser(description="Neo4j知识图谱导入工具：将三元组数据导入Neo4j数据库")
    
    # 定义命令行参数
    p.add_argument('--input', '-i', default='triplets_final.json', help='三元组输入JSON文件路径（默认：triplets_final.json）')
    p.add_argument('--uri', default='bolt://localhost:7687', help='Neo4j连接地址（默认：bolt://localhost:7687，bolt为Neo4j二进制协议）')
    p.add_argument('--user', default='neo4j', help='Neo4j用户名（默认：neo4j）')
    p.add_argument('--password', required=True, help='Neo4j密码（必填，用于数据库身份验证）')
    p.add_argument('--database', default=None, help='目标数据库名称（可选，适用于Neo4j多数据库功能，默认使用默认数据库）')
    
    # 解析参数
    args = p.parse_args()
    
    # 启动导入流程：传入解析后的参数
    import_triplets(args.uri, args.user, args.password, args.input, database=args.database)