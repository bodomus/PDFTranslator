"""Scanned-book OCR and logical paragraph reconstruction."""

from pdftranslate.book.assembly import AssemblyOptions, assemble_book
from pdftranslate.book.models import BookDocument, BookParagraph
from pdftranslate.book.pipeline import BookOcrOptions, book_to_text, ocr_book
from pdftranslate.book.tesseract import TesseractError, TesseractRunner, parse_tsv
from pdftranslate.book.translate import book_translation_text, translate_book

__all__ = [
    "AssemblyOptions",
    "BookDocument",
    "BookOcrOptions",
    "BookParagraph",
    "TesseractError",
    "TesseractRunner",
    "assemble_book",
    "book_to_text",
    "book_translation_text",
    "ocr_book",
    "parse_tsv",
    "translate_book",
]
