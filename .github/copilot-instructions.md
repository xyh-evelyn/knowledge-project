# AI Coding Agent Instructions for Knowledge Graph Pipeline

## Architecture Overview
This is a modular knowledge graph construction pipeline for urban planning texts, processing PDFs/texts into Neo4j graphs via LLM-driven NER and relation extraction.

**Core Flow**: `pdf_processing.py` → `ner_llm.py` → `relation_extraction.py` → `clean_triplets.py` → `neo4j_import.py`

**Key Components**:
- `src/` contains reusable modules; root-level scripts are convenience entry points
- Data flows through JSON intermediates: `processed_texts.json` → `entities_extracted.json` → `triplets_final.json` → `triplets_cleaned.json`
- Orchestrator in `pipeline_orchestrator.py` integrates the full pipeline with demo/llm modes

## Critical Workflows
- **Environment Setup**: Activate venv, install deps (no requirements.txt - install manually: openai, neo4j, tqdm, spacy), download `zh_core_web_sm`, set env vars (`OPENAI_API_KEY`, `GRAPHRAG_*`, `NEO4J_*`)
- **Running Pipeline**: Use `main.py` for staged runs (e.g., `python main.py all --text input/text1.txt --neo4j-password $pwd`) or `pipeline_orchestrator.py` for end-to-end
- **Always Clean Triplets**: Run `clean_triplets.py --input triplets_final.json --output triplets_cleaned.json` before Neo4j import to normalize relations and remove invalid triplets
- **Neo4j Import**: Uses `MERGE` for incremental updates; sanitize relation names to uppercase (e.g., "位于" → "位于")

## Project Conventions
- **Entity Types**: Urban planning specific - Location, Land use function, Direction, Concept, Planned activity (see `ENTITY_DEFINITIONS` in `ner_llm.py`)
- **Relation Normalization**: In `clean_triplets.py`, synonyms like "推进/促进/推动" → "推进"; only keep triplets with keywords like "推进", "实现", "发展"
- **Prompt Engineering**: Chinese prompts with few-shot examples; system prompts define strict extraction rules (no hallucination)
- **Error Handling**: Try/except for optional imports (e.g., OpenAI); tqdm progress bars; argparse CLIs
- **Testing**: pytest in `tests/` for spacy functions; validate JSON structures and token analyses

## Integration Points
- **LLM APIs**: OpenAI client or GraphRAG (SiliconFlow); env vars for API keys/bases/models
- **Neo4j**: Bolt protocol; supports Aura remote DBs; Cypher MERGE for nodes/relationships
- **SpaCy**: Chinese model `zh_core_web_sm` for syntax analysis in relation extraction prompts

## Key Files to Reference
- [pipeline_orchestrator.py](pipeline_orchestrator.py): End-to-end integration example
- [src/ner_llm.py](src/ner_llm.py): Entity definitions and LLM prompting patterns
- [clean_triplets.py](clean_triplets.py): Cleaning heuristics and relation mapping
- [src/neo4j_import.py](src/neo4j_import.py): Graph import logic with sanitization</content>
<parameter name="filePath">d:\中国建筑设计研究院\knowledgeProject\.github\copilot-instructions.md