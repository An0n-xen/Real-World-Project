from __future__ import annotations

import os
from pathlib import Path

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from medagent.config import get_settings
from medagent.logger import get_logger

logger = get_logger(__name__)


class MedicalRAG:
    """Retrieve relevant medical guidelines via RAG.

    Uses ChromaDB as the vector store and HuggingFace sentence-transformers
    for local embeddings (no external API call needed for embeddings).
    """

    def __init__(
        self,
        persist_directory: str | None = None,
    ) -> None:
        settings = get_settings()

        self._embeddings = OpenAIEmbeddings(
            model=settings.embedding_model,
            openai_api_key=settings.deepinfra_api_key,
            openai_api_base=settings.deepinfra_base_url,
            check_embedding_ctx_length=False,
        )
        self._persist_dir = persist_directory or os.path.join(
            settings.output_dir, "chroma_db"
        )
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        self._top_k = settings.rag_top_k
        self._vectorstore: Chroma | None = None
        self._try_load_existing()

        logger.info(
            "MedicalRAG initialised  embed_model=%s  persist=%s",
            settings.embedding_model,
            self._persist_dir,
        )

    def _try_load_existing(self) -> None:
        """Load an existing ChromaDB store from disk if available."""
        if self._vectorstore is not None:
            return
        if os.path.isdir(self._persist_dir):
            store = Chroma(
                persist_directory=self._persist_dir,
                embedding_function=self._embeddings,
            )
            if store._collection.count() > 0:
                self._vectorstore = store
                logger.info(
                    "Loaded existing ChromaDB (%d docs) from %s",
                    store._collection.count(),
                    self._persist_dir,
                )

    def has_data(self) -> bool:
        """Return True if the vector store already contains documents."""
        return self._vectorstore is not None

    # ── Ingestion ──────────────────────────────────────────────

    def load_guidelines(self, path: str | Path, force: bool = False) -> int:
        """Ingest medical guideline documents from *path*.

        *path* can be a single file or a directory.  Supported formats:
        `.txt`, `.md`.

        Skips ingestion if ChromaDB already contains data (use force=True to re-ingest).
        Returns the number of chunks stored (0 if skipped).
        """
        if self.has_data() and not force:
            logger.info("Guidelines already loaded in ChromaDB — skipping ingestion")
            return 0

        path = Path(path)
        texts: list[str] = []
        metadatas: list[dict] = []

        files = list(path.rglob("*")) if path.is_dir() else [path]

        for f in files:
            if f.suffix.lower() not in {".txt", ".md"}:
                logger.debug("Skipping unsupported file: %s", f)
                continue
            content = f.read_text(encoding="utf-8", errors="ignore")
            if not content.strip():
                continue
            texts.append(content)
            metadatas.append({"source": str(f)})
            logger.info("Loaded guideline: %s (%d chars)", f.name, len(content))

        if not texts:
            logger.warning("No guideline documents found in %s", path)
            return 0

        chunks = self._splitter.create_documents(texts, metadatas=metadatas)
        logger.info("Split into %d chunks", len(chunks))

        self._vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self._embeddings,
            persist_directory=self._persist_dir,
        )
        logger.info("ChromaDB vector store persisted to %s", self._persist_dir)
        return len(chunks)

    # ── Query ──────────────────────────────────────────────────

    def query(self, question: str) -> str:
        """Retrieve the top-k relevant guideline passages for *question*."""
        if self._vectorstore is None:
            logger.warning("No vector store available — returning empty context")
            return ""

        docs = self._vectorstore.similarity_search(question, k=self._top_k)
        if not docs:
            logger.warning("No relevant documents found for: %s", question)
            return ""

        context = "\n\n---\n\n".join(doc.page_content for doc in docs)
        logger.info(
            "Retrieved %d guideline passages (%d chars)",
            len(docs),
            len(context),
        )
        return context
