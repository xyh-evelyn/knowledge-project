"""Neo4j 导入模块（src 版本）。"""
import json
import re
from tqdm import tqdm
from neo4j import GraphDatabase


def sanitize_rel(rel):
    s = re.sub(r"\W+", "_", str(rel)).strip('_')
    if not s:
        s = 'REL'
    if not re.match(r'^[A-Za-z]', s):
        s = 'R_' + s
    return s.upper()


def import_triplets(uri, user, password, input_json, database=None):
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with open(input_json, 'r', encoding='utf-8') as f:
        data = json.load(f)

    total = 0
    for item in data:
        t = item.get('triplets', [])
        if isinstance(t, list):
            total += len(t)

    pbar = tqdm(total=total, desc='Importing to Neo4j')

    if database:
        with driver.session(database=database) as session:
            def import_batch(tx):
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
                        cypher = (
                            f"MERGE (a:Entity {{name: $head}}) "
                            f"MERGE (b:Entity {{name: $tail}}) "
                            f"MERGE (a)-[r:{rel_type}]->(b) SET r.name = $rel"
                        )
                        tx.run(cypher, head=head, tail=tail, rel=str(rel))
                        pbar.update(1)
            session.execute_write(import_batch)
    else:
        with driver.session() as session:
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
                    cypher = (
                        f"MERGE (a:Entity {{name: $head}}) "
                        f"MERGE (b:Entity {{name: $tail}}) "
                        f"MERGE (a)-[r:{rel_type}]->(b) SET r.name = $rel"
                    )
                    session.run(cypher, head=head, tail=tail, rel=str(rel))
                    pbar.update(1)

    pbar.close()
    driver.close()


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--input', '-i', default='triplets_final.json')
    p.add_argument('--uri', default='bolt://localhost:7687')
    p.add_argument('--user', default='neo4j')
    p.add_argument('--password', required=True)
    p.add_argument('--database', default=None)
    args = p.parse_args()
    import_triplets(args.uri, args.user, args.password, args.input, database=args.database)
