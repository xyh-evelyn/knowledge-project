from spacy_nlp import analyze_sentence_syntax


def test_punctuation_handling():
    s = '项目A、项目B和项目C，均需完成。'
    res = analyze_sentence_syntax(s)
    # punctuation tokens should appear
    texts = [t['text'] for t in res['tokens']]
    assert '、' in texts or '，' in texts
    assert res['dep_triples']


def test_complex_sentence():
    s = '在考虑到居民需求和环境影响后，规划团队决定调整方案以提高可持续性。'
    res = analyze_sentence_syntax(s)
    # should have multiple clauses, tokens > 5
    assert len(res['tokens']) > 5
    assert any('决定' in t['text'] for t in res['tokens'])
    assert res['dep_triples']


def test_special_characters():
    s = '新材料(如A型)已通过ISO-9001认证—性能良好。'
    res = analyze_sentence_syntax(s)
    texts = [t['text'] for t in res['tokens']]
    # parentheses and hyphen-like characters should be tokenized or present
    assert any(ch in texts for ch in ['(', ')', '-', '—']) or any('ISO' in t for t in texts)
    assert res['dep_triples']
