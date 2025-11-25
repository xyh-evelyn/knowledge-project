from neo4j import GraphDatabase

uri='bolt+ssc://aca21d27.databases.neo4j.io'
user='neo4j'
password='lSxrlawYdmJpBwD4JR4cHaJF0eznAi7RNq1HTzhTz88'
db='neo4j'

driver=GraphDatabase.driver(uri, auth=(user,password))
with driver.session(database=db) as s:
    # Try simpler queries first
    try:
        result = s.run('RETURN 1 as num')
        print('连接成功')
    except Exception as e:
        print('连接失败:', e)
    
    # Count all nodes without label filter
    n = s.run('MATCH (n) RETURN count(n) as c').single().get('c')
    r = s.run('MATCH ()-[r]->() RETURN count(r) as c').single().get('c')
    print('节点总数:', n)
    print('关系总数:', r)
    
    if n > 0:
        print('\n标签示例:')
        labels_res = s.run('MATCH (n) RETURN distinct labels(n) LIMIT 10')
        for row in labels_res:
            print(row[0])
        
        print('\n示例三元组:')
        res = s.run("MATCH (a)-[r]->(b) RETURN labels(a) as a_labels, properties(a) as a_props, type(r) as rel, properties(r) as r_props, labels(b) as b_labels, properties(b) as b_props LIMIT 5")
        for row in res:
            print(row['a_labels'], row['a_props'], '-', row['rel'], '->', row['b_labels'], row['b_props'])
    else:
        print('\nNo data found in database')

driver.close()
