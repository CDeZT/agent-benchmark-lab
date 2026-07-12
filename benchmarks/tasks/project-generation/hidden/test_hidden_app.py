"""Hidden tests for Todo List API — edge cases and advanced features."""
import os
import sys
import tempfile

workspace = os.environ.get("AGENT_BENCH_WORKSPACE", ".")
sys.path.insert(0, workspace)

try:
    from app import app
    import database
except ImportError:
    print("SKIP: flask not installed")
    sys.exit(0)


def setup_app():
    app.config["TESTING"] = True
    db_path = tempfile.mktemp(suffix=".db")
    app.config["DATABASE"] = db_path
    import app as app_module
    app_module.DATABASE = db_path
    return app.test_client(), db_path


def test_create_todo_with_all_fields():
    """Test creating a todo with all fields."""
    client, db_path = setup_app()
    try:
        resp = client.post("/todos", json={
            "title": "Test Todo",
            "description": "Test Description"
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["title"] == "Test Todo"
        assert data["description"] == "Test Description"
        assert data["completed"] == False
    finally:
        os.remove(db_path)


def test_update_todo():
    """Test updating a todo."""
    client, db_path = setup_app()
    try:
        resp = client.post("/todos", json={"title": "Original"})
        todo_id = resp.get_json()["id"]
        resp = client.put(f"/todos/{todo_id}", json={"title": "Updated", "completed": True})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["title"] == "Updated"
        assert data["completed"] == True
    finally:
        os.remove(db_path)


def test_delete_todo():
    """Test deleting a todo."""
    client, db_path = setup_app()
    try:
        resp = client.post("/todos", json={"title": "To Delete"})
        todo_id = resp.get_json()["id"]
        resp = client.delete(f"/todos/{todo_id}")
        assert resp.status_code == 200
        resp = client.get(f"/todos/{todo_id}")
        assert resp.status_code == 404
    finally:
        os.remove(db_path)


def test_filter_by_completed():
    """Test filtering todos by completed status."""
    client, db_path = setup_app()
    try:
        client.post("/todos", json={"title": "Todo 1"})
        client.post("/todos", json={"title": "Todo 2"})
        resp = client.get("/todos")
        todo_id = resp.get_json()[0]["id"]
        client.put(f"/todos/{todo_id}", json={"completed": True})
        resp = client.get("/todos?completed=true")
        data = resp.get_json()
        assert len(data) == 1
        assert data[0]["completed"] == True
    finally:
        os.remove(db_path)


def test_search_todos():
    """Test searching todos by title."""
    client, db_path = setup_app()
    try:
        client.post("/todos", json={"title": "Buy groceries"})
        client.post("/todos", json={"title": "Clean house"})
        client.post("/todos", json={"title": "Buy clothes"})
        resp = client.get("/todos?search=Buy")
        data = resp.get_json()
        assert len(data) == 2
    finally:
        os.remove(db_path)


def test_pagination():
    """Test pagination."""
    client, db_path = setup_app()
    try:
        for i in range(15):
            client.post("/todos", json={"title": f"Todo {i}"})
        resp = client.get("/todos?page=1&per_page=10")
        data = resp.get_json()
        assert len(data) == 10
        resp = client.get("/todos?page=2&per_page=10")
        data = resp.get_json()
        assert len(data) == 5
    finally:
        os.remove(db_path)


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
