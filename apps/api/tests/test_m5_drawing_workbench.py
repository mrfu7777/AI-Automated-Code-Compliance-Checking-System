import asyncio
from typing import Any

from app.services.drawing_pipeline import (
    DrawingExtraction,
    extract_drawing_candidates,
    polyline_length,
)
from app.services.fact_candidates import CandidateWrite
from app.services.job_runtime import run_persisted_job
from app.services.regulation_parser import ExtractedPage, TextLine
from app.tasks import drawing_processing


def _page() -> ExtractedPage:
    return ExtractedPage(
        page_number=2,
        width=842,
        height=595,
        method="text_layer",
        lines=[
            TextLine("2层平面图", {"x0": 10, "y0": 540, "x1": 100, "y1": 560}, 0.99),
            TextLine("图号: A-102", {"x0": 700, "y0": 20, "x1": 810, "y1": 40}, 0.98),
            TextLine("比例 1:100", {"x0": 700, "y0": 45, "x1": 810, "y1": 65}, 0.97),
            TextLine("安全出口", {"x0": 40, "y0": 60, "x1": 100, "y1": 80}, 0.93),
            TextLine("楼梯间", {"x0": 140, "y0": 60, "x1": 190, "y1": 80}, 0.92),
            TextLine("D12", {"x0": 220, "y0": 60, "x1": 250, "y1": 80}, 0.91),
            TextLine("走道 1800", {"x0": 280, "y0": 60, "x1": 360, "y1": 80}, 0.90),
        ],
        image_png=b"drawing-png",
    )


def test_drawing_golden_set_extracts_positioned_objects_metadata_and_dimensions() -> None:
    candidates = extract_drawing_candidates([_page()])
    keys = {candidate.key for candidate in candidates}
    assert {
        "drawing.title",
        "drawing.number",
        "drawing.floor",
        "drawing.scale_denominator",
        "drawing.object",
        "drawing.dimension_m",
        "exit.count",
        "door.count",
        "room.count",
        "stair.count",
    } <= keys
    scale = next(
        candidate for candidate in candidates if candidate.key == "drawing.scale_denominator"
    )
    dimension = next(
        candidate for candidate in candidates if candidate.key == "drawing.dimension_m"
    )
    assert scale.value == 100
    assert dimension.value == 1.8
    assert dimension.location["page"] == 2
    assert dimension.location["bbox"]["x0"] == 280
    assert polyline_length([(0, 0), (30, 40), (30, 80)], 10) == 9


def test_drawing_pipeline_reuses_m4_candidate_review_and_evidence(
    m1_environment: Any, monkeypatch: Any
) -> None:
    client, storage, dispatcher, session_factory = m1_environment
    project = client.post("/api/v1/projects", json={"name": "M5 drawing pilot"}).json()
    upload = client.post(
        f"/api/v1/projects/{project['id']}/files",
        data={"logical_name": "A-102 existing floor plan"},
        files={"upload": ("A-102.pdf", b"%PDF-1.7\ndrawing", "application/pdf")},
    ).json()
    file_version_id = upload["file_version"]["id"]
    queued = client.post(
        f"/api/v1/projects/{project['id']}/drawing-extractions",
        json={"file_version_id": file_version_id},
    )
    assert queued.status_code == 201
    job_id, job_type = dispatcher.dispatched[-1]
    assert job_type == "drawing.extract"
    extraction = DrawingExtraction(
        [_page()],
        [
            CandidateWrite(
                key="exit.count",
                value=2,
                unit="count",
                scope_data={"page": 2},
                location={"page": 2, "bbox": {"x0": 40, "y0": 60, "x1": 100, "y1": 80}},
                excerpt="安全出口",
                confidence=0.93,
            )
        ],
    )
    monkeypatch.setattr(drawing_processing, "get_object_storage", lambda: storage)
    monkeypatch.setattr(
        drawing_processing.DrawingPipeline,
        "extract",
        lambda _self, _key, _filename: extraction,
    )
    asyncio.run(
        run_persisted_job(
            session_factory,
            job_id,
            drawing_processing.extract_drawing,
            error_code="drawing_extraction_failed",
        )
    )

    pages = client.get(
        f"/api/v1/projects/{project['id']}/drawings/{file_version_id}/pages"
    ).json()
    assert pages[0]["page_number"] == 2
    assert pages[0]["image_url"].startswith("https://storage.invalid/")
    candidates = client.get(f"/api/v1/projects/{project['id']}/fact-candidates").json()
    extracted = next(item for item in candidates if item["key"] == "exit.count")
    assert extracted["source"] == "drawing"
    assert extracted["evidence"][0]["kind"] == "image_region"
    assert extracted["verification_status"] == "candidate"

    measured = client.post(
        f"/api/v1/projects/{project['id']}/drawing-annotations",
        json={
            "file_version_id": file_version_id,
            "page_number": 2,
            "annotation_kind": "path",
            "fact_key": "egress.travel_distance_m",
            "label": "Architect-measured route",
            "points": [{"x": 0, "y": 0}, {"x": 30, "y": 40}],
            "pixels_per_meter": 10,
        },
    )
    assert measured.status_code == 201
    assert measured.json()["candidate"]["value"] == 5
    assert measured.json()["candidate"]["verification_status"] == "candidate"
    verified = client.post(
        f"/api/v1/fact-candidates/{measured.json()['candidate']['id']}/verify",
        json={"reason": "Calibrated against a known dimension"},
    )
    assert verified.status_code == 200
