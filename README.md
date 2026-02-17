# 🏥 MedAgent-Pro

> **Evidence-based multi-modal medical diagnosis via reasoning agentic workflow**

An agentic medical diagnosis platform inspired by the [MedAgent-Pro paper](https://arxiv.org/abs/2503.18968), built with **LangChain/LangGraph**, powered by open-source models on **DeepInfra**.


The platform implements a **hierarchical diagnostic workflow**:

1. **Disease-Level Planning** — RAG-retrieves clinical guidelines, then the Planner agent generates a structured step-by-step diagnostic plan
2. **Patient-Level Reasoning** — The orchestrator executes each plan step using quantitative tools (segmentation, computation) and qualitative VLM analysis
3. **Evidence-Based Decision** — The Decider agent synthesises all indicators with clinical weights into a final diagnosis

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| **Framework** | LangChain + LangGraph |
| **VLM** | Qwen/Qwen2.5-VL-32B-Instruct (via DeepInfra) |
| **Text LLM** | Qwen/Qwen2.5-72B-Instruct (via DeepInfra) |
| **Embeddings** | BAAI/bge-large-en-v1.5 (via DeepInfra) |
| **Vector Store** | ChromaDB |
| **Logging** | colorlog (color-coded, structured) |
| **Package Manager** | uv |
| **Schemas** | Pydantic v2 |

---

## Project Structure

```
Real-World-Project/
├── main.py                          # CLI entry point
├── pyproject.toml                   # Dependencies & build config
├── .env.example                     # API key template
├── src/
│   └── medagent/
│       ├── __init__.py
│       ├── config.py                # Pydantic-settings configuration
│       ├── logger.py                # Colorlog factory
│       ├── schemas.py               # Data models (TaskConfig, PlanStep, etc.)
│       ├── workflow.py              # LangGraph 7-node pipeline
│       ├── rag/
│       │   └── retriever.py         # ChromaDB + DeepInfra embeddings
│       ├── agents/
│       │   ├── planner.py           # Disease-level plan generation
│       │   ├── coding_agent.py      # Dynamic code generation
│       │   ├── analyzer.py          # Multi-modal VLM analysis
│       │   ├── summarizer.py        # Clinical summary generation
│       │   └── decider.py           # Weighted indicator synthesis
│       └── tools/
│           ├── registry.py          # Dynamic tool registry
│           └── medical_tools.py     # Placeholder segmentation tools
└── diseases/
    └── glaucoma/
        ├── task.json                # Disease config
        ├── toolset.json             # Available tools
        └── guidelines/
            └── glaucoma_guidelines.md  # Clinical criteria (CDR, ISNT, etc.)
```

---

## Quick Start

### 1. Prerequisites

- Python ≥ 3.12
- [uv](https://docs.astral.sh/uv/) package manager
- [DeepInfra](https://deepinfra.com/) API key

### 2. Installation

```bash
git clone <repo-url>
cd Real-World-Project
uv sync
```

### 3. Configuration

```bash
cp .env.example .env
```

Edit `.env` and add your DeepInfra API key:

```env
DEEPINFRA_API_KEY=your_key_here
```

### 4. Usage

#### Ingest Medical Guidelines
Load clinical guidelines into the RAG vector store:
```bash
uv run python main.py ingest --disease glaucoma
```

#### Generate Diagnostic Plan
Create a structured diagnostic workflow for a disease:
```bash
uv run python main.py plan --disease glaucoma
```

#### Run Full Diagnosis
Execute the complete pipeline on a patient image:
```bash
uv run python main.py diagnose --disease glaucoma --image path/to/fundus.jpg
```

---

## Pipeline Deep Dive

###  RAG Module (`rag/retriever.py`)
Retrieves relevant medical guidelines using ChromaDB + DeepInfra embeddings. Guidelines are chunked, embedded, and stored for similarity search during plan generation.

###  Planner Agent (`agents/planner.py`)
Takes the disease config, toolset, and RAG context to generate a JSON plan — an ordered list of steps with tool assignments, dependency chains, and output types.

###  Coding Agent (`agents/coding_agent.py`)
Dynamically generates Python functions for quantitative computation steps (e.g., cup-to-disc ratio calculation from segmentation masks).

###  Analyzer Agent (`agents/analyzer.py`)
Sends medical images (base64-encoded) to the multi-modal VLM for qualitative assessment — detecting abnormalities, noting visual features, and providing confidence scores.

###  Summary Agent (`agents/summarizer.py`)
Condenses detailed VLM analysis into brief clinical summaries with severity ratings and key findings.

###  Decider Agent (`agents/decider.py`)
Synthesises all diagnostic indicators by proposing clinical weights and a decision threshold. Computes a weighted abnormality score and produces the final diagnosis.

---

## Adding New Diseases

1. Create a directory under `diseases/`:
   ```
   diseases/diabetic_retinopathy/
   ├── task.json
   ├── toolset.json
   └── guidelines/
       └── dr_guidelines.md
   ```

2. Define the task in `task.json`:
   ```json
   {
       "input": "Fundus image of the patient",
       "disease": "Diagnose diabetic retinopathy"
   }
   ```

3. Define available tools in `toolset.json` (see `diseases/glaucoma/toolset.json` for format)

4. Add clinical guidelines as `.md` or `.txt` files in the `guidelines/` directory

5. Run the pipeline:
   ```bash
   uv run python main.py ingest --disease diabetic_retinopathy
   uv run python main.py diagnose --disease diabetic_retinopathy --image path/to/image.jpg
   ```

---

## Configuration

All settings can be overridden via environment variables or `.env`:

| Variable | Default | Description |
|----------|---------|-------------|
| `DEEPINFRA_API_KEY` | — | DeepInfra API key (required) |
| `PRIMARY_VLM_MODEL` | `Qwen/Qwen2.5-VL-32B-Instruct` | Multi-modal VLM |
| `TEXT_LLM_MODEL` | `Qwen/Qwen2.5-72B-Instruct` | Text-only LLM |
| `EMBEDDING_MODEL` | `BAAI/bge-large-en-v1.5` | Embedding model |
| `LOG_LEVEL` | `INFO` | Logging level |
| `RAG_CHUNK_SIZE` | `1000` | RAG chunk size |
| `RAG_TOP_K` | `5` | Number of RAG results |

---

## Extending with Real Tools

The placeholder segmentation tools in `tools/medical_tools.py` can be replaced with real models:

```python
# Example: integrating MedSAM for optic disc segmentation
def segment_optic_disc(image_path: str, save_dir: str, save_name: str) -> str:
    from medsam import MedSAM
    model = MedSAM.load("optic_disc")
    mask = model.predict(image_path)
    output_path = os.path.join(save_dir, save_name)
    mask.save(output_path)
    return output_path
```

Register new tools in `tools/registry.py` or add them to `toolset.json`.

---

## References

- **Paper**: [MedAgent-Pro: Towards Evidence-based Multi-modal Medical Diagnosis via Reasoning Agentic Workflow](https://arxiv.org/abs/2503.18968)
- **Original Repo**: [jinlab-imvr/MedAgent-Pro](https://github.com/jinlab-imvr/MedAgent-Pro)

---

## License

MIT
