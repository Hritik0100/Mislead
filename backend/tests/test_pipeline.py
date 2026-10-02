"""End-to-end MVP test: case -> collect (manual+rss-mock) -> analysis -> report."""
from fastapi.testclient import TestClient
from app.main import app

def test_e2e():
    c = TestClient(app)
    assert c.get("/health").status_code == 200
    r = c.post("/api/cases", json={"title": "T", "objective": "O", "keywords": ["breaking", "cure"], "platforms": ["rss", "web"]})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    r = c.post(f"/api/cases/{cid}/collect", json={"sources": [
        {"type": "manual", "platform": "x", "username": "acc1", "text": "Breaking shocking secret cure exposed share before deleted", "url": "http://example.invalid/1"},
        {"type": "manual", "platform": "telegram", "username": "acc2", "text": "Breaking shocking secret cure exposed share before deleted", "url": "http://example.invalid/2"},
    ], "max_items": 10})
    assert r.status_code == 200, r.text
    assert r.json()["stored"] >= 1
    r = c.post(f"/api/cases/{cid}/analysis", json={"analysis_type": "full"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "A_fake_news" in body and "D_verification" in body
    r = c.get(f"/api/cases/{cid}/report")
    assert r.status_code == 200
    rep = r.json()
    assert rep["counts"]["posts"] >= 1
    assert len(rep["assessments"]) >= 1
    # override audited
    r = c.patch(f"/api/cases/{cid}/assessment", json={"label": "Misleading", "rationale": "analyst confirmed", "actor": "tester"})
    assert r.status_code == 200
    print("E2E OK", rep["counts"])
