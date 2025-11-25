"""spaCy 中文句法分析工具

提供函数:
    analyze_sentence_syntax(text) -> dict

返回字典包含:
    - 'dep': 依存关系字符串（示例: "政府(nsubj) -> 加强(ROOT) -> 建设(dobj)"）
    - 'con_pos': 词性/成分标注字符串（示例: "政府(NOUN) 加强(VERB) 建设(NOUN)"）

注意: 需要先安装 `spacy` 与中文模型，例如:
    pip install -U spacy
    python -m spacy download zh_core_web_sm

此模块对缺少依赖或模型提供友好错误提示。
"""
from typing import Dict

def analyze_sentence_syntax(text: str, model_name: str = None) -> Dict[str, object]:
    """分析中文句子的依存关系与词性标注。

    Args:
        text: 待分析的中文句子或文本片段。
        model_name: 可选 spaCy 模型名，默认会尝试 'zh_core_web_trf'，再尝试 'zh_core_web_sm'.

    Returns:
        dict: 结构化结果，示例：
            {
                'tokens': [
                    {'text': '政府', 'lemma': '政府', 'pos': 'NOUN', 'tag': 'NN', 'dep': 'nsubj', 'i':0, 'head_i':1, 'head_text':'加强'},
                    ...
                ],
                'dep': '政府(nsubj) -> 加强(ROOT) -> 建设(dobj)',
                'con_pos': '政府(NOUN) 加强(VERB) 建设(NOUN)'
            }

    Raises:
        RuntimeError: 当 spacy 未安装或模型不可用时，包含安装/下载建议。
    """
    if not isinstance(text, str) or not text.strip():
        return {'tokens': [], 'dep': '', 'con_pos': ''}

    # lazy import to keep module import cheap and allow py_compile to pass
    try:
        import spacy
    except Exception as e:  # pragma: no cover - runtime dependency
        raise RuntimeError(
            "spaCy 未安装。请先运行: pip install -U spacy；\n"
            "然后下载中文模型，例如: python -m spacy download zh_core_web_sm"
        ) from e

    # model selection
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
            "或者指定模型名称传入 analyze_sentence_syntax(..., model_name='your_model')"
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

    # build dependency triples: head ->(dep) -> child
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
    # 简单交互示例（仅在本地有安装模型时可运行）
    sample = "政府加强建设城市基础设施。"
    try:
        res = analyze_sentence_syntax(sample)
        print('Dep:', res['dep'])
        print('Con/Pos:', res['con_pos'])
    except RuntimeError as err:
        print('错误:', err)
