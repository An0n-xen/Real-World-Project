# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MedAgent-Pro — an AI-powered medical diagnosis platform using LangChain/LangGraph with open-source LLMs (via DeepInfra API). It combines RAG-informed planning, VLM image analysis, dynamic code generation, and weighted indicator synthesis through a 7-node agentic workflow.

## Tech Stack

- **Backend:** Python 3.12+, FastAPI, LangChain/LangGraph, ChromaDB, Pydantic v2
- **Frontend:** Next.js 16, React 19, TypeScript (strict), CSS Modules
- **LLMs:** Qwen2.5-VL-32B (vision), Qwen2.5-72B (text), BGE-large-en (embeddings) — all via DeepInfra
- **Package managers:** uv (Python), npm (frontend)

## Common Commands

### Backend
```bash
uv sync                                          # Install Python dependencies
uv run uvicorn api:app --host 0.0.0.0 --port 8000 --reload  # Start API server
uv run python main.py ingest --disease glaucoma  # Ingest guidelines into RAG
uv run python main.py plan --disease glaucoma    # Generate diagnostic plan
uv run python main.py diagnose --disease glaucoma --image path/to/image.jpg  # Run diagnosis
```

### Frontend
```bash
cd frontend
npm install        # Install dependencies
npm run dev        # Dev server on :3000
npm run build      # Production build (static export)
npm start          # Production server
npm run lint       # ESLint
```

## Architecture

### LangGraph 7-Node Pipeline (`src/medagent/workflow.py`)

1. **load_config** → Load disease task.json, toolset.json, init RAG
2. **retrieve_guidelines** → Semantic search of clinical guidelines via ChromaDB
3. **generate_plan** → Planner agent creates structured diagnostic steps
4. **generate_tools** → Coding agent generates Python functions for quantitative analysis
5. **execute_steps** → Runs plan steps (segmentation tools + VLM qualitative analysis + concept extraction)
6. **collect_indicators** → Aggregates diagnostic indicators
7. **final_decision** → Decider agent synthesizes weighted indicators into final diagnosis

### API (`api.py`, port 8000)

- `GET /api/diseases` — List configured diseases
- `GET /api/results` — List past diagnosis records
- `GET /api/results/{disease}/{record}` — Full result bundle
- `POST /api/diagnose` — Streaming diagnosis via NDJSON (Server-Sent Events)
  - Progress: `{"type": "progress", "node": "..."}`
  - Result: `{"type": "result", "data": {...}}`

### Frontend → Backend

Next.js rewrites `/api/*` and `/static/*` to `localhost:8000` (configured in `next.config.ts`). The frontend reads NDJSON streams line-by-line for real-time progress updates.

### Key Modules

| Module | Purpose |
|--------|---------|
| `src/medagent/config.py` | Pydantic Settings with .env loading |
| `src/medagent/schemas.py` | All data models (TaskConfig, PlanStep, DiagnosisResult, etc.) |
| `src/medagent/agents/planner.py` | RAG-informed diagnostic plan generation |
| `src/medagent/agents/analyzer.py` | VLM qualitative image analysis (base64 encoded) |
| `src/medagent/agents/coding_agent.py` | Dynamic Python function generation |
| `src/medagent/agents/decider.py` | Final weighted diagnosis synthesis |
| `src/medagent/agents/disease_setup.py` | Bootstrap new diseases via SerpAPI |
| `src/medagent/rag/retriever.py` | ChromaDB + DeepInfra embeddings |
| `src/medagent/knowledge/concept_linker.py` | Medical concept extraction (DR.KNOWS-style) |
| `src/medagent/tools/registry.py` | Dynamic tool registration & invocation |
| `src/medagent/tracer.py` | Pipeline observability (NodeTrace, PipelineTrace) |

### Disease Configuration

Each disease lives in `diseases/{name}/` with:
- `task.json` — Diagnostic goal definition
- `toolset.json` — Available tools
- `plan.json` — Pre-generated or dynamic diagnostic plan
- `guidelines/` — Clinical reference documents (.md, .txt) for RAG
- `tools/` — Disease-specific tool implementations

### Output Artifacts

Diagnosis results saved to `output/{disease}/record/` as JSON:
- `pipeline_trace.json`, `reasoning_trace.json`, `concepts.json`, `brief_diagnosis.json`, `final_diagnosis.json`

## Environment Variables

Required in `.env` (see `.env.example`):
- `DEEPINFRA_API_KEY` — Required for all LLM calls
- `SERPAPI_API_KEY` — Required for disease setup (guideline search)
- `LANGSMITH_API_KEY` — Optional, for LangSmith tracing
- Model overrides: `PRIMARY_VLM_MODEL`, `TEXT_LLM_MODEL`, `EMBEDDING_MODEL`
- RAG tuning: `RAG_CHUNK_SIZE` (default 1000), `RAG_TOP_K` (default 5)
