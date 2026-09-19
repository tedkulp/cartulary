# Two model ports, each bound to one provider and model

Services that need a model (OCR, embeddings, the assistant) receive it at construction as one of two ports: a **chat model** (messages in, text out; images ride on messages, so vision is just chat) or an **embedder** (texts in, vectors out). Each instance is already bound to a single provider *and* model, so OCR receives a vision model and a formatter model rather than a client plus model names. We rejected a single "model provider" port with chat, vision-chat and embed methods (as first sketched in #14) because no provider but Ollama can do all three: sentence-transformers only embeds and Gemini is only used for chat, so a single port would force "not supported" methods on most adapters. We also rejected passing the model name per call: binding it keeps provider and model choice out of the services, lets tests script each OCR pass independently, and lets the vision and formatter models come from different providers (#8).

## Consequences

- Provider selection happens in one place, the factory, which builds each role (vision, formatter, assistant, embedder) from settings.
- A disabled capability is represented by no model (`None`), not by a flag inside the service.
