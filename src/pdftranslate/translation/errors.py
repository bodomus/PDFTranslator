"""Translation-specific failures with actionable messages."""


class TranslationError(RuntimeError):
    """Base class for translation pipeline failures."""


class TranslationBackendError(TranslationError):
    """The selected model backend could not load or infer."""


class TranslationOutOfMemoryError(TranslationBackendError):
    """The backend exhausted accelerator memory."""


class TranslationCacheError(TranslationError):
    """The local translation-memory database is unavailable or corrupt."""


class ResumeMismatchError(TranslationError):
    """A partial output cannot be resumed with the requested settings."""


class ProtectedTokenError(TranslationError):
    """A protected source token could not be restored after inference."""


class TranslationInterruptedError(TranslationError):
    """Translation was interrupted after a recoverable checkpoint."""

    def __init__(self, partial_document: object) -> None:
        super().__init__("translation was interrupted; rerun with --resume")
        self.partial_document = partial_document
