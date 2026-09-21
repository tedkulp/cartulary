# A model failure is retried; everything else is terminal

A stage that raises `ModelError` is run again, up to three times, waiting 10s, 60s and then
300s. Every other exception leaves the Document `failed` with `processing_error` set, exactly
as before. Which of the two a failure is, is `worth_retrying()` in
`app/processing/retry.py`, and it is the type and nothing else: `ModelError` is how every
adapter reports a provider failure — an unreachable host, a rate limit, a read that went
quiet for `MODEL_TIMEOUT_SECONDS` (ADR 0001) — and much of that class comes out differently a
minute later. A missing file, a bad row and a programming error do not.

The one carve-out is `ModelConfigurationError`, a subclass of `ModelError` raised by the
adapters for a fault this deployment is configured into: no `OPENAI_API_KEY`, no SDK
installed, a model asked for images it cannot take. It stays a `ModelError`, so every caller
that already handles one handles it, but it reads exactly the same on the fourth attempt as
on the first. Retrying it would delay the operator's answer by six minutes on every document
and tell them nothing new.

Before this, every stage failure was terminal, and the configuration that was supposed to
prevent that had never once fired: all three tasks carried `autoretry_for=(Exception,)` while
catching every exception and returning a dict, so Celery never saw a failure to retry. #37
removed it rather than repairing it, because repairing it would have retried a bad row as
eagerly as a restarting model server. This is the repair, narrowed to the failures worth
repeating.

## Where the decision lives

The runner catches the exception and owns the error write, and it deliberately imports no
Celery — but running a task again is `self.retry`, which only Celery has. So the runner asks
the policy whether this failure is worth retrying and how long to wait, and then calls a
`retry` callable the caller passed in, which raises. Under Celery that callable is two lines
in `app/tasks/document_tasks.py`; in a test it is a function that raises something the test
can catch, which is why the retry path runs with no broker. With no `retry` callable at all,
every failure is terminal, so the runner alone never retries anything.

The alternative — the runner returning "worth retrying" in its result dict for the task
adapter to inspect — was rejected. It makes the adapter re-decide what the runner already
knows, and a task that forgot to look would silently stop retrying. `app/processing/stages.py`
stays pure either way; `retry.py` is pure too, and is tested with no fixtures.

Celery is told `max_retries=len(RETRY_DELAYS)` at that seam rather than left on its default of
3, so a longer schedule can never be cut short by a number written somewhere else.

`RETRY_DELAYS` is a constant and not a setting. `retry.py` is pure for the same reason
`stages.py` is — it opens nothing and reads nothing — and an operator turning a dial here
changes how long a Document sits looking as though it is being worked on, which is a decision
about the machine rather than about this deployment. `.env` stays for what genuinely differs
between installations: which models, which provider, which dimension.

## What a Document reads while a retry is pending

Nothing is written. The Document keeps the status it already had — `processing` for a read,
`ocr_complete` or `embedding_complete` for the stages after it — no status event is emitted,
`processing_error` is untouched, and the transaction is rolled back before the retry is
raised. Only an exhausted schedule takes the existing failure path and writes `failed`.

An eighth status, `retrying`, was considered and rejected: it would need a migration's worth
of coordination through `packages/shared` to both clients for a state a Document is in for
six minutes at the outside, and the status it would replace is not wrong. A retry that is
still in flight is not a failure. Writing `failed` and then quietly succeeding on the third
attempt is a status event that lies twice, which is the thing this ADR exists to prevent.

The cost is that a Document waiting on a retry is indistinguishable from one being worked on,
which is exactly what it is. The worker log says which, and after at most 370 seconds the row
says so too.

## The queue is the only record of a pending retry

Writing nothing has a cost: between attempts, the Celery message is the sole evidence that
work is outstanding. Celery acks on receipt by default, and a `countdown` retry is held in the
receiving worker's in-memory timer, so a worker restarted during a 300-second wait would take
the last record of that Document with it, leaving it at `processing` for ever — a state that
was unreachable before this ADR, because every failure used to write `failed` synchronously.

So `task_acks_late` and `task_reject_on_worker_lost` are on. A message is acked after the work
rather than on receipt, and a worker that dies mid-wait returns it to the broker. The price is
that a stage can be redelivered and run twice, which every stage tolerates: each writes once,
at the end, in one transaction, and OCR's page cache makes the second read of a page already
read a lookup. `max(RETRY_DELAYS)` plus `task_time_limit` stays under the broker's visibility
timeout, so nothing is redelivered while it is still legitimately waiting; a test pins that.

## Which failures reach the runner at all

A retry is only worth having if a `ModelError` can escape a stage, and two of the three
stages used to catch every one of them:

- **OCR** caught `ModelError` per page and fell back to that page's embedded text, so an
  unreachable model server produced `ocr_failed` with "No text could be extracted from
  document" — a Document reported as unreadable that nothing had tried to read.
- **Metadata extraction** caught it in `AssistantService.extract_metadata` and returned empty
  metadata, so the same unreachable server produced `llm_complete` with no title, no summary
  and no tags: a Document reported as described that no model had seen.

Both now let it through, under one rule: **a `ModelError` a stage can work around is absorbed;
one that leaves the stage with nothing to show is raised.** So:

- A page that fails while other pages were read keeps falling back to its embedded text. One
  unreadable page still costs the page, not the document.
- A read where the models read *no* page they were sent raises, because that is the models
  being away and not a document of blank pages. An image is always that case: one page, no
  embedded text to fall back on. The test counts pages the models read rather than comparing
  failures against pages sent, so a page dropped for some other reason — a PyMuPDF error on
  the worker — cannot stand in for one the models answered and hide an all-failed read.
- A page whose *formatter* failed keeps the raw text pass 1 read, and is not cached. Pass 1
  is the read; pass 2 is presentation, and throwing away a vision pass already paid for to
  retry the whole page is the expensive way to get back what is already in hand. The page
  cache is skipped for it because the key names the formatter, so remembering text that
  formatter never saw would serve it again once it is back.
- Tag reconciliation still falls back to the tags already generated. It has something to show.
- A reply that will not parse is still empty metadata, and a date that will not parse is still
  dropped (ADR 0006). Those are answers, just bad ones, and repeating them changes nothing.

`OCR_PAGE_CONCURRENCY` and the page-level fallback therefore cover a *page* that fails, and
the retry covers a *provider* that is away. They do not overlap.

## Consequences

- A model server restarting for ten seconds no longer leaves Documents needing a manual
  reprocess. The first retry is ten seconds later.
- A whole-stage retry re-reads pages that succeeded on the previous attempt. The page cache
  (ADR 0002) makes that a Redis lookup rather than two model passes, which is what makes
  retrying a 40-page read affordable. With `OCR_PAGE_CACHE_ENABLED` off, a retry costs the
  whole read again.
- A PDF whose pages mostly hold embedded text, with one scan the models could not read, now
  fails and retries rather than landing at `ocr_complete` with that page missing. Its embedded
  text is dropped with the failed attempt and re-read on the next one. Losing a page silently
  is the worse outcome: it cannot be seen after the fact, and a `failed` Document can.
- A rate limit and an unreachable host get the same backoff. Both are transient and the
  escalating schedule reaches both ends of that range, so splitting them would serve a
  distinction nothing can yet act on. `ModelConfigurationError` is a different case and is
  worth its own type: it is not transient at all, and the split is a fact about the fault
  rather than a guess about timing. If a provider's rate limits do turn out to want their own
  backoff, that subclass belongs in the adapters too, where the response actually is.
- Four attempts spread over 370 seconds is the whole budget. A model server down for longer
  leaves the Document `failed` with the provider's own message in `processing_error`, which is
  a truer report than the "No text could be extracted" it used to get.
- `autoretry_for` stays gone. Retrying is now a decision a pure function makes about a caught
  exception, not configuration on a decorator that cannot see one.
