from __future__ import annotations

import math
import re
from dataclasses import dataclass
from itertools import pairwise
from typing import Any

from app.services.fact_candidates import CandidateWrite
from app.services.pdf_extraction import PdfiumRegulationExtractor
from app.services.regulation_parser import ExtractedPage, TextLine
from app.services.storage import ObjectStorage

DRAWING_EXTRACTOR_VERSION = "m5.drawing-pipeline.v1"


@dataclass(frozen=True)
class DrawingExtraction:
    pages: list[ExtractedPage]
    candidates: list[CandidateWrite]


_OBJECT_PATTERNS = {
    "door": re.compile(r"^(?:[FM]?D\d+[A-Z]?|门\s*\d*)$", re.IGNORECASE),
    "room": re.compile(
        r"(?:办公室|会议室|储藏室|设备间|卫生间|走道|前室|机房|office|room|corridor|lobby)",
        re.IGNORECASE,
    ),
    "stair": re.compile(r"(?:楼梯|楼梯间|stair)", re.IGNORECASE),
    "exit": re.compile(r"(?:安全出口|疏散出口|EXIT)", re.IGNORECASE),
}
_TITLE = re.compile(
    r"(?:总平面图|平面图|剖面图|立面图|floor plan|section|elevation)", re.IGNORECASE
)
_NUMBER = re.compile(r"(?:图号|drawing\s*no\.?)[\uff1a:\s]*([A-Z0-9._-]+)", re.IGNORECASE)
_FLOOR = re.compile(r"((?:地下)?\d+\s*层|[B]?\d+F|roof|屋面)", re.IGNORECASE)
_SCALE = re.compile(r"(?:比例|scale)?\s*[\uff1a:]?\s*1\s*[\uff1a:]\s*(\d{1,5})", re.IGNORECASE)
_DIMENSION = re.compile(r"(?<!\d)(\d{3,5})(?:\s*mm)?(?!\d)", re.IGNORECASE)


def polyline_length(points: list[tuple[float, float]], pixels_per_meter: float) -> float:
    if len(points) < 2:
        raise ValueError("A path requires at least two points")
    if pixels_per_meter <= 0:
        raise ValueError("pixels_per_meter must be positive")
    pixels = sum(math.dist(start, end) for start, end in pairwise(points))
    return round(pixels / pixels_per_meter, 3)


def _location(page: ExtractedPage, line: TextLine) -> dict[str, Any]:
    return {
        "page": page.page_number,
        "bbox": line.bbox,
        "page_width": page.width,
        "page_height": page.height,
        "method": page.method,
    }


def _candidate(
    page: ExtractedPage,
    line: TextLine,
    key: str,
    value: Any,
    unit: str | None = None,
    scope: dict[str, Any] | None = None,
) -> CandidateWrite:
    return CandidateWrite(
        key=key,
        value=value,
        unit=unit,
        scope_data={"page": page.page_number, **(scope or {})},
        location=_location(page, line),
        excerpt=line.text.strip(),
        confidence=line.confidence,
    )


def extract_drawing_candidates(pages: list[ExtractedPage]) -> list[CandidateWrite]:
    candidates: list[CandidateWrite] = []
    for page in pages:
        object_counts = {name: 0 for name in _OBJECT_PATTERNS}
        for line_index, line in enumerate(page.lines, start=1):
            text = line.text.strip()
            if not text:
                continue
            if _TITLE.search(text):
                candidates.append(_candidate(page, line, "drawing.title", text))
            number_match = _NUMBER.search(text)
            if number_match:
                candidates.append(_candidate(page, line, "drawing.number", number_match.group(1)))
            floor_match = _FLOOR.search(text)
            if floor_match:
                candidates.append(_candidate(page, line, "drawing.floor", floor_match.group(1)))
            scale_match = _SCALE.search(text)
            if scale_match:
                candidates.append(
                    _candidate(
                        page,
                        line,
                        "drawing.scale_denominator",
                        int(scale_match.group(1)),
                        "ratio",
                    )
                )
            for object_type, pattern in _OBJECT_PATTERNS.items():
                if pattern.search(text):
                    object_counts[object_type] += 1
                    candidates.append(
                        _candidate(
                            page,
                            line,
                            "drawing.object",
                            {"type": object_type, "label": text},
                            scope={"object_type": object_type, "line": line_index},
                        )
                    )
            dimension_matches = [] if number_match or scale_match else _DIMENSION.finditer(text)
            for dimension_index, match in enumerate(dimension_matches, start=1):
                millimeters = float(match.group(1))
                candidates.append(
                    _candidate(
                        page,
                        line,
                        "drawing.dimension_m",
                        millimeters / 1000,
                        "m",
                        {"dimension": dimension_index, "raw_mm": millimeters},
                    )
                )
        for object_type, count in object_counts.items():
            if count:
                key = "exit.count" if object_type == "exit" else f"{object_type}.count"
                anchor = next(
                    line
                    for line in page.lines
                    if _OBJECT_PATTERNS[object_type].search(line.text.strip())
                )
                candidates.append(_candidate(page, anchor, key, count, "count"))
    return candidates


class DrawingPipeline:
    def __init__(self, storage: ObjectStorage) -> None:
        self.storage = storage

    def extract(self, object_key: str, filename: str) -> DrawingExtraction:
        if not filename.lower().endswith(".pdf"):
            raise ValueError("The M5 drawing pipeline currently accepts PDF drawings")
        pages = PdfiumRegulationExtractor(self.storage).extract(object_key)
        return DrawingExtraction(pages, extract_drawing_candidates(pages))
