# Cartulary

A personal and team document archive: documents come in, are read (OCR), described (metadata), and made searchable and askable.

## Language

### Models

**Provider**:
A service Cartulary sends model work to: Ollama, OpenAI, Gemini, or local sentence-transformers.
_Avoid_: backend, vendor, client

**Chat model**:
A specific model at a specific provider that turns messages, optionally carrying images, into text.
_Avoid_: LLM, vision-chat, client

**Assistant model**:
The chat model that extracts document metadata and answers questions about documents.
_Avoid_: LLM

**Embedder**:
A specific model at a specific provider that turns text into vectors of one fixed dimension.
_Avoid_: embedding service, embedding client

### OCR

**Vision model**:
The chat model that reads raw text off a page image in the first OCR pass.

**Formatter model**:
The chat model that turns the vision model's raw text into markdown in the second OCR pass.

**Page concurrency**:
The most of a PDF's pages that are in the models at once. Both passes for one page run
together, so it is also a ceiling on the model requests OCR has outstanding.
_Avoid_: batch size, OCR parallelism
