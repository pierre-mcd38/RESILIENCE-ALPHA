"""Microservice Assistant Documentaire RAG Local (`services/rag`)."""

from services.rag.app import (
    SIMILARITY_THRESHOLD,
    LocalRAGAssistant,
    app,
    create_app,
    rag_assistant,
)
from services.rag.indexer import DocumentChunk, MarkdownSectionIndexer

__all__ = [
    "DocumentChunk",
    "LocalRAGAssistant",
    "MarkdownSectionIndexer",
    "SIMILARITY_THRESHOLD",
    "app",
    "create_app",
    "rag_assistant",
]
