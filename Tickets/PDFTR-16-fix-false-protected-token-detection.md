# PDFTR-16 — Fix false protected token detection for slash-separated prose and PDF ligatures

## Source

YouTrack: https://bodomus.youtrack.cloud/projects/PDFTR/issues/PDFTR-16/Fix-false-protected-token-detection-for-slash-separated-prose-and-PDF-ligatures

## User-provided validation PDF

`tests/Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf`

## Summary

Fix false positives in generic protected-token detection where ordinary slash-separated prose from
PDF text extraction is treated as a protected path or identifier. Also normalize PDF ligature
characters before protected-token matching so words containing compatibility ligatures are handled
as prose instead of opaque tokens.

## Expected behavior

- Slash-separated ordinary prose remains translatable.
- Real URLs, email addresses, Windows paths, relative file paths, measurements, and numeric
  identifiers remain protected.
- PDF ligatures such as `ﬁ` and `ﬂ` are normalized for translation/cache identity and protected
  token detection.
- The fix is covered by focused unit tests and the normal quality gate.

## Workflow

- Branch: `codex/PDFTR-16-fix-protected-token-detection`
- Workflow level: Level 1 local translation text-preparation fix.
- Attachments: tool support for attaching files to the existing YouTrack issue is unavailable in
  this session; this markdown file is saved locally as required.
