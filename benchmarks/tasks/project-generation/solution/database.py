"""Database module for Todo List API."""

import sqlite3
from datetime import datetime
from typing import Any, Dict, List, Optional


class Database:
    """SQLite database manager for todos."""

    def __init__(self, db_path: str = "todos.db"):
        """Initialize database connection."""
        self.db_path = db_path
        self._create_table()

    def _create_table(self) -> None:
        """Create todos table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    completed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get_all(self, completed: Optional[str] = None, search: Optional[str] = None,
                page: int = 1, per_page: int = 10) -> List[Dict[str, Any]]:
        """Get all todos with optional filtering and pagination."""
        query = "SELECT * FROM todos WHERE 1=1"
        params = []

        if completed is not None:
            query += " AND completed = ?"
            params.append(completed.lower() == 'true')

        if search:
            query += " AND title LIKE ?"
            params.append(f"%{search}%")

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def get_by_id(self, todo_id: int) -> Optional[Dict[str, Any]]:
        """Get a todo by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
            return dict(row) if row else None

    def create(self, title: str, description: str = "") -> Dict[str, Any]:
        """Create a new todo."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO todos (title, description, created_at, updated_at) VALUES (?, ?, ?, ?)",
                (title, description, now, now)
            )
            conn.commit()
            return self.get_by_id(cursor.lastrowid)

    def update(self, todo_id: int, **kwargs) -> Optional[Dict[str, Any]]:
        """Update a todo."""
        todo = self.get_by_id(todo_id)
        if not todo:
            return None

        updates = []
        params = []
        for key, value in kwargs.items():
            if key in ['title', 'description', 'completed']:
                updates.append(f"{key} = ?")
                params.append(value)

        if not updates:
            return todo

        updates.append("updated_at = ?")
        params.append(datetime.now().isoformat())
        params.append(todo_id)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(f"UPDATE todos SET {', '.join(updates)} WHERE id = ?", params)
            conn.commit()
            return self.get_by_id(todo_id)

    def delete(self, todo_id: int) -> bool:
        """Delete a todo."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
            conn.commit()
            return cursor.rowcount > 0
