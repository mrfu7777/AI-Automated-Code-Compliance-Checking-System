from app.services.regulation_parser import ExtractedPage, TextLine, parse_clause_tree


def _line(text: str, y0: float, y1: float, confidence: float = 0.98) -> TextLine:
    return TextLine(
        text=text,
        bbox={"x0": 20.0, "y0": y0, "x1": 580.0, "y1": y1, "origin": "bottom-left"},
        confidence=confidence,
    )


def test_golden_set_builds_hierarchy_coordinates_and_continuations() -> None:
    header = _line("建筑防火通用规范 1", 780, 795)
    pages = [
        ExtractedPage(
            1,
            600,
            800,
            "text_layer",
            [
                header,
                _line("第一章 总则", 700, 720),
                _line("第一节 基本规定", 660, 680),
                _line("1.0.1 建筑防火设计应保障人身和财产安全。", 620, 640),
                _line("不得以资料缺失推定为符合。", 590, 610, 0.92),
            ],
            b"png",
        ),
        ExtractedPage(
            2,
            600,
            800,
            "ocr",
            [
                _line("建筑防火通用规范 2", 780, 795),
                _line("2.1.3 疏散门净宽度不应小于 0.80m。", 620, 640, 0.88),
            ],
            b"png",
        ),
        ExtractedPage(
            3,
            600,
            800,
            "text_layer",
            [
                _line("建筑防火通用规范 3", 780, 795),
                _line("3.2.1 防火分区应符合规定。", 620, 640),
            ],
            b"png",
        ),
    ]

    clauses = parse_clause_tree(pages)

    assert [item.number for item in clauses] == ["第一章", "第一节", "1.0.1", "2.1.3", "3.2.1"]
    assert clauses[2].parent_number == "第一节"
    assert "不得以资料缺失" in clauses[2].text
    assert clauses[2].confidence == 0.92
    assert clauses[3].page_number == 2
    assert clauses[3].bbox["origin"] == "bottom-left"
    assert all("建筑防火通用规范" not in item.text for item in clauses)


def test_parser_ignores_unnumbered_text_before_first_heading() -> None:
    page = ExtractedPage(1, 600, 800, "text_layer", [_line("封面", 400, 420)], b"")
    assert parse_clause_tree([page]) == []
