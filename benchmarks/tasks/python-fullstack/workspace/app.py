"""
Simple Book Library API - Flask backend with SQLite.

BUGS:
1. PUT /api/books/<id> doesn't update 'updated_at' timestamp
2. DELETE /api/books/<id> doesn't remove from reading_list first (FK error)
3. POST /api/reading-list doesn't validate book_id exists
4. GET /api/stats includes NULL ratings in average
"""

import os
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template, g

app = Flask(__name__)
DATABASE = os.path.join(os.path.dirname(__file__), "library.db")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DATABASE)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS books (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT NOT NULL,
            isbn TEXT UNIQUE,
            genre TEXT DEFAULT 'fiction',
            rating REAL,
            pages INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reading_list (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            book_id INTEGER NOT NULL,
            status TEXT DEFAULT 'want_to_read',
            notes TEXT,
            added_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (book_id) REFERENCES books(id)
        );
    """)
    db.commit()


@app.before_request
def ensure_db():
    init_db()


@app.route("/api/books", methods=["GET"])
def list_books():
    db = get_db()
    genre = request.args.get("genre")
    sort = request.args.get("sort", "title")
    order = request.args.get("order", "asc")
    query = "SELECT * FROM books"
    params = []
    if genre:
        query += " WHERE genre = ?"
        params.append(genre)
    allowed_sorts = ["title", "author", "rating", "pages", "created_at"]
    if sort in allowed_sorts:
        query += f" ORDER BY {sort}"
        if order.lower() == "desc":
            query += " DESC"
    books = db.execute(query, params).fetchall()
    return jsonify([dict(b) for b in books])


@app.route("/api/books/<int:book_id>", methods=["GET"])
def get_book(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        return jsonify({"error": "Book not found"}), 404
    return jsonify(dict(book))


@app.route("/api/books", methods=["POST"])
def create_book():
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    required = ["title", "author"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing field: {field}"}), 400
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO books (title, author, isbn, genre, rating, pages) VALUES (?, ?, ?, ?, ?, ?)",
            (data["title"], data["author"], data.get("isbn"), data.get("genre", "fiction"),
             data.get("rating"), data.get("pages")),
        )
        db.commit()
        book = db.execute("SELECT * FROM books WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(dict(book)), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "ISBN already exists"}), 409


# BUG: doesn't update 'updated_at' field
@app.route("/api/books/<int:book_id>", methods=["PUT"])
def update_book(book_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        return jsonify({"error": "Book not found"}), 404
    fields = []
    params = []
    for key in ["title", "author", "isbn", "genre", "rating", "pages"]:
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if not fields:
        return jsonify({"error": "No fields to update"}), 400
    params.append(book_id)
    db.execute(f"UPDATE books SET {', '.join(fields)} WHERE id = ?", params)
    db.commit()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    return jsonify(dict(book))


# BUG: doesn't remove from reading_list first
@app.route("/api/books/<int:book_id>", methods=["DELETE"])
def delete_book(book_id):
    db = get_db()
    book = db.execute("SELECT * FROM books WHERE id = ?", (book_id,)).fetchone()
    if not book:
        return jsonify({"error": "Book not found"}), 404
    db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    db.commit()
    return jsonify({"message": "Book deleted"})


@app.route("/api/books/search", methods=["GET"])
def search_books():
    query = request.args.get("q", "")
    if not query:
        return jsonify([])
    db = get_db()
    search_term = f"%{query}%"
    books = db.execute(
        "SELECT * FROM books WHERE title LIKE ? OR author LIKE ? OR isbn LIKE ?",
        (search_term, search_term, search_term),
    ).fetchall()
    return jsonify([dict(b) for b in books])


@app.route("/api/reading-list", methods=["GET"])
def get_reading_list():
    db = get_db()
    status = request.args.get("status")
    query = "SELECT rl.*, b.title, b.author, b.genre FROM reading_list rl JOIN books b ON rl.book_id = b.id"
    params = []
    if status:
        query += " WHERE rl.status = ?"
        params.append(status)
    items = db.execute(query, params).fetchall()
    return jsonify([dict(item) for item in items])


# BUG: doesn't validate book_id exists
@app.route("/api/reading-list", methods=["POST"])
def add_to_reading_list():
    data = request.get_json()
    if not data or "book_id" not in data:
        return jsonify({"error": "book_id required"}), 400
    db = get_db()
    try:
        cursor = db.execute(
            "INSERT INTO reading_list (book_id, status, notes) VALUES (?, ?, ?)",
            (data["book_id"], data.get("status", "want_to_read"), data.get("notes")),
        )
        db.commit()
        item = db.execute("SELECT * FROM reading_list WHERE id = ?", (cursor.lastrowid,)).fetchone()
        return jsonify(dict(item)), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": "Invalid book_id"}), 400


@app.route("/api/reading-list/<int:item_id>", methods=["PUT"])
def update_reading_list(item_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "JSON body required"}), 400
    db = get_db()
    item = db.execute("SELECT * FROM reading_list WHERE id = ?", (item_id,)).fetchone()
    if not item:
        return jsonify({"error": "Reading list item not found"}), 404
    fields = []
    params = []
    for key in ["status", "notes"]:
        if key in data:
            fields.append(f"{key} = ?")
            params.append(data[key])
    if not fields:
        return jsonify({"error": "No fields to update"}), 400
    params.append(item_id)
    db.execute(f"UPDATE reading_list SET {', '.join(fields)} WHERE id = ?", params)
    db.commit()
    item = db.execute("SELECT * FROM reading_list WHERE id = ?", (item_id,)).fetchone()
    return jsonify(dict(item))


@app.route("/api/reading-list/<int:item_id>", methods=["DELETE"])
def remove_from_reading_list(item_id):
    db = get_db()
    item = db.execute("SELECT * FROM reading_list WHERE id = ?", (item_id,)).fetchone()
    if not item:
        return jsonify({"error": "Reading list item not found"}), 404
    db.execute("DELETE FROM reading_list WHERE id = ?", (item_id,))
    db.commit()
    return jsonify({"message": "Removed from reading list"})


# BUG: includes NULL ratings in average
@app.route("/api/stats", methods=["GET"])
def get_stats():
    db = get_db()
    total_books = db.execute("SELECT COUNT(*) FROM books").fetchone()[0]
    total_in_list = db.execute("SELECT COUNT(*) FROM reading_list").fetchone()[0]
    avg_rating = db.execute("SELECT AVG(rating) FROM books").fetchone()[0]
    genre_counts = db.execute(
        "SELECT genre, COUNT(*) as count FROM books GROUP BY genre ORDER BY count DESC"
    ).fetchall()
    status_counts = db.execute(
        "SELECT status, COUNT(*) as count FROM reading_list GROUP BY status"
    ).fetchall()
    return jsonify({
        "total_books": total_books,
        "total_in_reading_list": total_in_list,
        "average_rating": round(avg_rating, 2) if avg_rating else 0,
        "genres": [dict(g) for g in genre_counts],
        "reading_status": [dict(s) for s in status_counts],
    })


@app.route("/")
def index():
    return render_template("index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
