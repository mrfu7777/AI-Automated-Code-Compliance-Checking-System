from __future__ import annotations

import io
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Literal, cast

import pypdfium2 as pdfium
from rapidocr import RapidOCR

from app.services.regulation_parser import ExtractedPage, TextLine
from app.services.storage import ObjectStorage


class PdfiumRegulationExtractor:
    """Extract positioned text, falling back to local Chinese OCR page by page."""

    def __init__(self, storage: ObjectStorage, ocr: RapidOCR | None = None) -> None:
        self.storage = storage
        self.ocr = ocr

    def extract(self, object_key: str) -> list[ExtractedPage]:
        with TemporaryDirectory(prefix="code-compliance-m2-") as directory:
            source = Path(directory) / "source.pdf"
            self.storage.download_to_file(object_key, source)
            document = pdfium.PdfDocument(source)
            return [
                self._extract_page(document[index], index + 1) for index in range(len(document))
            ]

    def _extract_page(self, page: pdfium.PdfPage, page_number: int) -> ExtractedPage:
        width, height = page.get_size()
        bitmap = page.render(scale=2)
        image = bitmap.to_pil()
        image_buffer = io.BytesIO()
        image.save(image_buffer, format="PNG")
        image_png = image_buffer.getvalue()
        lines = self._text_layer_lines(page)
        useful_chars = sum(len(re.sub(r"\s+", "", line.text)) for line in lines)
        method: Literal["text_layer", "ocr"] = "text_layer"
        if useful_chars < 40:
            lines = self._ocr_lines(image_png, width, height, image.width, image.height)
            method = "ocr"
        return ExtractedPage(page_number, width, height, method, lines, image_png)

    def _text_layer_lines(self, page: pdfium.PdfPage) -> list[TextLine]:
        text_page = page.get_textpage()
        lines: list[TextLine] = []
        chars: list[str] = []
        boxes: list[tuple[float, float, float, float]] = []
        for index in range(text_page.count_chars()):
            char = text_page.get_text_range(index, 1)
            if char in {"\r", "\n"}:
                self._append_text_line(lines, chars, boxes)
                chars, boxes = [], []
            elif char:
                chars.append(char)
                boxes.append(text_page.get_charbox(index))
        self._append_text_line(lines, chars, boxes)
        return lines

    @staticmethod
    def _append_text_line(
        lines: list[TextLine], chars: list[str], boxes: list[tuple[float, float, float, float]]
    ) -> None:
        text = "".join(chars).strip()
        if not text or not boxes:
            return
        lines.append(
            TextLine(
                text,
                {
                    "x0": min(box[0] for box in boxes),
                    "y0": min(box[1] for box in boxes),
                    "x1": max(box[2] for box in boxes),
                    "y1": max(box[3] for box in boxes),
                    "origin": "bottom-left",
                },
                1.0,
            )
        )

    def _ocr_lines(
        self, image_png: bytes, width: float, height: float, image_width: int, image_height: int
    ) -> list[TextLine]:
        if self.ocr is None:
            self.ocr = RapidOCR()
        output = cast(Any, self.ocr(image_png))
        boxes = output.boxes or []
        texts = output.txts or []
        scores = output.scores or []
        result: list[TextLine] = []
        for box, text, score in zip(boxes, texts, scores, strict=False):
            xs = [float(point[0]) for point in box]
            ys = [float(point[1]) for point in box]
            result.append(
                TextLine(
                    str(text),
                    {
                        "x0": min(xs) * width / image_width,
                        "y0": height - max(ys) * height / image_height,
                        "x1": max(xs) * width / image_width,
                        "y1": height - min(ys) * height / image_height,
                        "origin": "bottom-left",
                    },
                    float(score),
                )
            )
        return result
