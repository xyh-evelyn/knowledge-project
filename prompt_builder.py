"""构造发送给 LLM 的核心 Prompt。

提供函数:
    build_core_prompt(sentence, para_content, syntax_info, core_concepts) -> str

该函数按用户要求的模板严格构造最终 Prompt（使用 Python f-string 风格）。
"""
from typing import Dict, List, Any


def build_core_prompt(sentence: str,
                      para_content: str,
                      syntax_info: Dict[str, Any],
                      core_concepts: List[str]) -> str:
    """根据输入构造 LLM 用的最终 Prompt 字符串。

    参数:
        sentence: 当前要处理的句子（本函数模板中并未直接插入句子，但保留为输入以便扩展）。
        para_content: 段落背景上下文文本。
        syntax_info: 句法分析结果字典，至少包含键 'dep' 与 'con'（或 'con_pos'）；如果键名不同，会尝试回退。
        core_concepts: 用户自定义的核心概念列表。

    返回:
        构造好的 Prompt 字符串（已按模板组织）。
    """
    # defensive extraction for syntax_info keys
    dep = syntax_info.get('dep') or syntax_info.get('dependency') or ''
    con = syntax_info.get('con') or syntax_info.get('con_pos') or syntax_info.get('const') or ''

    # format core concepts as a readable list
    if isinstance(core_concepts, (list, tuple)):
        cc_display = ', '.join(str(x) for x in core_concepts)
    else:
        cc_display = str(core_concepts)

    prompt = (
        f"系统：你是一个NLP专家，专注于城市规划领域的关系抽取（RE）任务。\n"
        f"用户：你的任务是根据提供的信息，在每个输入句子中提取关系三元组。\n\n"
        f"段落的背景内容：\n{para_content}\n\n"
        f"句法分析结果：\n"
        f"依存关系：{dep}\n"
        f"成分分析：{con}\n\n"
        f"任务目标：\n"
        f"围绕核心概念【{cc_display}】进行抽取。请确保提取的三元组中，头实体或尾实体至少有一个与上述核心概念语义高度相关。\n\n"
        f"实体约束（a1）：\n"
        f"- 头实体/主语（h/sbj）和尾实体/宾语（t/obj）必须属于以下类别：[地点, 土地使用功能, 方向, 概念]。\n"
        f"- 关系谓词（r/pred）必须属于：[计划活动, 土地添加] 或同义动作。\n\n"
        f"输出约束（b1）：\n"
        f"- 仅输出关系三元组。避免任何附加的解释或描述。\n"
        f"- 格式严格如下：< h/sbj, r/pred, t/obj >\n"
    )

    return prompt


if __name__ == '__main__':
    # 简单示例
    s = '政府加强建设城市基础设施。'
    para = '本段描述了城市更新背景与政策导向。'
    syntax = {'dep': '政府(nsubj) -> 加强(ROOT) -> 建设(dobj)', 'con': '政府(NOUN) 加强(VERB) 建设(NOUN)'}
    concepts = ['城市更新', '交通网络']
    print(build_core_prompt(s, para, syntax, concepts))
