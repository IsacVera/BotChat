import os
import logging
from typing import List, Tuple

from celery import shared_task
from django.conf import settings
from django.db import connection, transaction
from pypdf import PdfReader

from .models import Document, Chunk
from api.gemini import embed_texts

logger = logging.getLogger(__name__)


def _extract_text_per_page(pdf_path: str) -> List[str]:
    reader = PdfReader(pdf_path)
    pages = []
    for page in reader.pages:
        try:
            txt = page.extract_text() or ""
        except Exception:
            txt = ""
        pages.append(txt)
    return pages


def _normalize_text(text: str) -> str:
    # Light normalize but keep newlines (useful for headings/sections)
    if not text:
        return ""
    text = text.replace("\r", "")
    # Fix common PDF hyphenation at line breaks: "end-\nline" -> "endline"
    text = text.replace("-\n", "")
    # Collapse excessive spaces within lines but preserve line structure
    return "\n".join(" ".join(line.split()) for line in text.split("\n")).strip()

def _detect_repeated_lines(pages: List[str], freq_threshold: float = 0.6) -> set:
    """
    Identify header/footer lines that repeat across many pages and should be removed
    (e.g., restaurant name, page numbers, addresses repeated on every page).
    Only considers lines with 3+ words to avoid removing common English words.
    """
    from collections import Counter
    line_counts = Counter()
    total_pages = max(1, len(pages))
    for p in pages:
        seen = set()
        for line in p.split("\n"):
            s = line.strip()
            if not s:
                continue
            # Skip numeric-only or "Page N" patterns (typical footers/headers)
            if s.isdigit() or (s.lower().startswith("page ") and s[5:].strip().isdigit()):
                continue
            # ONLY consider lines with 3+ words to avoid removing common words
            word_count = len(s.split())
            if word_count < 3:
                continue
            # Count each line once per page to avoid over-weighting multi-occurrence lines
            if s not in seen:
                line_counts[s] += 1
                seen.add(s)
    repeated = {ln for (ln, c) in line_counts.items() if c / total_pages >= freq_threshold}
    return repeated

def _strip_repeated_lines(pages: List[str], repeated: set) -> List[str]:
    cleaned = []
    for p in pages:
        lines = [ln for ln in p.split("\n") if ln.strip()]
        kept = [ln for ln in lines if ln.strip() not in repeated]
        # If we would remove more than 50% of a page's lines, keep the original (fail-safe)
        if lines and len(kept) < 0.5 * len(lines):
            kept = lines
        cleaned.append("\n".join(kept))
    return cleaned

def _guess_page_heading(page_text: str) -> str:
    """
    Heuristic: First non-empty line that looks like a section title:
    - SHORT line (< 90 chars)
    - Title Case or starts with a number/bullet
    Fallback to first non-empty line.
    """
    import re
    for line in page_text.split("\n"):
        s = line.strip()
        if not s:
            continue
        if len(s) <= 90 and (re.match(r"^\d+[\).\s-]+", s) or s.istitle() or s.isupper()):
            return s
    # fallback
    for line in page_text.split("\n"):
        s = line.strip()
        if s:
            return s[:90]
    return "Document"


def _make_chunks(pages: List[str], target_words: int = 700, overlap: int = 120) -> List[Tuple[int, int, str]]:
    """
    Returns list of (page_from, page_to, text)
    - Word-based sliding window with overlap
    - Preserves page ranges correctly
    - Avoids ultra-short tail chunks

    Notes:
    - We intentionally avoid resetting buffer_start_page to the current page when sliding the window.
      That was causing subsequent chunks to report incorrect page_from values (the bug you flagged).
    - Use a light normalization that preserves intra-line structure (newlines) to help retrieval.
    """
    def normalize_keep_structure(t: str) -> str:
        # Use the improved normalizer above
        return _normalize_text(t)

    # Validate overlap and target_words
    assert target_words > 0, "target_words must be > 0"
    overlap = max(0, min(overlap, target_words - 1))

    # Buffer holds (word, page)
    buf: List[Tuple[str, int]] = []
    # Track a heading per page so we can prefix chunks for better retrieval signal
    page_headings: List[str] = []
    chunks: List[Tuple[int, int, str]] = []

    # Flatten all pages into (word, page)
    # 1) Normalize pages
    norm_pages = [normalize_keep_structure(p) for p in pages]
    # 2) Remove headers/footers that repeat across many pages
    repeated = _detect_repeated_lines(norm_pages)
    norm_pages = _strip_repeated_lines(norm_pages, repeated)
    # 3) Pre-compute page headings
    page_headings = [_guess_page_heading(p) for p in norm_pages]

    for pageno, text in enumerate(norm_pages, start=1):
        if not text:
            continue
        for w in text.split():
            buf.append((w, pageno))

    if not buf:
        return []

    i = 0
    n = len(buf)

    def emit(lo: int, hi: int):
        words = [w for (w, _) in buf[lo:hi]]
        pages_in_chunk = [pg for (_, pg) in buf[lo:hi]]
        page_from = min(pages_in_chunk)
        page_to = max(pages_in_chunk)
        body = " ".join(words).strip()
        # Determine heading for this chunk (from first page present)
        heading_prefix = ""
        first_pg = pages_in_chunk[0] - 1 if pages_in_chunk else -1
        if 0 <= first_pg < len(page_headings):
            heading = page_headings[first_pg]
            if heading:
                heading_prefix = f"{heading}\n\n"
                # Avoid duplicating heading at the start of the body (case-insensitive)
                h_lower = heading.lower()
                if body.lower().startswith(h_lower):
                    body = body[len(heading):].lstrip(" :.-\n")
        text = f"{heading_prefix}{body}" if heading_prefix else body
        return (page_from, page_to, text)

    # Sliding window
    min_chunk_words = max(80, target_words // 4)
    chunk_starts = []  # Track where each chunk starts
    
    while i < n:
        remaining = n - i
        # If remaining words are less than minimum and we have chunks, merge into last chunk
        if remaining < min_chunk_words and chunks:
            # Extend the last chunk from where it started to include all remaining words
            last_start = chunk_starts[-1]
            chunks[-1] = emit(last_start, n)
            break
        
        j = min(i + target_words, n)
        chunk_starts.append(i)
        chunks.append(emit(i, j))
        
        if j >= n:
            break
        # Slide forward by (target_words - overlap)
        i += (target_words - overlap)

    return chunks


@shared_task
def ingest_document(document_id: int):
    """Process a Document: parse PDF, chunk, (try to) embed, and mark ready.
    Resilient: if embeddings fail, we still mark the document ready so keyword-only
    retrieval can work. Error details are saved to error_message.
    """
    doc = Document.objects.filter(id=document_id).select_related("company").first()
    if not doc:
        return

    # Update status to processing
    Document.objects.filter(id=document_id).update(status="processing", error_message="")

    try:
        pdf_path = os.path.join(settings.MEDIA_ROOT, doc.storage_path)
        pages = _extract_text_per_page(pdf_path)
        page_count = len(pages)

        # Chunking
        triples = _make_chunks(pages)
        if not triples:
            # No text found; keep as error because chat cannot proceed
            Document.objects.filter(id=document_id).update(status="error", error_message="No text extracted from PDF")
            return
        
        # Log parsed chunks for debugging
        logger.info(f"Document {document_id} parsed into {len(triples)} chunks")
        for idx, (p_from, p_to, text) in enumerate(triples, 1):
            word_count = len(text.split())
            logger.info(f"  Chunk {idx}: pages {p_from}-{p_to}, {word_count} words")
            logger.info(f"    Preview: {text[:200]}...")

        # Create Chunk rows
        chunk_ids: List[int] = []
        with transaction.atomic():
            for (p_from, p_to, text) in triples:
                ch = Chunk.objects.create(
                    company=doc.company,
                    document=doc,
                    page_from=p_from,
                    page_to=p_to,
                    text=text,
                )
                chunk_ids.append(ch.id)

        # Mark ready early so keyword-only retrieval can work while embeddings run
        Document.objects.filter(id=document_id).update(status="ready", page_count=page_count)

        # Try embeddings (non-fatal)
        embed_error = None
        try:
            texts = [t for (_, _, t) in triples]
            vectors = embed_texts(texts)
            # Write to embedding_vec via SQL cast
            with connection.cursor() as cur:
                for cid, vec in zip(chunk_ids, vectors):
                    lit = "[" + ",".join(f"{x:.6f}" for x in vec) + "]"
                    cur.execute("UPDATE core_chunk SET embedding_vec = %s::vector WHERE id = %s", [lit, cid])
        except Exception as e:
            embed_error = str(e)
            # keep going; keyword retrieval will still work

        # Mark ready and set page_count regardless of embedding success
        if embed_error:
            Document.objects.filter(id=document_id).update(status="ready", page_count=page_count, error_message=f"embedding_error: {embed_error}")
        else:
            Document.objects.filter(id=document_id).update(status="ready", page_count=page_count)

    except Exception as e:
        # Save error on any unexpected failure
        Document.objects.filter(id=document_id).update(status="error", error_message=str(e))
        return
