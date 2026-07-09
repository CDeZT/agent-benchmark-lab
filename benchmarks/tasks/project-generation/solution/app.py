"""Todo List API application."""

from flask import Flask, request, jsonify
from database import Database

app = Flask(__name__)
db = Database()


@app.route('/todos', methods=['GET'])
def list_todos():
    """List all todos with optional filtering and pagination."""
    completed = request.args.get('completed')
    search = request.args.get('search')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))

    todos = db.get_all(completed=completed, search=search, page=page, per_page=per_page)
    return jsonify(todos)


@app.route('/todos/<int:todo_id>', methods=['GET'])
def get_todo(todo_id):
    """Get a specific todo."""
    todo = db.get_by_id(todo_id)
    if todo is None:
        return jsonify({"error": "Todo not found"}), 404
    return jsonify(todo)


@app.route('/todos', methods=['POST'])
def create_todo():
    """Create a new todo."""
    data = request.get_json()
    if not data or 'title' not in data:
        return jsonify({"error": "Title is required"}), 400

    todo = db.create(
        title=data['title'],
        description=data.get('description', '')
    )
    return jsonify(todo), 201


@app.route('/todos/<int:todo_id>', methods=['PUT'])
def update_todo(todo_id):
    """Update a todo."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    todo = db.update(todo_id, **data)
    if todo is None:
        return jsonify({"error": "Todo not found"}), 404
    return jsonify(todo)


@app.route('/todos/<int:todo_id>', methods=['DELETE'])
def delete_todo(todo_id):
    """Delete a todo."""
    success = db.delete(todo_id)
    if not success:
        return jsonify({"error": "Todo not found"}), 404
    return jsonify({"message": "Todo deleted"}), 200


if __name__ == '__main__':
    app.run(debug=True)
