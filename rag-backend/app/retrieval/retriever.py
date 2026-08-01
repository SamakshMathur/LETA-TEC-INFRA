import faiss
import json
import logging
import threading
import numpy as np
from pathlib import Path
import re

from rank_bm25 import BM25Okapi
from flashrank import Ranker as FlashRanker, RerankRequest
from FlagEmbedding import FlagReranker
from app.config import (
    RERANKING_MODEL, EMBEDDING_MODEL, VECTOR_DIM,
    VECTOR_SEARCH_TOP_K, VECTOR_EXPANDED_TOP_K, BM25_TOP_K, MMR_LAMBDA,
)
from app.retrieval.reranker import LegalReranker
from app.retrieval.statute_retriever import StatuteRetriever
from app.retrieval.provision_graph import ProvisionGraphRetriever

logger = logging.getLogger(__name__)

# ─── Pool classification — folder patterns per document category ───────────
_CASE_LAW_FOLDERS     = {"high court case laws", "supreme court case laws", "aar", "other app result"}
_STATUTE_FOLDERS      = {"act", "rules", "cgst", "igst", "utgst", "export"}
_NOTIFICATION_FOLDERS = {"notification", "notifications"}
_CIRCULAR_FOLDERS     = {"circulars", "circular", "icai", "brochures", "faqs"}


def _chunk_category(chunk: dict) -> str:
    path = (chunk.get("rel_path") or chunk.get("source") or
            chunk.get("metadata", {}).get("rel_path", "")).lower().replace("\\", "/")
    for folder in _CASE_LAW_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "case_law"
    for folder in _CIRCULAR_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "circular"
    for folder in _NOTIFICATION_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "notification"
    for folder in _STATUTE_FOLDERS:
        if f"/{folder}/" in path or path.startswith(folder + "/"):
            return "statute"
    return "other"

# ─── Thread-safe embedding model singleton ─────────────────────────────────
_model = None
_model_lock = threading.Lock()
_model_device = "auto"   # tracks where the model was loaded; "cpu" after GPU fallback


def get_model(force_cpu: bool = False):
    """Returns the embedding model, loading it once with thread safety.

    If force_cpu=True the existing model is discarded and reloaded on CPU.
    This is called automatically after a CUDA error to recover from GPU
    context loss caused by a system sleep / resume cycle.
    """
    global _model, _model_device
    if _model is None or force_cpu:
        with _model_lock:
            if _model is None or force_cpu:
                from sentence_transformers import SentenceTransformer
                device = "cpu" if force_cpu else None   # None = auto-detect
                device_label = "CPU (fallback)" if force_cpu else "auto"
                logger.info(f"Loading embedding model: {EMBEDDING_MODEL} | device={device_label}")
                _model = SentenceTransformer(EMBEDDING_MODEL, device=device)
                _model_device = "cpu" if force_cpu else "auto"
                logger.info(f"Embedding model loaded successfully on {_model_device}")
    return _model


def _is_cuda_error(exc: Exception) -> bool:
    """Returns True for PyTorch CUDA / GPU errors (e.g. after sleep/wake)."""
    name = type(exc).__name__
    msg  = str(exc).lower()
    return (
        "AcceleratorError" in name
        or "CudaError" in name
        or "cuda error" in msg
        or "unknown error" in msg and "cuda" in msg
    )


def embed_query(text: str):
    """
    Embeds a single query string (normalized for cosine similarity with IndexFlatIP).
    Results are cached in Redis by SHA-256(text) — saves 200-400ms per cache hit.

    Automatically recovers from CUDA errors caused by sleep/wake GPU context loss:
    the model is reloaded on CPU and the encode is retried once.
    """
    if not text or not text.strip():
        logger.warning("embed_query called with empty text")
        return None

    # L0: embedding cache (Redis)
    try:
        from app.cache import get_cached_embedding, set_cached_embedding
        cached = get_cached_embedding(text)
        if cached is not None:
            return cached
    except Exception:
        pass  # cache miss or unavailable — proceed to model

    model = get_model()
    try:
        vec = model.encode(text, normalize_embeddings=True)
    except Exception as exc:
        if _is_cuda_error(exc):
            # GPU context lost (sleep/wake cycle) — reload on CPU and retry once
            logger.warning(
                f"CUDA error during embed_query — reloading model on CPU and retrying: {exc}"
            )
            model = get_model(force_cpu=True)
            vec = model.encode(text, normalize_embeddings=True)
        else:
            raise

    # Store for next time
    try:
        set_cached_embedding(text, vec)
    except Exception:
        pass

    return vec


# GST compound phrases used to generate bigram tokens for BM25
_GST_BIGRAMS = frozenset([
    "input tax credit", "reverse charge mechanism", "reverse charge",
    "place of supply", "time of supply", "zero rated supply",
    "show cause notice", "input service distributor", "electronic cash ledger",
    "electronic credit ledger", "inverted duty structure", "composite supply",
    "mixed supply", "works contract", "capital goods", "job work",
    "advance ruling", "high court", "supreme court", "annual return",
    "inter state", "intra state", "e way bill", "transitional credit",
    "input tax", "output tax", "zero rated", "exempt supply",
])

# Abbreviation → full-form expansion for BM25 query preprocessing
_GST_ABBREV = [
    (re.compile(r'\bitc\b', re.IGNORECASE), 'input tax credit ITC'),
    (re.compile(r'\brcm\b', re.IGNORECASE), 'reverse charge mechanism RCM'),
    (re.compile(r'\bscn\b', re.IGNORECASE), 'show cause notice SCN'),
    (re.compile(r'\bisd\b', re.IGNORECASE), 'input service distributor ISD'),
    (re.compile(r'\blut\b', re.IGNORECASE), 'letter of undertaking LUT'),
    (re.compile(r'\bsez\b', re.IGNORECASE), 'special economic zone SEZ'),
    (re.compile(r'\bcgst\b', re.IGNORECASE), 'central goods services tax CGST'),
    (re.compile(r'\bigst\b', re.IGNORECASE), 'integrated goods services tax IGST'),
    (re.compile(r'\bsgst\b', re.IGNORECASE), 'state goods services tax SGST'),
    (re.compile(r'\bgstr\b', re.IGNORECASE), 'return GSTR'),
    (re.compile(r'\bfaq\b', re.IGNORECASE), 'frequently asked questions FAQ'),
    (re.compile(r'\baar\b', re.IGNORECASE), 'advance ruling AAR'),
    (re.compile(r'\bpoc\b', re.IGNORECASE), 'place of supply POS'),
    # CBIC expands to full form — circulars/instructions are issued by CBIC
    (re.compile(r'\bcbic\b', re.IGNORECASE), 'CBIC central board indirect taxes customs circular instruction'),
    # Normalize section shorthand: "sec 16", "s.16", "s16" → "section 16"
    (re.compile(r'\bsec\.?\s*(\d)', re.IGNORECASE), r'section \1'),
    (re.compile(r'\bs\.\s*(\d)', re.IGNORECASE), r'section \1'),
]


def _expand_for_bm25(query: str) -> str:
    """Expand GST abbreviations in a query string for better BM25 keyword coverage."""
    result = query
    for pattern, replacement in _GST_ABBREV:
        result = pattern.sub(replacement, result)
    return result


# ─── Direct legal reference extraction ────────────────────────────────────────
# Maps lowercase act keywords found near a section/rule citation to canonical codes
_ACT_CODE_MAP = [
    ("cgst", "CGST"), ("igst", "IGST"), ("sgst", "SGST"), ("utgst", "UTGST"),
    ("central goods", "CGST"), ("integrated goods", "IGST"),
    ("union territory", "UTGST"),
]


def _extract_query_refs(query: str) -> list:
    """
    Extracts normalized provision keys from a query, matching the format stored
    in chunk.metadata.provisions (e.g. CGST_SEC_16, IGST_SEC_13, CGST_RUL_89).

    Called before FAISS search so that explicitly-cited sections are pinned at
    the top of the retrieval pool, bypassing ranking uncertainty.
    """
    q = query.lower()
    refs = []
    seen: set = set()

    def _act_codes(ctx: str) -> list:
        found = [code for kw, code in _ACT_CODE_MAP if kw in ctx]
        # Remove duplicates while preserving order
        seen_codes: set = set()
        deduped = []
        for c in found:
            if c not in seen_codes:
                seen_codes.add(c)
                deduped.append(c)
        return deduped if deduped else ["CGST", "IGST"]  # try both when no act named

    # Section references: "section 16", "sec 16", "section 2(13)", "sec.16"
    for m in re.finditer(r'\bsec(?:tion)?\s*\.?\s*(\d+)(?:\s*\([^)]{0,12}\))*', q):
        sec = m.group(1)
        ctx = q[max(0, m.start() - 40): m.end() + 40]
        for code in _act_codes(ctx):
            key = f"{code}_SEC_{sec}"
            if key not in seen:
                seen.add(key)
                refs.append(key)

    # Rule references: "rule 89", "rule 42(2)"
    for m in re.finditer(r'\brule\s+(\d+)(?:\s*\([^)]{0,12}\))*', q):
        rule = m.group(1)
        ctx = q[max(0, m.start() - 40): m.end() + 40]
        for code in _act_codes(ctx):
            key = f"{code}_RUL_{rule}"
            if key not in seen:
                seen.add(key)
                refs.append(key)

    # Schedule references: "schedule ii", "schedule iii", "schedule 1"
    for m in re.finditer(r'\bschedule\s+([ivxlcdm]+|\d+)\b', q):
        sch = m.group(1).upper()
        key = f"CGST_SCH_{sch}"
        if key not in seen:
            seen.add(key)
            refs.append(key)

    # Circular references: "Circular No. 183", "Circular 183/15/2022", "CBIC Circular 183"
    for m in re.finditer(r'\bcircular\s+(?:no\.?\s*)?(\d{2,3})\b', q):
        cir_num = m.group(1)
        key = f"CIRCULAR_{cir_num}"
        if key not in seen:
            seen.add(key)
            refs.append(key)

    return refs


def _expand_context_window(
    selected: list,
    doc_map: dict,
    all_chunks: list,
    max_neighbors: int = 2,
) -> list:
    """
    Full-corpus context window expansion.

    For each selected chunk, looks up its document in the startup-built doc_map
    (rel_path → sorted [(page, chunk_index)]) and fetches adjacent-page neighbors
    directly from all_chunks by index. Neighbors can be anywhere in the full corpus,
    not just the 80-chunk retrieval pool — this is the key improvement over the
    previous pool-only version.

    Stores the enriched text in context_text; original text is preserved for
    scoring, snippet display, and the source panel.
    """
    if not doc_map or not all_chunks:
        return selected

    expanded = []
    for chunk in selected:
        rel = chunk.get("rel_path") or chunk.get("metadata", {}).get("rel_path", "")
        pages = chunk.get("pages") or chunk.get("metadata", {}).get("pages") or []
        page = min(pages) if pages else (
            chunk.get("page") or chunk.get("metadata", {}).get("page") or 0
        )
        cid = chunk.get("chunk_id")

        if rel and rel in doc_map and len(doc_map[rel]) > 1:
            neighbor_chunks = []
            for (p, idx) in doc_map[rel]:
                if abs(p - page) <= 2 and 0 <= idx < len(all_chunks):
                    nbr = all_chunks[idx]
                    if nbr.get("chunk_id") != cid:
                        neighbor_chunks.append(nbr)

            if neighbor_chunks:
                neighbor_chunks = neighbor_chunks[:max_neighbors]
                neighbor_texts = [
                    n.get("text", "").strip()
                    for n in neighbor_chunks
                    if n.get("text", "").strip()
                ]
                if neighbor_texts:
                    chunk = chunk.copy()
                    chunk["context_text"] = (
                        chunk.get("text", "")
                        + "\n\n[ADJACENT CONTEXT FROM SAME DOCUMENT]\n"
                        + "\n\n".join(neighbor_texts)
                    )

        expanded.append(chunk)

    return expanded


def tokenize_text(text: str):
    """
    Enhanced BM25 tokenizer that:
    - Preserves section/rule compound references as additional tokens
    - Keeps form codes (DRC-01, GSTR-3B) with hyphen intact
    - Adds underscore-joined bigrams for critical GST compound phrases
    - Falls back to standard word tokenization for everything else
    """
    text_lower = text.lower()
    tokens = list(re.findall(r'\b\w+\b', text_lower))

    # Preserve section/rule number references as compound tokens
    # e.g. "section 16(2)(b)" → "section_16_2_b"
    for m in re.finditer(
        r'\b(section|rule|schedule|article|clause|sub-section|proviso)\s+(\d+(?:[(\w)]+)*)',
        text_lower
    ):
        compound = re.sub(r'[^a-z0-9]', '_', m.group(0))
        tokens.append(compound)

    # Keep form/notification codes with hyphens as single tokens
    # e.g. "DRC-01", "GSTR-3B", "RFD-01"
    for m in re.finditer(r'\b[a-z]{2,5}-[\w\d]+\b', text_lower):
        tokens.append(m.group(0))

    # Circular/notification number references as compound tokens
    # e.g. "Circular No. 183" → "circular_no_183", "cir-183-15" → "circular_183"
    for m in re.finditer(
        r'\b(?:circular|cir)[-_.\s]*(?:no\.?[-_.\s]*)?(\d{2,3})\b',
        text_lower
    ):
        tokens.append(f"circular_{m.group(1)}")

    # Add bigram tokens for GST compound phrases
    for phrase in _GST_BIGRAMS:
        if phrase in text_lower:
            tokens.append(phrase.replace(' ', '_'))

    return tokens


def _mmr_deduplicate(results, top_k: int, lambda_param: float = MMR_LAMBDA):
    """
    Maximal Marginal Relevance (MMR) deduplication.

    Prevents the top-k being dominated by near-duplicate chunks from the
    same document/paragraph.  Uses token-overlap (Jaccard) as a cheap
    proxy for similarity — avoids a second round of vector encoding.

    lambda_param: 1.0 = pure relevance, 0.0 = pure diversity.
    """
    if not results:
        return results

    selected = []
    remaining = list(results)

    max_score = max(r.get("_final_legal_score", 0) for r in remaining) or 1.0

    def jaccard(a: str, b: str) -> float:
        set_a = set(a.lower().split())
        set_b = set(b.lower().split())
        if not set_a or not set_b:
            return 0.0
        return len(set_a & set_b) / len(set_a | set_b)

    while remaining and len(selected) < top_k:
        best_item = None
        best_mmr = -1.0

        for candidate in remaining:
            relevance = candidate.get("_final_legal_score", 0) / max_score

            if selected:
                max_sim = max(
                    jaccard(candidate.get("text", ""), s.get("text", ""))
                    for s in selected
                )
            else:
                max_sim = 0.0

            mmr_score = lambda_param * relevance - (1 - lambda_param) * max_sim

            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best_item = candidate

        if best_item:
            selected.append(best_item)
            remaining.remove(best_item)

    return selected


class Retriever:
    def __init__(self, index_path: Path, chunks_path: Path):
        self.index_path = index_path
        self.chunks_path = chunks_path
        self.chunks = []
        self.metadata = []
        self.index = None
        self.bm25 = None

        if not index_path.exists():
            logger.error(f"FAISS index not found at {index_path} — search will return empty results")
            return

        # Load FAISS index
        logger.info("Loading FAISS index...")
        self.index = faiss.read_index(str(index_path))
        logger.info(f"FAISS index loaded: {self.index.ntotal} vectors, dim={self.index.d}")

        # Merge sidecar index if it exists (produced by incremental ingest scripts)
        sidecar_path = index_path.parent / "index_sidecar.faiss"
        if sidecar_path.exists():
            try:
                sidecar = faiss.read_index(str(sidecar_path))
                if sidecar.d == self.index.d and sidecar.ntotal > 0:
                    # Merge: extract all vectors from sidecar and add to main index
                    all_vecs = faiss.rev_swig_ptr(sidecar.get_xb(), sidecar.ntotal * sidecar.d)
                    import numpy as _np
                    all_vecs = _np.array(all_vecs).reshape(sidecar.ntotal, sidecar.d).astype('float32')
                    self.index.add(all_vecs)
                    # Persist merged index and remove sidecar
                    faiss.write_index(self.index, str(index_path))
                    sidecar_path.unlink()
                    logger.info(f"Sidecar merged: +{sidecar.ntotal} vectors → main index now {self.index.ntotal}")
            except Exception as e:
                logger.warning(f"Sidecar merge failed (non-fatal): {e}")

        # Validate dimension
        if self.index.d != VECTOR_DIM:
            logger.error(f"FAISS dimension mismatch: index has {self.index.d}, config expects {VECTOR_DIM}")

        # Load Chunks and Metadata
        logger.info("Loading chunks & building BM25 index...")
        tokenized_corpus = []
        try:
            with open(chunks_path, "r", encoding="utf-8") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        chunk = json.loads(line)
                        self.chunks.append(chunk)
                        self.metadata.append(chunk.get("metadata", {}))
                        tokenized_corpus.append(tokenize_text(chunk.get("text", "")))
                    except json.JSONDecodeError:
                        logger.warning(f"Malformed JSON at line {line_num} in chunks.jsonl — skipped")
        except FileNotFoundError:
            logger.error(f"Chunks file not found: {chunks_path}")
            return

        # Validate FAISS-chunk alignment
        if self.index.ntotal != len(self.chunks):
            logger.warning(
                f"FAISS/chunk count mismatch: {self.index.ntotal} vectors vs {len(self.chunks)} chunks — "
                "rebuild the index to fix"
            )

        # Initialize BM25
        self.bm25 = BM25Okapi(tokenized_corpus)
        logger.info(f"BM25 index built: {len(tokenized_corpus)} documents")

        # Backfill missing year metadata from path — checks both subfolder structure
        # (Circulars/circulars/2022/file.pdf) and filename (cir-252-09-2025-cgst.pdf).
        # The reranker's _year_recency() reads this field — without it every circular
        # and notification gets the "unknown year" score of 0.55 regardless of actual age.
        _year_dir_re  = re.compile(r'[/\\](\d{4})[/\\]')       # year as directory component
        _year_fname_re = re.compile(r'[-_](\d{4})[-_.]')        # year embedded in filename
        _year_patched = 0
        for _chunk in self.chunks:
            _meta = _chunk.get("metadata", {})
            if not (_meta.get("year") or _chunk.get("year")):
                _rel_path = _chunk.get("rel_path") or _meta.get("rel_path", "")
                _ym = _year_dir_re.search(_rel_path) or _year_fname_re.search(_rel_path)
                if _ym:
                    _yr = int(_ym.group(1))
                    if 2010 <= _yr <= 2030:
                        _chunk["year"] = _yr
                        _meta["year"] = _yr
                        _year_patched += 1
        logger.info(f"Year backfill: patched {_year_patched} chunks from path/filename")

        # Build provision index for O(1) direct section/rule lookup.
        # Maps citation key (e.g. "CGST_SEC_16") → list of chunk indices.
        # Built once at startup; each query with explicit citations does a
        # dict lookup instead of a linear scan over all chunks.
        self._provision_index: dict = {}
        for _ci, _chunk in enumerate(self.chunks):
            _meta = _chunk.get("metadata", {})
            for _ref in set(_meta.get("provisions", []) + _meta.get("citations", [])):
                # Skip generic "ACT" citation — matches everything, not useful
                if _ref and _ref not in ("ACT", "RULES", "NOTIFICATION"):
                    if _ref not in self._provision_index:
                        self._provision_index[_ref] = []
                    self._provision_index[_ref].append(_ci)
        logger.info(f"Provision index built: {len(self._provision_index)} citation keys")

        # Build circular number index for O(1) direct circular lookup.
        # Maps "CIRCULAR_183" → list of chunk indices from circular filenames.
        # Covers patterns: Circular-No-183, cir-183, circular-cgst-183, circularno-183.
        self._circular_index: dict = {}
        _cir_num_re = re.compile(
            # Handles: "Circular No. 183", "cir-252", "Cir251" (no sep), "circularno-183"
            r'(?:circular[s]?[-_.\s]*(?:[a-z]*[-_.\s]*)?(?:no[-_.\s]*)?'
            r'|cir[-_.](?:cgst[-_.])?'   # cir-252, cir_cgst_183
            r'|cir(?=[0-9])'              # Cir251 — no separator before digits
            r'|circularno[-_.])'
            r'(\d{2,3})',
            re.IGNORECASE,
        )
        _cir_leading_re = re.compile(r'^(\d{2,3})[-_]\d+[-_]\d{4}', re.IGNORECASE)
        for _ci, _chunk in enumerate(self.chunks):
            _meta = _chunk.get("metadata", {})
            _cat = (_meta.get("category") or "").lower()
            _dtype = (_meta.get("document_type") or "").lower()
            _rel = _chunk.get("rel_path") or _meta.get("rel_path", "")
            # Also check rel_path: 1,541 circular-file chunks were tagged document_type="Statute"
            # (because the chunker classified the quoted statutory text, not the container doc).
            if "circular" not in _cat and "circular" not in _dtype and "circular" not in _rel.lower():
                continue
            _fname = _rel.split("/")[-1].split("\\")[-1] if _rel else ""
            _m = _cir_num_re.search(_fname) or _cir_leading_re.match(_fname)
            if _m:
                _key = f"CIRCULAR_{_m.group(1)}"
                if _key not in self._circular_index:
                    self._circular_index[_key] = []
                if _ci not in self._circular_index[_key]:
                    self._circular_index[_key].append(_ci)
        logger.info(f"Circular index built: {len(self._circular_index)} circular numbers indexed")

        # Build full-corpus document map for context window expansion.
        # Maps rel_path → sorted list of (page_num, chunk_index).
        # Built once at startup so every query can fetch neighbors from the
        # entire corpus by index, not just from the 80-chunk retrieval pool.
        self._doc_map: dict = {}
        for _ci, _chunk in enumerate(self.chunks):
            _meta = _chunk.get("metadata", {})
            _rel = _chunk.get("rel_path") or _meta.get("rel_path", "")
            if not _rel:
                continue
            _pages = _chunk.get("pages") or _meta.get("pages") or []
            _page = min(_pages) if _pages else (
                _chunk.get("page") or _meta.get("page") or 0
            )
            if _rel not in self._doc_map:
                self._doc_map[_rel] = []
            self._doc_map[_rel].append((_page, _ci))
        for _rel in self._doc_map:
            self._doc_map[_rel].sort(key=lambda x: x[0])
        logger.info(
            f"Doc map built: {len(self._doc_map)} documents, "
            f"{len(self.chunks)} total chunks"
        )

        # 2-stage cascade reranker:
        #   Stage 1 — FlashRank ms-marco (22 MB ONNX, ~0.3s): 80 candidates → top 30
        #   Stage 2 — BGE reranker v2-m3 (570 MB fp16, ~1.5s on top-30): final ranking
        # Total reranking: ~2s vs 8s (BGE alone on 80) or 0.3s (FlashRank alone).
        # Quality gain: BGE was trained on dense legal/multilingual corpora, ms-marco
        # on general web search — the cascade gets speed from stage-1, precision from stage-2.
        logger.info("Loading 2-stage cascade reranker...")
        try:
            self.flash_ranker = FlashRanker(
                model_name="ms-marco-MiniLM-L-12-v2",
                cache_dir=".flashrank_cache",
            )
            logger.info("  Stage 1: FlashRank ms-marco loaded")
        except Exception as e:
            logger.error(f"Failed to load FlashRank (stage 1): {e}", exc_info=True)
            self.flash_ranker = None
        try:
            self.ranker = FlagReranker(RERANKING_MODEL, use_fp16=True)
            logger.info("  Stage 2: BGE reranker v2-m3 loaded")
        except Exception as e:
            logger.error(f"Failed to load BGE reranker (stage 2): {e}", exc_info=True)
            self.ranker = None

        # Initialize Layer 1 (Statute-First)
        self.statute_retriever = StatuteRetriever()

        # Initialize Provision Graph
        graph_path = Path(chunks_path).parent.parent / "graph" / "edges.jsonl"
        self.graph_retriever = ProvisionGraphRetriever(graph_path)

        logger.info("Retriever initialized: 3-Layer Architecture + Provision Graph + MMR")

    def _cascade_rerank(self, query: str, candidates: list,
                        stage1_keep: int = 30) -> list:
        """
        2-stage cascade reranker.

        Stage 1 — FlashRank (fast ONNX, ~0.3s):
          Scores all `candidates` and keeps the top `stage1_keep`.
        Stage 2 — BGE reranker v2-m3 (high quality, ~1.5s on 30 pairs):
          Precisely scores the stage-1 survivors and returns them sorted.

        Falls back gracefully: if stage 2 unavailable → stage 1 only.
        If stage 1 also unavailable → returns candidates unsorted.
        """
        pool = list(candidates)

        # ── Stage 1: FlashRank ────────────────────────────────────────────────
        if self.flash_ranker and pool:
            try:
                passages = [
                    {"id": i, "text": (c.get("context_text") or c.get("text", ""))[:2048],
                     "meta": c}
                    for i, c in enumerate(pool)
                ]
                flash_out = self.flash_ranker.rerank(RerankRequest(query=query, passages=passages))
                for r in flash_out:
                    r["meta"]["_rerank_score"] = r["score"]
                pool = [r["meta"] for r in flash_out]
                pool = pool[:stage1_keep]           # keep only top-N for stage 2
                logger.debug(f"Stage-1 FlashRank: {len(candidates)} → {len(pool)}")
            except Exception as e:
                logger.warning(f"FlashRank stage-1 failed: {e}")

        # ── Stage 2: BGE reranker ─────────────────────────────────────────────
        if self.ranker and pool:
            try:
                texts = [(c.get("context_text") or c.get("text", ""))[:2048] for c in pool]
                pairs = [[query, t] for t in texts]
                scores = self.ranker.compute_score(pairs, normalize=True)
                if not isinstance(scores, list):
                    scores = [scores]
                for chunk, score in zip(pool, scores):
                    chunk["_rerank_score"] = float(score)
                pool = sorted(pool, key=lambda x: x.get("_rerank_score", 0), reverse=True)
                logger.debug(f"Stage-2 BGE: scored {len(pool)} survivors")
            except Exception as e:
                logger.warning(f"BGE stage-2 failed: {e}")

        return pool

    def _enforce_pool_quotas(self, pool: list, query: str, quotas: dict) -> list:
        """
        Guarantee minimum chunks from each document category — BUT ONLY from
        chunks that actually score above the BM25 relevance threshold.

        Statutes (Acts/Rules) get an unconditional floor because they are
        the legal foundation for every GST answer.  Circulars/notifications
        only fill the quota if the BM25 cross-encoder agrees they are
        topically relevant — this prevents irrelevant circulars being forced
        into a pure statutory answer (e.g. "define supply") and displacing
        better-ranked Acts chunks from the 80-candidate reranker window.

        min_bm25_by_cat: per-category BM25 score floor.
          statute / case_law = 0.0  (always include to ensure legal foundation)
          circular / notification = 1.5 (only add if there is real keyword overlap)
        """
        MIN_BM25 = {"statute": 0.0, "case_law": 0.0, "circular": 1.5, "notification": 1.5}

        by_cat = {"statute": [], "case_law": [], "circular": [], "notification": [], "other": []}
        for chunk in pool:
            by_cat[_chunk_category(chunk)].append(chunk)

        seen_ids = {c.get("chunk_id") for c in pool}
        result = list(pool)  # start with the full pool

        if self.bm25:
            tokenized_query = tokenize_text(_expand_for_bm25(query))
            bm25_scores = self.bm25.get_scores(tokenized_query)

            for cat, quota in quotas.items():
                have = len(by_cat[cat])
                if have >= quota:
                    continue  # already enough — no action needed

                needed = quota - have
                min_score = MIN_BM25.get(cat, 0.0)

                # Build sorted list of (chunk_index, score) for this category,
                # filtered by the per-category BM25 floor.
                cat_indices = [
                    (i, bm25_scores[i])
                    for i, c in enumerate(self.chunks)
                    if _chunk_category(c) == cat and bm25_scores[i] >= min_score
                ]
                cat_indices.sort(key=lambda x: x[1], reverse=True)

                added = 0
                for idx, score in cat_indices:
                    if added >= needed:
                        break
                    chunk = self.chunks[idx].copy()
                    cid = chunk.get("chunk_id")
                    if cid and cid not in seen_ids:
                        chunk["_targeted_fill"] = True
                        chunk["_fill_category"] = cat
                        result.append(chunk)
                        seen_ids.add(cid)
                        added += 1

                if added:
                    logger.info(
                        f"Pool quota fill: +{added} {cat} chunks "
                        f"(had {have}, needed {quota}, min_bm25={min_score})"
                    )
                elif have < quota:
                    logger.debug(
                        f"Pool quota fill: no relevant {cat} chunks above "
                        f"BM25={min_score} — query may not need {cat} documents"
                    )

        return result

    def _direct_ref_lookup(self, refs: list) -> list:
        """
        Returns chunks that explicitly cite any of the given provision keys,
        using the pre-built provision index for O(1) lookup per key.
        CIRCULAR_N keys are resolved via _circular_index (filename-based).
        These chunks are pinned at the top of combined_results with
        _statute_priority=1.0 so they survive FlashRank and LegalReranker.
        Capped at 20 to avoid flooding the reranker with pinned chunks.
        """
        if not refs or not hasattr(self, "_provision_index"):
            return []
        seen_ids: set = set()
        pinned = []

        def _pin(idx: int) -> bool:
            if idx >= len(self.chunks):
                return False
            chunk = self.chunks[idx]
            cid = chunk.get("chunk_id")
            if cid and cid not in seen_ids:
                c = chunk.copy()
                c["_pinned_by_ref"] = True
                c["_statute_priority"] = 1.0
                pinned.append(c)
                seen_ids.add(cid)
                return True
            return False

        for ref in refs:
            # Statutory provisions (CGST_SEC_16, CGST_RUL_89, etc.)
            for idx in self._provision_index.get(ref, []):
                _pin(idx)
                if len(pinned) >= 20:
                    return pinned
            # Circular number keys (CIRCULAR_183) — resolved from filename-based index
            if ref.startswith("CIRCULAR_") and hasattr(self, "_circular_index"):
                for idx in self._circular_index.get(ref, []):
                    _pin(idx)
                    if len(pinned) >= 20:
                        return pinned
        return pinned

    def search(self, query: str, top_k: int = 50, allowed_sources=None, advanced_queries=None, domain_paths=None, is_draft: bool = False, skip_rerank: bool = False):
        if not query or not query.strip():
            logger.warning("search() called with empty query")
            return []

        if not self.index or not self.bm25:
            logger.warning("search() called but retriever is not initialized (missing index/bm25)")
            return []

        # --- 1. Query Topic & Subtopic (from pre-computed advanced_queries, no extra LLM call) ---
        topic = "General"
        subtopic = None
        if advanced_queries:
            topic = advanced_queries.get("topic", "General")
            subtopic = advanced_queries.get("subtopic")

        # --- Direct section/rule reference lookup (pinned, bypasses FAISS ranking) ---
        # Extracts explicit citations from query (e.g. "Section 16 CGST") and pins
        # matching chunks at priority 1.0 so they always reach the top of the pool.
        _query_refs = _extract_query_refs(query)
        _pinned = self._direct_ref_lookup(_query_refs) if _query_refs else []
        if _pinned:
            logger.info(f"Direct ref lookup: {_query_refs} → {len(_pinned)} pinned chunks")

        # --- Layer 1: Statute-First Retrieval (Deterministic) ---
        statute_results = self.statute_retriever.search_statutes(self.chunks, topic, subtopic)

        # --- Provision Graph Expansion ---
        graph_results = []
        if statute_results:
            matched_provisions = []
            for res in statute_results:
                matched_provisions.extend(res.get("_matched_provisions", []))

            if matched_provisions:
                graph_results = self.graph_retriever.expand_results(self.chunks, matched_provisions)
                for res in graph_results:
                    res["_is_graph_expanded"] = True
                    res["_statute_priority"] = 0.8

        # --- Layer 2: Broad Semantic Retrieval (Vector + BM25) ---
        candidate_pool = []
        seen_chunk_ids = set()

        def _add_to_pool(idx):
            """Add chunk by index if not already in pool and index is valid."""
            if 0 <= idx < len(self.chunks):
                cid = self.chunks[idx].get("chunk_id")
                if cid and cid not in seen_chunk_ids:
                    seen_chunk_ids.add(cid)
                    candidate_pool.append(self.chunks[idx].copy())

        # 1. Vector Search — primary query
        query_vec = embed_query(query)
        if self.index and query_vec is not None:
            D, I = self.index.search(np.array([query_vec]).astype('float32'), VECTOR_SEARCH_TOP_K)
            for idx in I[0]:
                _add_to_pool(idx)

        # 1b. Vector Search — expanded queries + HyDE document
        if advanced_queries and self.index:
            extra_queries = advanced_queries.get("queries", [])[1:]
            hyde_doc = advanced_queries.get("hyde_document", "")
            if hyde_doc:
                extra_queries.append(hyde_doc)

            for eq in extra_queries:
                if not eq or not eq.strip():
                    continue
                eq_vec = embed_query(eq)
                if eq_vec is not None:
                    D2, I2 = self.index.search(np.array([eq_vec]).astype('float32'), VECTOR_EXPANDED_TOP_K)
                    for idx in I2[0]:
                        _add_to_pool(idx)

        # 2. BM25 Search — expand abbreviations before tokenizing so "ITC" matches
        # chunks that say "Input Tax Credit", "sec 16" matches "Section 16", etc.
        if self.bm25:
            tokenized_query = tokenize_text(_expand_for_bm25(query))
            bm25_scores = self.bm25.get_scores(tokenized_query)
            top_bm25_idxs = np.argsort(bm25_scores)[::-1][:BM25_TOP_K]
            for idx in top_bm25_idxs:
                _add_to_pool(idx)

        # Filter by allowed_sources (file extension)
        if allowed_sources:
            candidate_pool = [
                c for c in candidate_pool
                if any(src.lower() in c.get("rel_path", c.get("metadata", {}).get("rel_path", "")).lower()
                       for src in allowed_sources)
            ]

        # Filter by domain_paths (RAG_INFORMATION_DATABASE sub-folder names).
        # Only applied when the router detected a specific domain; empty = no filter.
        if domain_paths:
            full_path_key = "source"
            filtered = [
                c for c in candidate_pool
                if any(
                    dp.lower() in c.get(full_path_key, "").lower()
                    or dp.lower() in c.get("rel_path", c.get("metadata", {}).get("rel_path", "")).lower()
                    for dp in domain_paths
                )
            ]
            # Only apply the domain filter when it keeps a meaningful subset;
            # fall back to the unfiltered pool if the filter is too aggressive.
            if len(filtered) >= max(3, top_k // 3):
                candidate_pool = filtered
            else:
                logger.debug(
                    f"domain_paths filter too aggressive ({len(filtered)} results) — skipping"
                )

        # ── Phase 2A: Enforce pool quotas — guarantee representation from all source types ──
        # Statutes always get a floor (Acts/Rules are the foundation of every GST answer).
        # Circulars/notifications only fill in when BM25 confirms topical relevance (see
        # _enforce_pool_quotas min_bm25 threshold) — prevents irrelevant circulars being
        # forced into a pure statutory answer and displacing better-ranked Acts chunks.
        _quotas = (
            {"statute": 10, "case_law": 8, "circular": 4, "notification": 3}
            if is_draft else
            {"statute": 6,  "case_law": 4, "circular": 4, "notification": 3}
        )
        candidate_pool = self._enforce_pool_quotas(candidate_pool, query, _quotas)

        # Merge layers: Pinned > Statute-First > Graph > Semantic pool (including any fills).
        # Fills now compete on merit via FlashRank+LegalReranker instead of being force-promoted.
        combined_results = _pinned + statute_results[:40] + graph_results[:20]
        existing_ids = {r.get("chunk_id") for r in combined_results}
        for r in candidate_pool:
            if r.get("chunk_id") not in existing_ids:
                combined_results.append(r)
                existing_ids.add(r.get("chunk_id"))

        # Cap total candidates for reranker (FlashRank OOM above ~300)
        RERANK_MAX = 80
        reranker_input = combined_results[:RERANK_MAX]

        # --- Semantic Reranking (FlashRank) ---
        # skip_rerank=True bypasses the cross-encoder to stay within API Gateway's 29s timeout
        reranked_results = reranker_input
        if reranker_input and not skip_rerank:
            reranked_results = self._cascade_rerank(query, reranker_input)
            if reranked_results:
                logger.info(
                    f"Cascade rerank: {len(reranker_input)} → {len(reranked_results)} | "
                    f"top_score={reranked_results[0].get('_rerank_score', 0):.3f}"
                )

        # --- Layer 3: Legal Reranking (Composite Scoring) ---
        reranked_results = LegalReranker.rerank(query, reranked_results, query_topic=topic, is_draft=is_draft)

        # --- Layer 4: MMR Deduplication ---
        reranked_results = _mmr_deduplicate(reranked_results, top_k=top_k)

        # --- Context Window Expansion ---
        # Enrich each selected chunk with adjacent-page neighbors from the full
        # corpus (self._doc_map covers all chunks, not just the 80-chunk pool).
        reranked_results = _expand_context_window(reranked_results, self._doc_map, self.chunks)

        # Flatten metadata for final output (safe merge avoiding key collisions)
        final_results = []
        for res in reranked_results:
            if "metadata" in res:
                meta = res.pop("metadata")
                for key, val in meta.items():
                    if key not in res:  # don't overwrite existing keys
                        res[key] = val
            final_results.append(res)

        logger.debug(
            f"search() complete: query='{query[:60]}' | "
            f"statute={len(statute_results)} graph={len(graph_results)} "
            f"semantic={len(candidate_pool)} final={len(final_results)}"
        )
        return final_results[:top_k]

    def supplement_and_rerank(self, base_chunks: list, advanced_queries: dict, query: str, top_k: int) -> list:
        """
        Called after fast retrieval (skip_rerank=True) + query expansion finish in parallel.
        Supplements the fast pool with FAISS results from expanded queries, then runs ONE
        FlashRank + LegalReranker + MMR pass on the merged pool capped at 80 chunks.
        This replaces the old pattern of running FlashRank on 200 chunks twice.
        """
        if not advanced_queries:
            return base_chunks[:top_k]

        topic = advanced_queries.get("topic", "General")

        # Direct ref lookup: pin explicitly-cited sections at top of pool
        _query_refs = _extract_query_refs(query)
        _pinned = self._direct_ref_lookup(_query_refs) if _query_refs else []

        existing_ids = {c.get("chunk_id") for c in base_chunks}
        for c in _pinned:
            existing_ids.add(c.get("chunk_id"))

        extra_queries = list(advanced_queries.get("queries", [])[1:])
        hyde = advanced_queries.get("hyde_document", "")
        if hyde:
            extra_queries.append(hyde)

        combined = _pinned + list(base_chunks)
        if self.index:
            for eq in extra_queries:
                if not eq or not eq.strip():
                    continue
                vec = embed_query(eq)
                if vec is not None:
                    D, I = self.index.search(np.array([vec]).astype('float32'), VECTOR_EXPANDED_TOP_K)
                    for idx in I[0]:
                        if 0 <= idx < len(self.chunks):
                            chunk = self.chunks[idx].copy()
                            cid = chunk.get("chunk_id")
                            if cid and cid not in existing_ids:
                                existing_ids.add(cid)
                                combined.append(chunk)

        # Enforce category quotas — circulars/notifications only fill in when BM25
        # confirms topical relevance; statutes always get their floor.
        _sr_quotas = {"statute": 6, "case_law": 4, "circular": 4, "notification": 3}
        combined = self._enforce_pool_quotas(combined, query, _sr_quotas)
        # No priority-front promotion — fills compete on merit via FlashRank + LegalReranker.

        RERANK_CAP = 80
        rerank_input = combined[:RERANK_CAP]
        reranked = rerank_input

        if rerank_input:
            reranked = self._cascade_rerank(query, rerank_input)

        reranked = LegalReranker.rerank(query, reranked, query_topic=topic, is_draft=False)

        mmr_results = _mmr_deduplicate(reranked, top_k=top_k)

        # Context window expansion using the full-corpus doc map
        mmr_results = _expand_context_window(mmr_results, self._doc_map, self.chunks)

        final = []
        for res in mmr_results:
            if "metadata" in res:
                meta = res.pop("metadata")
                for key, val in meta.items():
                    if key not in res:
                        res[key] = val
            final.append(res)

        logger.info(
            f"supplement_and_rerank: pinned={len(_pinned)} base={len(base_chunks)} "
            f"expanded={len(combined)-len(base_chunks)-len(_pinned)} "
            f"reranked={len(reranked)} final={len(final)}"
        )
        return final
