"""Prompt builder (src 版本)"""
from typing import Dict, List, Any


def build_core_prompt(sentence: str,
                      para_content: str,
                      syntax_info: Dict[str, Any],
                      core_concepts: List[str]) -> str:
    dep = syntax_info.get('dep') or syntax_info.get('dependency') or ''
    con = syntax_info.get('con') or syntax_info.get('con_pos') or syntax_info.get('const') or ''
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
    s = '政府加强建设城市基础设施。'
    para = '本段描述了城市更新背景与政策导向。'
    syntax = {'dep': '政府(nsubj) -> 加强(ROOT) -> 建设(dobj)', 'con': '政府(NOUN) 加强(VERB) 建设(NOUN)'}
    concepts = ['城市更新', '交通网络']
    print(build_core_prompt(s, para, syntax, concepts))
