---
title: Foreign-language preservation
type: component
status: active
created: 2026-09-18
updated: 2026-09-18
tags:
- translation
- foreign-language
- protected-spans
- glossary
- cache
sources:
- ../../../Tickets/PDFTR-21-preserve-foreign-language-text.md
- ../../../src/pdftranslate/translation/foreign_language.py
- ../../../src/pdftranslate/translation/paragraphs.py
- ../../../src/pdftranslate/translation/cache.py
- ../../../tests/test_translation.py
related:
- ../architecture/system-overview.md
- ../testing/pilot-evaluation.md
---

# Foreign-language preservation

Paragraph translation classifies normal translatable content, confidently foreign whole units,
and translatable prose containing protected foreign spans. The decision is deterministic and is
recorded per logical-paragraph occurrence, because paragraph IDs are not necessarily unique.

## Policy

- A Greek-majority unit with sufficient Unicode Greek-script evidence is preserved verbatim.
- A Latin unit is preserved only when its length and several distinct Latin function-word signals
  reach conservative thresholds. Latin script alone is never evidence because English uses it.
- Greek-script runs and a deliberately small set of academic foreign terms are split out of
  otherwise translatable prose, never submitted to the model, then interleaved back exactly.
- Ambiguous content follows normal translation and records
  `no_confident_foreign_language_evidence`; the classifier has no probabilistic fallback.
- Whole-unit preservation bypasses the translation backend and sets `translated_text` to the exact
  source text. Inconsistent span assembly fails closed.

The implementation deliberately has no language-detection service or heavyweight dependency. It
does not claim universal language identification.

## Glossary and protected-token interaction

An explicit glossary `translate` match overrides automatic whole-unit preservation. Otherwise,
whole-unit classification uses the original paragraph so glossary placeholders cannot hide the
language evidence. The remaining prose still composes with glossary and general protected-token
placeholders; foreign spans are restored before glossary output validation performs the final
terminology check.

## Evidence and compatibility

Translation metadata reports classification, evidence reasons, page and paragraph identity,
preserved-span count, and whether the backend was called in the current run. Aggregate report
fields answer how many whole units and inline spans were preserved without including book text.

Translation behavior revision `5` invalidates earlier SQLite cache keys, partial translation
resume artifacts, and source-derived pipeline workspaces. This prevents a pre-PDFTR-21 result from
bypassing the preservation policy.
