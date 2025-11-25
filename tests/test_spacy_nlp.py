import pytest

from spacy_nlp import analyze_sentence_syntax


def test_empty_input():
    res = analyze_sentence_syntax('')
    assert isinstance(res, dict)
    assert res['tokens'] == []
    assert res['dep'] == ''
    assert res['con_pos'] == ''
    assert res.get('dep_triples', []) == []


def test_simple_sentence_structure():
    s = '政府加强建设城市基础设施。'
    res = analyze_sentence_syntax(s)
    assert 'tokens' in res and isinstance(res['tokens'], list)
    assert len(res['tokens']) >= 3
    # token structure
    tok0 = res['tokens'][0]
    assert set(['text', 'lemma', 'pos', 'tag', 'dep', 'i', 'head_i', 'head_text']).issubset(tok0.keys())
    # dep and con_pos strings include token texts
    assert '政府' in res['dep']
    assert '政府' in res['con_pos']
    # dep_triples exists and basic shape
    assert 'dep_triples' in res and isinstance(res['dep_triples'], list)
    assert all(set(['head_i','head_text','dep','child_i','child_text']).issubset(t.keys()) for t in res['dep_triples'])
