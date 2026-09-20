# A disabled capability answers 503, and clients ask before offering it

Cartulary's optional work — OCR, embeddings, chat, metadata extraction — is each a **capability**, on exactly when its builder in `app/providers/factory.py` returns a model rather than `None` (ADR 0001). An endpoint that needs one and finds it off raises `capability_disabled_error()` from `app/core/capabilities.py`, which is the only place the status code is written: **503 Service Unavailable**.

503, not 400: nothing about the request is wrong, and no change the caller makes will help. The condition is the server's, and it clears when whoever runs the deployment sets a flag. 501 was considered and rejected — it says the server does not implement the method at all, whereas Cartulary implements every one of these and this deployment has them switched off. The detail is therefore written for an operator: it names the capability, the setting that turns it back on, and the restart. No `Retry-After` is sent, because there is no time at which retrying starts working.

The two `documents.py` sites previously answered 400 and read `settings.EMBEDDING_ENABLED` / `settings.LLM_ENABLED` from inside the handler, which also broke ADR 0001's rule that only the factory reads settings. Asking the factory for the model and treating `None` as off settles both at once (#28).

Because 503 arrives only after a client has already offered the feature, `GET /api/v1/capabilities` reports the same four capabilities from the same builders, so web and mobile can hide or disable a feature instead of presenting one that always errors. It requires authentication: which capabilities a deployment runs is its configuration, not public. Chat and metadata share `LLM_ENABLED` and are reported separately anyway, so no client has to know they are one setting.

## Consequences

- One rule for the next endpoint: ask the factory, and raise `capability_disabled_error()` with what is missing and one of the `TURN_ON_*` constants, so the instruction to the operator is written once and shared by every endpoint needing that model. Adding a capability means adding a field to `CapabilitiesResponse` beside it.
- 503 conventionally invites a retry, and monitoring that alerts on 5xx will see these. That is the intended reading — a deployment answering 503 for a feature its users are reaching for is worth an operator's attention.
- A caller's own mistakes keep their 4xx: regenerating embeddings for a document with no text is still 400, because the caller can fix that.
- The capabilities endpoint is a second place the capabilities are listed. It reads them from the builders rather than from settings, so a capability cannot be reported on while its endpoints refuse. A builder that raises on a setting it cannot parse is reported off and logged, so a misconfigured provider does not take the whole answer down.
- Clients must not treat a missing `/capabilities` route as "everything off": an older backend has no such route, and the feature still works there.
