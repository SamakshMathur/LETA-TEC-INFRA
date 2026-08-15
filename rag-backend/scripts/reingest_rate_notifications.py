"""
Targeted re-ingestion of the 4 Rate Notification PDFs.

Problem: current chunks are too coarse (avg 2101 chars, max 40895 chars) — entire
rate-schedule tables are crammed into one chunk, making SAC/HSN-specific queries miss.

Fix: split each rate schedule entry into its own chunk (1-3 entries per chunk),
prefixed with the notification title for context. Re-embed with bge-large-en-v1.5.

Steps:
  1. Drop the 311 Rate Notification entries from chunks.jsonl (lines 61396-61706)
  2. Re-extract the 4 PDFs with pdfplumber (preserves table rows)
  3. Split into entry-level chunks (one SAC/HSN heading per chunk)
  4. Embed with bge-large-en-v1.5
  5. Rebuild FAISS = original vectors (0..61395) + new vectors
  6. Save updated chunks.jsonl + index.faiss
  7. Upload both to S3

Run from: RAG/rag-backend/
    python -X utf8 scripts/reingest_rate_notifications.py
"""
import sys, os, json, re, time, shutil, hashlib
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
DB_ROOT     = Path("RAG_INFORMATION_DATABASE/Notification/Rate notification_2.0")
CHUNKS_FILE = Path("data/chunks/chunks.jsonl")
INDEX_FILE  = Path("vectordb/index.faiss")
S3_BUCKET   = os.getenv("S3_DATA_BUCKET", "gst-rag-data-bucket")

RATE_NOTIF_FILES = {
    "Notification 1_2017_Rate_Goods_08_08_2026.pdf": {
        "short":  "IGST Rate Goods Notification 1/2017",
        "act":    "IGST",
        "cat":    "rate_goods",
        "number": "1/2017-Integrated Tax (Rate)",
    },
    "Notification 2_2017_Rate_Goods_08_08_2026.pdf": {
        "short":  "CGST Exempt Goods Notification 2/2017",
        "act":    "CGST",
        "cat":    "rate_goods_exempt",
        "number": "2/2017-Central Tax (Rate)",
    },
    "Notification 11_2017_Rate_Service_08_08_2026.pdf": {
        "short":  "CGST Rate Schedule Services Notification 11/2017",
        "act":    "CGST",
        "cat":    "rate_services",
        "number": "11/2017-Central Tax (Rate)",
    },
    "Notification 12_2017_Rate_Service_08_08_2026.pdf": {
        "short":  "CGST Exempt Services Notification 12/2017",
        "act":    "CGST",
        "cat":    "rate_services_exempt",
        "number": "12/2017-Central Tax (Rate)",
    },
}

# ── 1. Load all chunks, split off Rate Notification tail ───────────────────────
print("Step 1: Loading existing chunks.jsonl ...")
all_chunks = []
rate_notif_indices = []
with CHUNKS_FILE.open(encoding='utf-8', errors='ignore') as f:
    for i, line in enumerate(f):
        try:
            c = json.loads(line.strip())
            if 'Rate notification_2.0' in c.get('rel_path', ''):
                rate_notif_indices.append(i)
            else:
                all_chunks.append(c)
        except:
            pass

print(f"  Kept   : {len(all_chunks)} non-Rate-Notification chunks")
print(f"  Dropped: {len(rate_notif_indices)} Rate Notification chunks (indices {rate_notif_indices[0]}..{rate_notif_indices[-1]})")

BASE_COUNT = len(all_chunks)   # FAISS vectors 0..BASE_COUNT-1 stay intact

# ── 2. Re-extract PDFs with pdfplumber ────────────────────────────────────────
def extract_pdf_text(pdf_path: Path) -> str:
    """
    Extract text from PDF, preserving table row structure as much as possible.
    Falls back to PyMuPDF if pdfplumber is unavailable.
    """
    try:
        import pdfplumber
        pages = []
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                # Try table extraction first
                tables = page.extract_tables()
                if tables:
                    for table in tables:
                        for row in table:
                            if row:
                                cells = [str(c or '').strip() for c in row]
                                non_empty = [c for c in cells if c]
                                if non_empty:
                                    pages.append(' | '.join(non_empty))
                else:
                    text = page.extract_text() or ''
                    if text.strip():
                        pages.append(text)
        return '\n'.join(pages)
    except ImportError:
        pass

    # PyMuPDF fallback
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        pages = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        return '\n'.join(pages)
    except Exception as e:
        print(f"  ! PDF extraction failed: {e}")
        return ''


# ── 3. Split rate schedule into entry-level chunks ────────────────────────────
# Patterns that mark the start of a new schedule entry:
_ENTRY_PATTERNS = [
    re.compile(r'^\s*(\d{1,3})\s*[|\s]+\s*(Chapter|Section|Heading|Group)\s+(\d[\d\w /]+)', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*Sl\.\s*No\.?\s*(\d+)', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*(\d{1,3})\s*[.)\]]\s+\d{4}', re.MULTILINE),   # "1. 0101 Live..."
    re.compile(r'^\s*\d+[a-z]?\s+Chapter\s+\d+', re.IGNORECASE | re.MULTILINE),
    re.compile(r'^\s*\d+[a-z]?\s+Heading\s+\d+', re.IGNORECASE | re.MULTILINE),
]

# For goods: entries are numbered rows "1. 0101 Live asses..."
_GOODS_ROW = re.compile(
    r'(?m)^(\d+[a-z]?\.?\s+[\d/ ,]+\s+.+?)(?=\n\d+[a-z]?\.?\s+[\d/ ,]+\s+|\Z)',
    re.DOTALL
)

# For services: entries grouped by Heading number
_SERVICE_HEADING = re.compile(
    r'(?m)(?=^\s*\d+\s+(?:Chapter|Section|Heading)\s+\d)',
    re.IGNORECASE
)


def split_rate_schedule(full_text: str, is_goods: bool, notif_info: dict) -> list:
    """
    Split the full rate schedule text into one-entry-per-chunk pieces.
    Each chunk is prefixed with the notification title for context.
    """
    title_prefix = (
        f"[GST Rate Notification] {notif_info['short']} "
        f"(Notification No. {notif_info['number']})\n"
    )

    lines = full_text.split('\n')
    chunks_text = []
    current = []
    MIN_CHARS = 80    # skip junk lines shorter than this
    MAX_CHARS = 800   # split if current buffer exceeds this

    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line:
            continue

        # Detect entry boundary: line starts with a serial number pattern
        is_new_entry = bool(
            re.match(r'^\d{1,3}[a-z]?[\s.)\]]', line) and len(line) > 10
        ) or bool(
            re.match(r'^(?:Chapter|Section|Heading)\s+\d', line, re.IGNORECASE)
        )

        if is_new_entry and current and sum(len(l) for l in current) >= MIN_CHARS:
            # Flush current chunk
            chunk_text = title_prefix + '\n'.join(current)
            if len(chunk_text.strip()) >= MIN_CHARS:
                chunks_text.append(chunk_text.strip())
            current = [line]
        else:
            current.append(line)
            # Also split if buffer gets too big
            if sum(len(l) for l in current) > MAX_CHARS:
                chunk_text = title_prefix + '\n'.join(current)
                if len(chunk_text.strip()) >= MIN_CHARS:
                    chunks_text.append(chunk_text.strip())
                current = []

    # Flush last
    if current and sum(len(l) for l in current) >= MIN_CHARS:
        chunk_text = title_prefix + '\n'.join(current)
        if len(chunk_text.strip()) >= MIN_CHARS:
            chunks_text.append(chunk_text.strip())

    return chunks_text


def make_chunk(text: str, rel_path: str, idx: int, notif_info: dict) -> dict:
    h = hashlib.sha256(text.encode()).hexdigest()[:12]
    chunk_id = f"rate_notif_{notif_info['cat']}_{idx:04d}_{h}"
    return {
        "chunk_id": chunk_id,
        "text":     text,
        "rel_path": rel_path,
        "source":   str(DB_ROOT / rel_path.split('\\')[-1]),
        "metadata": {
            "rel_path":       rel_path,
            "document_type":  "Notification",
            "source_type":    "rate_notification",
            "category":       "notification",
            "act":            notif_info["act"],
            "notification_no": notif_info["number"],
            "topic":          "Rate",
        },
    }


print("\nStep 2: Re-extracting and re-chunking 4 Rate Notification PDFs ...")
new_chunks = []

for filename, info in RATE_NOTIF_FILES.items():
    pdf_path = DB_ROOT / filename
    if not pdf_path.exists():
        print(f"  ! {filename} not found — skipping")
        continue

    rel_path = f"Notification\\Rate notification_2.0\\{filename}"
    print(f"\n  [{info['short']}]")
    print(f"    Extracting: {pdf_path.name} ...", end=' ', flush=True)

    full_text = extract_pdf_text(pdf_path)
    if not full_text.strip():
        print("EMPTY — skipping")
        continue
    print(f"done ({len(full_text):,} chars)")

    is_goods = 'Goods' in filename
    print(f"    Splitting into entries ...", end=' ', flush=True)
    entries = split_rate_schedule(full_text, is_goods=is_goods, notif_info=info)
    print(f"{len(entries)} chunks")

    for idx, entry_text in enumerate(entries):
        new_chunks.append(make_chunk(entry_text, rel_path, idx, info))

    sizes = [len(c['text']) for c in new_chunks[-len(entries):]]
    print(f"    Chunk sizes: avg={sum(sizes)//len(sizes)} | max={max(sizes)} | min={min(sizes)}")

total_new = len(new_chunks)
print(f"\n  New Rate Notification chunks: {total_new} (was 311)")

# ── 4. Embed new chunks with bge-large-en-v1.5 ───────────────────────────────
print("\nStep 3: Embedding new chunks with BAAI/bge-large-en-v1.5 ...")
import numpy as np
from sentence_transformers import SentenceTransformer
import torch
torch.set_num_threads(4)

model = SentenceTransformer("BAAI/bge-large-en-v1.5")
texts = [c['text'] for c in new_chunks]

t0 = time.time()
BATCH = 64
all_vecs = []
for start in range(0, len(texts), BATCH):
    batch = texts[start:start+BATCH]
    vecs = model.encode(batch, normalize_embeddings=True, show_progress_bar=False)
    all_vecs.append(vecs.astype('float32'))
    done = start + len(batch)
    elapsed = time.time() - t0
    rate = done / elapsed if elapsed > 0 else 1
    eta = (len(texts) - done) / rate
    print(f"  [{done}/{len(texts)}] {rate:.0f} chunks/s  ETA {eta:.0f}s", end='\r')

new_vecs = np.vstack(all_vecs)
print(f"\n  Embedded {len(new_vecs)} chunks in {time.time()-t0:.1f}s | shape={new_vecs.shape}")

# ── 5. Rebuild FAISS: keep base vectors + replace tail with new ───────────────
print("\nStep 4: Rebuilding FAISS index ...")
import faiss

print(f"  Loading original index ({INDEX_FILE}) ...", end=' ', flush=True)
orig_idx = faiss.read_index(str(INDEX_FILE))
DIM = orig_idx.d
print(f"done ({orig_idx.ntotal} vectors, dim={DIM})")

# Reconstruct the BASE_COUNT vectors we're keeping
print(f"  Reconstructing {BASE_COUNT} base vectors ...", end=' ', flush=True)
base_vecs = np.empty((BASE_COUNT, DIM), dtype=np.float32)
for i in range(BASE_COUNT):
    orig_idx.reconstruct(i, base_vecs[i])
print("done")

del orig_idx  # free RAM

# Build new index
new_idx = faiss.IndexFlatIP(DIM)
print(f"  Adding {BASE_COUNT} base vectors ...", end=' ', flush=True)
new_idx.add(base_vecs)
del base_vecs
print("done")

print(f"  Adding {len(new_vecs)} new Rate Notification vectors ...", end=' ', flush=True)
new_idx.add(new_vecs)
print("done")

print(f"  Total vectors in new index: {new_idx.ntotal}")
assert new_idx.ntotal == BASE_COUNT + total_new, "Vector count mismatch!"

# Backup old index
backup = INDEX_FILE.with_suffix('.faiss.pre_rate_notif.bak')
shutil.copy2(str(INDEX_FILE), str(backup))
print(f"  Old index backed up → {backup.name}")

faiss.write_index(new_idx, str(INDEX_FILE))
print(f"  New index written → {INDEX_FILE} ({INDEX_FILE.stat().st_size/1e6:.1f} MB)")

# ── 6. Write updated chunks.jsonl ─────────────────────────────────────────────
print("\nStep 5: Writing updated chunks.jsonl ...")
final_chunks = all_chunks + new_chunks   # base + new Rate Notif

backup_chunks = CHUNKS_FILE.with_suffix('.jsonl.pre_rate_notif.bak')
shutil.copy2(str(CHUNKS_FILE), str(backup_chunks))
print(f"  Old chunks.jsonl backed up → {backup_chunks.name}")

with CHUNKS_FILE.open('w', encoding='utf-8') as f:
    for c in final_chunks:
        f.write(json.dumps(c, ensure_ascii=False) + '\n')

print(f"  Written {len(final_chunks)} chunks → {CHUNKS_FILE}")
print(f"  Final alignment: {new_idx.ntotal} FAISS vectors == {len(final_chunks)} chunks : {'✅ PERFECT' if new_idx.ntotal == len(final_chunks) else '❌ MISMATCH'}")

# ── 7. Upload to S3 ───────────────────────────────────────────────────────────
print(f"\nStep 6: Uploading to S3 bucket: {S3_BUCKET} ...")
try:
    import boto3
    s3 = boto3.client('s3')

    # Upload FAISS index
    print("  Uploading vectordb/index.faiss ...", end=' ', flush=True)
    t0 = time.time()
    s3.upload_file(str(INDEX_FILE), S3_BUCKET, 'vectordb/index.faiss')
    print(f"done ({time.time()-t0:.1f}s)")

    # Upload chunks.jsonl
    print("  Uploading data/chunks/chunks.jsonl ...", end=' ', flush=True)
    t0 = time.time()
    s3.upload_file(str(CHUNKS_FILE), S3_BUCKET, 'data/chunks/chunks.jsonl')
    print(f"done ({time.time()-t0:.1f}s)")

    print("\n✅ S3 upload complete.")
except Exception as e:
    print(f"\n  ⚠ S3 upload failed: {e}")
    print("  Manually upload:")
    print(f"    aws s3 cp vectordb/index.faiss s3://{S3_BUCKET}/vectordb/index.faiss")
    print(f"    aws s3 cp data/chunks/chunks.jsonl s3://{S3_BUCKET}/data/chunks/chunks.jsonl")

print("\n" + "="*60)
print("DONE. Next: restart ECS tasks to load new index.")
print("  aws ecs update-service --cluster gst-rag-cluster --service gst-rag-service --force-new-deployment")
print("="*60)
