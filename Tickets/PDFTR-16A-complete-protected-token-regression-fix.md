# PDFTR-16A — Complete protected-token regression fix

## Source

User-provided review file:
`C:/Users/bodom/Downloads/PDFTR-16A-complete-protected-token-regression-fix.md`

## Goal

Finish PDFTR-16 in the same branch:

```text
codex/PDFTR-16-fix-protected-token-detection
```

Do not create a new branch and do not start PDFTR-15.

## Required fixes

1. Update cache/workspace identity so stale protected-token preprocessing artifacts cannot be
   reused.
2. Tighten bare path detection structurally so natural-language slash alternatives remain
   translatable while real paths remain protected.
3. Add exact `men/ﬁrst` regression coverage.
4. Run the real failing PDF with CUDA and record whether execution proceeds beyond the previous
   protected-token error.

## Validation

Run focused tests, full static checks, `.\scripts\check.ps1`, and the real CUDA regression command
against:

```text
tests/Robitzsch Jan Maximilian - Epicurean Justice. Nature, Agreement, and Virtue - 2024_50.pdf
```

## Notes

Attachment support for YouTrack is unavailable in the current tool set; this file is saved locally
under `Tickets/` as required by the repository workflow.
