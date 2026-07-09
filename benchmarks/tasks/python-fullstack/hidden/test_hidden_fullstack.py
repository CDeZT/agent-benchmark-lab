"""
Hidden tests for the Book Library API.
Tests: update timestamp, delete cascade, reading list validation, stats accuracy.
"""

import sys
import os
import time
from pathlib import Path

workspace = Path(os.environ["AGENT_BENCH_WORKSPACE"])
sys.path.insert(0, str(workspace))

try:
    from app import app
except ImportError:
    print("SKIP: flask not installed. Run: pip install flask")
    sys.exit(0)


def setup_app():
    app.config["TESTING"] = True
    db_path = str(workspace / "test_hidden_library.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    import app as app_module
    app_module.DATABASE = db_path
    return app.test_client()


def test_update_sets_timestamp():
    client = setup_app()
    resp = client.post("/api/books", json={"title": "Timestamp Test", "author": "Author"})
    book_id = resp.get_json()["id"]
    resp = client.get(f"/api/books/{book_id}")
    original_ts = resp.get_json()["updated_at"]
    time.sleep(0.1)
    resp = client.put(f"/api/books/{book_id}", json={"title": "Updated Title"})
    updated = resp.get_json()
    assert updated["updated_at"] != original_ts, (
        f"updated_at should change after PUT. Was '{original_ts}', still '{updated['updated_at']}'"
    )


def test_delete_cascades_to_reading_list():
    client = setup_app()
    resp = client.post("/api/books", json={"title": "Cascade Test", "author": "Author"})
    book_id = resp.get_json()["id"]
    resp = client.post("/api/reading-list", json={"book_id": book_id})
    assert resp.status_code == 201
    resp = client.delete(f"/api/books/{book_id}")
    assert resp.status_code == 200, f"Delete should succeed but got {resp.status_code}: {resp.get_json()}"
    resp = client.get("/api/reading-list")
    items = resp.get_json()
    assert len(items) == 0, f"Reading list should be empty after book deletion, got {len(items)}"


def test_reading_list_validates_book_id():
    client = setup_app()
    resp = client.post("/api/reading-list", json={"book_id": 99999})
    assert resp.status_code in (400, 404), (
        f"Adding non-existent book to reading list should fail, got {resp.status_code}"
    )


def test_stats_excludes_null_ratings():
    client = setup_app()
    client.post("/api/books", json={"title": "Rated", "author": "A", "rating": 4.0})
    client.post("/api/books", json={"title": "Unrated", "author": "B"})
    resp = client.get("/api/stats")
    stats = resp.get_json()
    assert abs(stats["average_rating"] - 4.0) < 0.01, (
        f"Average rating should be 4.0 (excluding NULLs), got {stats['average_rating']}"
    )


def test_search_finds_results():
    client = setup_app()
    client.post("/api/books", json={"title": "The Great Gatsby", "author": "F. Scott Fitzgerald"})
    client.post("/api/books", json={"title": "Great Expectations", "author": "Charles Dickens"})
    resp = client.get("/api/books/search?q=Great")
    results = resp.get_json()
    assert len(results) == 2, f"Search for 'Great' should find 2 books, got {len(results)}"


def test_reading_list_with_filter():
    client = setup_app()
    resp = client.post("/api/books", json={"title": "Filter Test", "author": "A"})
    book_id = resp.get_json()["id"]
    client.post("/api/reading-list", json={"book_id": book_id, "status": "reading"})
    resp = client.get("/api/reading-list?status=reading")
    assert len(resp.get_json()) == 1
    resp = client.get("/api/reading-list?status=finished")
    assert len(resp.get_json()) == 0


if __name__ == "__main__":
    tests = [v for k, v in globals().items() if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for test in tests:
        try:
            test(); passed += 1; print(f"  PASS: {test.__name__}")
        except Exception as e:
            failed += 1; print(f"  FAIL: {test.__name__}: {e}")
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed > 0 else 0)
