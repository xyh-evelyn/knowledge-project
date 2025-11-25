import json

def main():
    with open('processed_texts.json', 'r', encoding='utf-8') as f:
        items = json.load(f)
    print('Total chunks:', len(items))
    for it in items[:5]:
        print('-', it.get('file'), 'chunk', it.get('chunk_index'), 'len', len(it.get('text','')))

if __name__ == '__main__':
    main()
