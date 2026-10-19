"""Indexeur sémantique et lexical par sections Markdown (`services/rag/indexer.py`).

Conformément à ADR-005 :
- Découpe tous les fichiers Markdown de `docs/`, `AGENTS.md` (et `infra/ansible/` si présents)
  selon leurs titres de sections (`#`, `##`, `###`).
- Construit un index vectoriel `TfidfVectorizer` (`scikit-learn`) avec suppression des mots
  vides français/anglais afin d'éviter toute similarité artificielle sur des questions hors-sujet.
- Associe chaque extrait à une référence précise : `[Source: <fichier>#<section>]`.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT_DIR: Path = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STOP_WORDS_FR_EN: list[str] = [
    "le", "la", "les", "de", "du", "des", "un", "une", "et", "ou", "en", "dans",
    "sur", "avec", "pour", "par", "au", "aux", "ce", "cet", "cette", "ces", "mon",
    "ton", "son", "notre", "votre", "leur", "que", "qui", "quoi", "dont", "ou",
    "comment", "pourquoi", "quand", "quel", "quelle", "quels", "quelles", "est",
    "sont", "etre", "avoir", "fait", "faire", "peut", "plus", "moins", "tres",
    "pas", "ne", "ni", "mais", "donc", "or", "car", "si", "comme", "tout", "tous",
    "toute", "toutes", "meme", "autres", "autre", "entre", "sans", "sous", "vers",
    "chez", "depuis", "pendant", "avant", "apres", "alors", "ainsi", "cela", "ca",
    "the", "is", "are", "was", "were", "be", "been", "to", "of", "and", "in",
    "that", "have", "it", "for", "not", "on", "with", "as", "you", "do", "at",
    "this", "but", "his", "by", "from", "they", "we", "say", "her", "she", "or",
    "an", "will", "my", "one", "all", "would", "there", "their", "what", "so",
    "up", "out", "if", "about", "who", "get", "which", "go", "me", "when", "make",
    "can", "like", "no", "just", "him", "know", "take", "into", "your", "some",
    "could", "them", "see", "other", "than", "then", "now", "look", "only", "come",
    "its", "over", "think", "also", "back", "after", "use", "two", "how", "our",
]

HEADING_RE = re.compile(r"^(#{1,3})\s+(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True)
class DocumentChunk:
    """Représente une section indexée issue d'un document officiel du projet."""

    chunk_id: str
    source_file: str
    section_title: str
    citation: str
    content: str


class MarkdownSectionIndexer:
    """Indexeur documentaire TF-IDF par sections Markdown."""

    def __init__(self, root_dir: Path | str = ROOT_DIR) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.chunks: list[DocumentChunk] = []
        self.vectorizer: TfidfVectorizer | None = None
        self.tfidf_matrix: Any = None
        self.reindex()

    def _discover_files(self) -> list[Path]:
        files: list[Path] = []
        agents_md = self.root_dir / "AGENTS.md"
        if agents_md.exists():
            files.append(agents_md)

        docs_dir = self.root_dir / "docs"
        if docs_dir.exists():
            files.extend(sorted(docs_dir.rglob("*.md")))

        ansible_dir = self.root_dir / "infra" / "ansible"
        if ansible_dir.exists():
            files.extend(sorted(ansible_dir.rglob("*.md")))
            files.extend(sorted(ansible_dir.rglob("*.yml")))

        scenarios_dir = self.root_dir / "scenarios"
        if scenarios_dir.exists():
            files.extend(sorted(scenarios_dir.rglob("*.md")))

        return files

    def _split_markdown_sections(self, file_path: Path) -> list[DocumentChunk]:
        rel_path = file_path.relative_to(self.root_dir).as_posix()
        try:
            raw_text = file_path.read_text(encoding="utf-8")
        except Exception:
            return []

        if not raw_text.strip():
            return []

        if file_path.suffix.lower() in (".yml", ".yaml"):
            title = f"Playbook {file_path.name}"
            citation = f"[Source: {rel_path}#{title}]"
            return [
                DocumentChunk(
                    chunk_id=f"{rel_path}#{title}",
                    source_file=rel_path,
                    section_title=title,
                    citation=citation,
                    content=f"{title}\n{raw_text.strip()}",
                )
            ]

        matches = list(HEADING_RE.finditer(raw_text))
        if not matches:
            title = file_path.stem
            citation = f"[Source: {rel_path}#{title}]"
            return [
                DocumentChunk(
                    chunk_id=f"{rel_path}#{title}",
                    source_file=rel_path,
                    section_title=title,
                    citation=citation,
                    content=raw_text.strip(),
                )
            ]

        doc_title = matches[0].group(2).strip()
        extracted: list[DocumentChunk] = []

        for idx, match in enumerate(matches):
            sec_title = match.group(2).strip()
            # Nettoyage des backticks éventuels dans le titre pour des citations propres
            clean_title = sec_title.replace("`", "").strip()
            start_pos = match.start()
            end_pos = matches[idx + 1].start() if idx + 1 < len(matches) else len(raw_text)
            section_body = raw_text[start_pos:end_pos].strip()

            # On ignore les en-têtes vides (qui ne contiennent que le titre sans texte avant un sous-titre)
            body_without_heading = section_body[len(match.group(0)) :].strip()
            if len(body_without_heading) < 15 and idx + 1 < len(matches):
                continue

            enriched_text = f"{doc_title} — {clean_title}\n{section_body}"
            citation = f"[Source: {rel_path}#{clean_title}]"
            extracted.append(
                DocumentChunk(
                    chunk_id=f"{rel_path}#{clean_title}",
                    source_file=rel_path,
                    section_title=clean_title,
                    citation=citation,
                    content=enriched_text,
                )
            )

        return extracted

    def reindex(self) -> int:
        """Parcourt l'arborescence documentaire et reconstruit la matrice TF-IDF."""
        discovered = self._discover_files()
        all_chunks: list[DocumentChunk] = []
        for fpath in discovered:
            all_chunks.extend(self._split_markdown_sections(fpath))

        self.chunks = all_chunks
        if not self.chunks:
            self.vectorizer = None
            self.tfidf_matrix = None
            return 0

        self.vectorizer = TfidfVectorizer(
            lowercase=True,
            strip_accents="unicode",
            stop_words=STOP_WORDS_FR_EN,
            ngram_range=(1, 2),
            sublinear_tf=True,
            token_pattern=r"(?u)\b[a-zA-Z0-9_\-]{2,}\b",
        )
        corpus = [c.content for c in self.chunks]
        self.tfidf_matrix = self.vectorizer.fit_transform(corpus)
        return len(self.chunks)

    def search(self, query: str, top_k: int = 3) -> list[dict[str, Any]]:
        """Recherche les `top_k` sections les plus pertinentes par similarité cosinus TF-IDF pondérée OOV."""
        if not query or not query.strip() or self.vectorizer is None or self.tfidf_matrix is None:
            return []

        import unicodedata

        normalized_q = (
            unicodedata.normalize("NFKD", query)
            .encode("ascii", "ignore")
            .decode("ascii")
            .lower()
        )
        raw_tokens = re.findall(r"(?u)\b[a-zA-Z0-9_\-]{2,}\b", normalized_q)
        stop_set = set(STOP_WORDS_FR_EN)
        content_tokens = [t for t in raw_tokens if t not in stop_set]
        if not content_tokens:
            return []

        vocab = self.vectorizer.vocabulary_
        in_vocab_tokens = [t for t in content_tokens if t in vocab]
        if not in_vocab_tokens:
            return []

        # Facteur de couverture du vocabulaire : évite que TfidfVectorizer ne normalise à 1.0
        # un unique mot ambigu (ex: "recette", "service", "port") dans une question hors-sujet.
        vocab_coverage = len(in_vocab_tokens) / len(content_tokens)

        q_vec = self.vectorizer.transform([query])
        if q_vec.nnz == 0:
            return []

        raw_sims = cosine_similarity(q_vec, self.tfidf_matrix)[0]
        sims = raw_sims * vocab_coverage
        ranked_indices = np.argsort(sims)[::-1][: max(1, top_k)]

        results: list[dict[str, Any]] = []
        for idx in ranked_indices:
            score = float(sims[int(idx)])
            if score <= 0.0:
                continue
            chunk = self.chunks[int(idx)]
            results.append(
                {
                    "chunk_id": chunk.chunk_id,
                    "source_file": chunk.source_file,
                    "section_title": chunk.section_title,
                    "citation": chunk.citation,
                    "similarity_score": round(score, 4),
                    "content": chunk.content,
                    "excerpt": chunk.content[:650].strip(),
                }
            )
        return results
