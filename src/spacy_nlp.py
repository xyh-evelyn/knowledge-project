"""spaCy 中文句法分析工具（src 版本，已优化为仅加载一次模型）"""
from typing import Dict, Optional

# 全局缓存的 nlp 对象，避免对每个句子重复加载 spaCy 模型（极慢）
_NLP_CACHE = None  # type: ignore[var-annotated]
_NLP_MODEL_NAME: Optional[str] = None


def _get_nlp(model_name: Optional[str] = None):
    """
    返回已加载的 spaCy 中文模型（带全局缓存）。
    第一次调用时加载模型，后续复用，大幅降低整体运行时间。
    """
    global _NLP_CACHE, _NLP_MODEL_NAME

    if _NLP_CACHE is not None:
        # 若指定了与已缓存不同的模型名称，则重新加载一次
        if model_name and model_name != _NLP_MODEL_NAME:
            _NLP_CACHE = None
        else:
            return _NLP_CACHE

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
    # 默认优先尝试大模型，其次是小模型
    candidates.extend(["zh_core_web_trf", "zh_core_web_sm"])

    last_err = None
    for m in candidates:
        try:
            _NLP_CACHE = spacy.load(m)
            _NLP_MODEL_NAME = m
            break
        except Exception as e:
            last_err = e
            continue

    if _NLP_CACHE is None:
        raise RuntimeError(
            "找不到可用的 spaCy 中文模型。请安装并下载一个中文模型，例如:\n"
            "pip install -U spacy\n"
            "python -m spacy download zh_core_web_sm\n"
        ) from last_err

    return _NLP_CACHE


def analyze_sentence_syntax(text: str, model_name: str = None) -> Dict[str, object]:
    """
    对输入文本进行句法分析。

    性能优化说明：
    - 通过 `_get_nlp` 使用全局缓存的 spaCy 模型；
    - 整个进程生命周期内模型只加载一次，大幅减少运行时间。
    """
    if not isinstance(text, str) or not text.strip():
        return {'tokens': [], 'dep': '', 'con_pos': '', 'dep_triples': []}

    nlp = _get_nlp(model_name)
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
