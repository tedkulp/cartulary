# A model may clear a Document's tags, but only when it answered

`suggested_tags: []` used to carry two meanings the pipeline could not tell apart. It was
what the model said when no tag applied to a document, and it was equally what came back
when the reply would not parse, when the reply left the key out, and — before ADR 0007 —
when the model never answered at all. Any rule keyed on the empty list was therefore wrong
for one of those cases.

It was first wrong in the destructive direction: metadata extraction cleared every
`document_tags` row before looking at what the model had said, so a reply that failed to
parse wiped tags a person had set by hand. Moving the delete inside `if suggested_tags:`
stopped that, at the cost of making tag replacement one-directional — the model could add
tags and swap them, but never end a document at none. A document whose tags genuinely no
longer applied kept them until a human intervened.

The fix is to stop inferring which case happened from the length of a list, and have the
parse say. `AssistantService.extract_metadata` now returns `suggested_tags` as three
values: a list of names, an empty list when the model answered that none apply, and `None`
when it answered nothing — the reply would not parse, or had no tags key, or had something
that was not a list under it. `run_metadata` passes that straight into `StageResult.tags`,
whose contract already said exactly this: `None` leaves the Document's tags alone, and a
list replaces them entirely. An empty list is a list. The runner needed no change.

The model being away is no longer one of these cases. A provider failure raises
`ModelError` out of extraction and the stage is retried rather than recording an answer
nobody gave (ADR 0007), so by the time a reply is parsed there is a reply.

The extraction prompt now tells the model that an empty array is a legitimate answer when
no specific tag applies. It previously asked for "5-7 relevant tags" and offered no way to
decline, so the honest empty answer was barely reachable — and a rule that only fires on an
answer the model has not been told it may give is not a rule.

The task's `tags_added` reports only what landed, and only when tags were written at all.
Absent means the stage touched no tags; `0` means it set the Document's tags to none. The
count used to read `0` for every one of those.

**What this costs**: a successful empty answer clears tags a person added by hand, because
`document_tags` does not record who put a tag on a document. Distinguishing model-set from
user-set associations needs a column and a migration, and the archive's owner decided that
is worth doing separately rather than holding this fix behind it. Until then the model
replaces the whole set, which is already true of every non-empty answer.

The alternative was to keep the behaviour one-directional and close the issue: never let a
model remove the last tag, and fix only the misleading count. That keeps hand-set tags safe
by keeping them permanent, which makes automatic tagging a ratchet — every document
accumulates the tags of every description it has ever had.

Closes #30.
