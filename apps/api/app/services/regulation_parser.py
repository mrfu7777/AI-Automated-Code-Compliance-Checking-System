from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class TextLine:
    text: str
    bbox: dict[str, float | str]
    confidence: float


@dataclass(frozen=True)
class ExtractedPage:
    page_number: int
    width: float
    height: float
    method: Literal["text_layer", "ocr"]
    lines: list[TextLine]
    image_png: bytes


@dataclass
class ClauseCandidate:
    number: str
    level: str
    heading: str | None
    text: str
    page_number: int
    bbox: dict[str, float | str]
    confidence: float
    parent_number: str | None = None


CHAPTER_RE = re.compile(r"^第([一二三四五六七八九十百〇零两\d]+)章\s*(.*)$")
SECTION_RE = re.compile(r"^第([一二三四五六七八九十百〇零两\d]+)节\s*(.*)$")
ARTICLE_RE = re.compile(r"^(\d+(?:\.\d+){1,4})\s*(.+)$")


def _normalized_margin(line: TextLine) -> str:
    return re.sub(r"\d+", "#", re.sub(r"\s+", "", line.text))


def remove_repeated_margins(pages: list[ExtractedPage]) -> list[ExtractedPage]:
    """Remove repeated top and bottom lines while retaining all source coordinates."""
    if len(pages) < 3:
        return pages
    counts: dict[str, int] = {}
    for page in pages:
        seen = {
            _normalized_margin(line)
            for line in page.lines
            if line.text.strip()
            and (
                float(line.bbox["y1"]) > page.height * 0.9
                or float(line.bbox["y0"]) < page.height * 0.1
            )
        }
        for value in seen:
            counts[value] = counts.get(value, 0) + 1
    repeated = {value for value, count in counts.items() if count / len(pages) >= 0.6}
    return [
        ExtractedPage(
            page_number=page.page_number,
            width=page.width,
            height=page.height,
            method=page.method,
            lines=[line for line in page.lines if _normalized_margin(line) not in repeated],
            image_png=page.image_png,
        )
        for page in pages
    ]


def parse_clause_tree(pages: list[ExtractedPage]) -> list[ClauseCandidate]:
    """Build a deterministic chapter/section/article tree from positioned text lines."""
    result: list[ClauseCandidate] = []
    current_chapter: str | None = None
    current_section: str | None = None
    current: ClauseCandidate | None = None

    for page in remove_repeated_margins(pages):
        for line in page.lines:
            text = re.sub(r"\s+", " ", line.text).strip()
            if not text:
                continue
            chapter = CHAPTER_RE.match(text)
            section = SECTION_RE.match(text)
            article = ARTICLE_RE.match(text)
            if chapter:
                number = f"第{chapter.group(1)}章"
                current = ClauseCandidate(
                    number,
                    "chapter",
                    chapter.group(2) or None,
                    text,
                    page.page_number,
                    line.bbox,
                    line.confidence,
                )
                result.append(current)
                current_chapter, current_section = number, None
            elif section:
                number = f"第{section.group(1)}节"
                current = ClauseCandidate(
                    number,
                    "section",
                    section.group(2) or None,
                    text,
                    page.page_number,
                    line.bbox,
                    line.confidence,
                    current_chapter,
                )
                result.append(current)
                current_section = number
            elif article:
                current = ClauseCandidate(
                    article.group(1),
                    "article",
                    None,
                    text,
                    page.page_number,
                    line.bbox,
                    line.confidence,
                    current_section or current_chapter,
                )
                result.append(current)
            elif current is not None and current.level == "article":
                current.text = f"{current.text}\n{text}"
                current.confidence = min(current.confidence, line.confidence)
                current.bbox = _union_bbox(current.bbox, line.bbox)
    return result


def _union_bbox(
    left: dict[str, float | str], right: dict[str, float | str]
) -> dict[str, float | str]:
    return {
        "x0": min(float(left["x0"]), float(right["x0"])),
        "y0": min(float(left["y0"]), float(right["y0"])),
        "x1": max(float(left["x1"]), float(right["x1"])),
        "y1": max(float(left["y1"]), float(right["y1"])),
        "origin": "bottom-left",
    }
