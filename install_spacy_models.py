"""安装 spaCy 及中文模型的辅助脚本

运行此脚本会在当前 Python 环境中：
 1. 使用 pip 安装 `requirements.txt` 中列出的包（包含 spacy）
 2. 尝试下载并安装小型中文模型 `zh_core_web_sm`
 3. 如果已安装 transformers 支持，则提示是否下载 `zh_core_web_trf`（仅尝试，不强制）

用法（在项目根目录并激活虚拟环境）：
  python install_spacy_models.py

注意：脚本会调用 pip 与 python -m spacy download，需要网络访问并可能需要较长时间。
"""
import subprocess
import sys
import shutil

PY = sys.executable

def run(cmd, check=True):
    print('>',' '.join(cmd))
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(res.stdout)
    if check and res.returncode != 0:
        raise SystemExit(f"命令失败: {' '.join(cmd)}\n退出码: {res.returncode}")

def main():
    print('1) 安装 requirements.txt 中的包...')
    if not shutil.which('pip'):
        print('警告：未找到全局 pip，使用当前 Python 执行 pip 模块')
    run([PY, '-m', 'pip', 'install', '-r', 'requirements.txt'])

    print('\n2) 尝试下载中文小模型 zh_core_web_sm ...')
    try:
        run([PY, '-m', 'spacy', 'download', 'zh_core_web_sm'])
    except SystemExit as e:
        print('下载 zh_core_web_sm 失败：', e)

    # 如果 transformers 可用，提示用户是否尝试 trf 模型
    try:
        import importlib
        trf_ok = importlib.util.find_spec('transformers') is not None
    except Exception:
        trf_ok = False

    if trf_ok:
        print('\n检测到 transformers 支持，可选择下载更高精度但较大的模型 zh_core_web_trf。')
        try:
            run([PY, '-m', 'spacy', 'download', 'zh_core_web_trf'])
        except SystemExit as e:
            print('下载 zh_core_web_trf 失败：', e)
    else:
        print('\n未检测到 transformers；若需要 trf 模型，请先安装 extras:')
        print('  pip install -U "spacy[transformers]"')

    print('\n完成。你现在可以运行:')
    print(f'  {PY} -c "import spacy; print(spacy.__version__)"')
    print('并在 Python 中导入模型:')
    print("  import spacy; nlp = spacy.load('zh_core_web_sm')")

if __name__ == '__main__':
    main()
