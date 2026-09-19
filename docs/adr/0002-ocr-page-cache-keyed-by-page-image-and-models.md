# The OCR page cache, keyed by page image and the models that read it

OCR remembers each page's finished text in a **page cache**, a port with `get`/`set` (`app/services/page_cache.py`) whose one adapter stores entries in Redis with a TTL. `OCRService` receives one at construction, like its models, and `get_page_cache()` builds it from settings, returning `None` when `OCR_PAGE_CACHE_ENABLED` is off (#7).

The key is a hash of everything that decides the text: the rendered page image, both models, both prompts, and a rules version bumped by hand when OCR's own behaviour (cleanup, thresholds) changes. Nothing stale is served because a changed model or prompt is simply a different key, so no invalidation pass is needed. Identifying a model by `repr()` was rejected: it is not stable across processes for a model without one, which silently defeats the cache. The chat model port instead gained a `model_name` property, matching the embedder port, and a key names the adapter class alongside it, because the same model name at two providers is two different models.

The cache lives in the service layer rather than in `app/providers/`, which ADR 0001 keeps for the two model ports and their adapters. It is a speed-up and never a source of truth, so neither method may raise: the Redis adapter logs every failure and reports it as a miss, and OCR reads the page again.

## Consequences

- Reprocessing a document reuses cached pages, so it costs a lookup per page. A caller wanting the models re-run asks for it explicitly: `refresh_cache` on `extract_text`, threaded through the reprocess task to `?refresh_cache=true` on both reprocess endpoints.
- Only non-empty text is stored, so a page the models found nothing on is tried again rather than remembered as empty.
- Entries are ordinary Redis keys under `cartulary:ocr:page:`, expiring after `OCR_PAGE_CACHE_TTL_SECONDS` (default 30 days). Redis flushed, unreachable or off means slower OCR, never wrong OCR.
- A rules change that should invalidate old entries needs `CACHE_SCHEMA_VERSION` in `ocr_service.py` bumped; forgetting it serves text produced under the old rules until the TTL expires.
