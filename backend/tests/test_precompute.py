"""Заранее посчитанные результаты примеров: хранятся, отдаются без расчёта и пересчитываются при правках."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.services import precompute, site


@pytest.fixture(scope="module")
def computed(client: TestClient) -> dict:
    """Все опубликованные примеры посчитаны — как после фонового расчёта при старте."""
    precompute.run_pending()
    return site.published_examples()[0]


def test_results_are_ready_without_calculation(client: TestClient, computed: dict, monkeypatch) -> None:
    monkeypatch.setattr(precompute, "compute", lambda ex: pytest.fail("расчёт при показе примера"))
    body = client.get(f"/api/public/examples/{computed['id']}/results").json()
    assert body["ready"] is True
    first = computed["variants"][0]["id"]
    assert body["keys"]["A"] == first
    report = body["variants"][first]
    assert {"id", "grid", "scores", "notes"} <= set(report)
    assert set(report["scores"]) == {"focus", "ease", "thumb", "contrast"}
    assert set(body["shelf"]) == {"mobile", "desktop"}


def test_registered_ids_work_for_the_shelf(client: TestClient, computed: dict) -> None:
    body = client.get(f"/api/public/examples/{computed['id']}/results").json()
    ids = {key: body["variants"][image_id]["id"] for key, image_id in body["keys"].items()}

    r = client.post("/api/shelf", data={"variants": json.dumps(ids)})
    assert r.status_code == 200  # картинки уже в очереди загрузок — повторно слать их не нужно


def test_showcase_comes_from_stored_results(client: TestClient, computed: dict) -> None:
    body = client.get("/api/public/showcase").json()
    assert body["example"] == computed["id"]
    assert 0 <= body["feed"]["target"] < len(body["feed"]["tiles"])


def test_edit_in_admin_invalidates_results(client: TestClient, computed: dict) -> None:
    token = client.post("/api/admin/login", json={"password": "test-password"}).json()["token"]
    headers = {"Authorization": f"Bearer {token}"}
    image = computed["variants"][0]
    url = f"/api/admin/examples/{computed['id']}/images/{image['id']}"
    client.patch(url, headers=headers, json={"title": "Новая подпись"})

    edited = next(e for e in site.published_examples() if e["id"] == computed["id"])
    assert precompute.load(edited) is None  # отпечаток изменился — старые результаты не отдаём
    assert client.get(f"/api/public/examples/{computed['id']}/results").json() == {"ready": False}
    assert precompute.run_pending() >= 1
    assert precompute.load(edited) is not None


def test_unknown_example_is_404(client: TestClient) -> None:
    assert client.get("/api/public/examples/deadbeef/results").status_code == 404
