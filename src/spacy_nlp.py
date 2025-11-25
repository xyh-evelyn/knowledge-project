"""spaCy 中文句法分析工具（src 版本）"""
from typing import Dict


def analyze_sentence_syntax(text: str, model_name: str = None) -> Dict[str, object]:
    if not isinstance(text, str) or not text.strip():
        return {'tokens': [], 'dep': '', 'con_pos': '', 'dep_triples': []}
    try:
        import spacy
    except Exception as e:
        raise RuntimeError(
            "spaCy 未安装。请先运行: pip install -U spacy；\n"
            "然后下载中文模型，例如: python -m spacy download zh_core_web_sm"
        ) from e
    candidates = []
    if model_name:
        candidates.append(model_name)
    candidates.extend(["zh_core_web_trf", "zh_core_web_sm"])
    nlp = None
    last_err = None
    for m in candidates:
        try:
            nlp = spacy.load(m)
            break
        except Exception as e:
            last_err = e
            continue
    if nlp is None:
        raise RuntimeError(
            "找不到可用的 spaCy 中文模型。请安装并下载一个中文模型，例如:\n"
            "pip install -U spacy\n"
            "python -m spacy download zh_core_web_sm\n"
        ) from last_err
    doc = nlp(text)
    tokens = []
    dep_parts = []
    con_pos_parts = []
    for token in doc:
        if token.is_space:
            continue
        tok = {
            'text': token.text,
            'lemma': token.lemma_,
            'pos': token.pos_,
            'tag': token.tag_,
            'dep': token.dep_,
            'i': token.i,
            'head_i': token.head.i,
            'head_text': token.head.text,
        }
        tokens.append(tok)
        dep_parts.append(f"{token.text}({token.dep_})")
        con_pos_parts.append(f"{token.text}({token.pos_})")
    dep_str = " -> ".join(dep_parts)
    con_pos_str = " ".join(con_pos_parts)
    dep_triples = []
    for token in doc:
        if token.is_space:
            continue
        dep_triples.append({
            'head_i': token.head.i,
            'head_text': token.head.text,
            'dep': token.dep_,
            'child_i': token.i,
            'child_text': token.text,
        })
    return {'tokens': tokens, 'dep': dep_str, 'con_pos': con_pos_str, 'dep_triples': dep_triples}


if __name__ == '__main__':
    sample = "政府加强建设城市基础设施。"
    try:
        res = analyze_sentence_syntax(sample)
        print('Dep:', res['dep'])
        print('Con/Pos:', res['con_pos'])
    except RuntimeError as err:
        print('错误:', err)
