"""
Public tests for the Book Library API.
Tests basic CRUD operations and frontend template rendering.

Requires: pip install flask
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

try:
    from app import app
except ImportError:
    print("SKIP: flask not installed. Run: pip install flask")
    sys.exit(0)


def setup_app():
    app.config["TESTING"] = True
    db_path = os.path.join(os.path.dirname(__file__), "test_library.db")
    if os.path.exists(db_path):
        os.remove(db_path)
    import app as app_module
    app_module.DATABASE = db_path
    return app.test_client()


def test_index_page():
    client = setup_app()
    response = client.get("/")
    assert response.status_code == 200
    assert b"Book Library" in response.data


def test_create_and_get_book():
    client = setup_app()
    response = client.post("/api/books", json={"title": "Test Book", "author": "Test Author", "genre": "fiction", "rating": 4.5, "pages": 300})
    assert response.status_code == 201
    data = response.get_json()
    assert data["title"] == "Test Book"
    book_id = data["id"]
    response = client.get(f"/api/books/{book_id}")
    assert response.status_code == 200
    assert response.get_json()["title"] == "Test Book"


def test_list_books():
    client = setup_app()
    client.post("/api/books", json={"title": "Book A", "author": "Author A"})
    client.post("/api/books", json={"title": "Book B", "author": "Author B"})
    response = client.get("/api/books")
    assert response.status_code == 200
    assert len(response.get_json()) == 2


def test_update_book():
    client = setup_app()
    response = client.post("/api/books", json={"title": "Old Title", "author": "Author"})
    book_id = response.get_json()["id"]
    response = client.put(f"/api/books/{book_id}", json={"title": "New Title"})
    assert response.status_code == 200
    assert response.get_json()["title"] == "New Title"


def test_delete_book():
    client = setup_app()
    response = client.post("/api/books", json={"title": "To Delete", "author": "Author"})
    book_id = response.get_json()["id"]
    response = client.delete(f"/api/books/{book_id}")
    assert response.status_code == 200
    response = client.get(f"/api/books/{book_id}")
    assert response.status_code == 404


def test_reading_list_crud():
    client = setup_app()
    response = client.post("/api/books", json={"title": "Reading Book", "author": "Author"})
    book_id = response.get_json()["id"]
    response = client.post("/api/reading-list", json={"book_id": book_id, "status": "reading"})
    assert response.status_code == 201
    response = client.get("/api/reading-list")
    assert response.status_code == 200
    items = response.get_json()
    assert len(items) == 1
    assert items[0]["title"] == "Reading Book"


def test_stats_endpoint():
    client = setup_app()
    client.post("/api/books", json={"title": "Book 1", "author": "A", "rating": 4.0})
    client.post("/api/books", json={"title": "Book 2", "author": "B", "rating": 5.0})
    response = client.get("/api/stats")
    assert response.status_code == 200
    stats = response.get_json()
    assert stats["total_books"] == 2


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
