"""Tests for Todo List API."""

import os
import sys
import json
import tempfile

sys.path.insert(0, os.path.dirname(__file__))

try:
    from app import app
    from database import Database
except ImportError:
    print("SKIP: flask not installed. Run: pip install flask")
    sys.exit(0)


def setup_app():
    """Setup test application."""
    app.config['TESTING'] = True
    db_path = tempfile.mktemp(suffix='.db')
    app.config['DATABASE'] = db_path
    return app.test_client(), db_path


def test_create_todo():
    """Test creating a new todo."""
    client, db_path = setup_app()
    try:
        response = client.post('/todos', json={
            'title': 'Test Todo',
            'description': 'Test Description'
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data['title'] == 'Test Todo'
        assert data['description'] == 'Test Description'
        assert data['completed'] == False
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_list_todos():
    """Test listing todos."""
    client, db_path = setup_app()
    try:
        # Create some todos
        client.post('/todos', json={'title': 'Todo 1'})
        client.post('/todos', json={'title': 'Todo 2'})

        response = client.get('/todos')
        assert response.status_code == 200
        data = response.get_json()
        assert len(data) == 2
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_get_todo():
    """Test getting a specific todo."""
    client, db_path = setup_app()
    try:
        # Create a todo
        response = client.post('/todos', json={'title': 'Test Todo'})
        todo_id = response.get_json()['id']

        # Get the todo
        response = client.get(f'/todos/{todo_id}')
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'Test Todo'
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_update_todo():
    """Test updating a todo."""
    client, db_path = setup_app()
    try:
        # Create a todo
        response = client.post('/todos', json={'title': 'Test Todo'})
        todo_id = response.get_json()['id']

        # Update the todo
        response = client.put(f'/todos/{todo_id}', json={
            'title': 'Updated Todo',
            'completed': True
        })
        assert response.status_code == 200
        data = response.get_json()
        assert data['title'] == 'Updated Todo'
        assert data['completed'] == True
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_delete_todo():
    """Test deleting a todo."""
    client, db_path = setup_app()
    try:
        # Create a todo
        response = client.post('/todos', json={'title': 'Test Todo'})
        todo_id = response.get_json()['id']

        # Delete the todo
        response = client.delete(f'/todos/{todo_id}')
        assert response.status_code == 200

        # Verify it's deleted
        response = client.get(f'/todos/{todo_id}')
        assert response.status_code == 404
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_filter_by_completed():
    """Test filtering todos by completed status."""
    client, db_path = setup_app()
    try:
        # Create todos
        client.post('/todos', json={'title': 'Todo 1'})
        client.post('/todos', json={'title': 'Todo 2'})

        # Mark one as completed
        response = client.get('/todos')
        todo_id = response.get_json()[0]['id']
        client.put(f'/todos/{todo_id}', json={'completed': True})

        # Filter by completed
        response = client.get('/todos?completed=true')
        data = response.get_json()
        assert len(data) == 1
        assert data[0]['completed'] == True
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_search_todos():
    """Test searching todos by title."""
    client, db_path = setup_app()
    try:
        # Create todos
        client.post('/todos', json={'title': 'Buy groceries'})
        client.post('/todos', json={'title': 'Clean house'})
        client.post('/todos', json={'title': 'Buy clothes'})

        # Search for "Buy"
        response = client.get('/todos?search=Buy')
        data = response.get_json()
        assert len(data) == 2
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


def test_pagination():
    """Test pagination."""
    client, db_path = setup_app()
    try:
        # Create multiple todos
        for i in range(15):
            client.post('/todos', json={'title': f'Todo {i}'})

        # Get first page
        response = client.get('/todos?page=1&per_page=10')
        data = response.get_json()
        assert len(data) == 10

        # Get second page
        response = client.get('/todos?page=2&per_page=10')
        data = response.get_json()
        assert len(data) == 5
    finally:
        if os.path.exists(db_path):
            os.remove(db_path)


if __name__ == '__main__':
    import pytest
    pytest.main([__file__, '-v'])
