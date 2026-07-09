# Todo List API

Create a simple Todo List API with the following features:

## Requirements

1. **Data Model**:
   - Todo item with: id, title, description, completed, created_at, updated_at
   - Use SQLite for storage

2. **API Endpoints**:
   - `GET /todos` - List all todos
   - `GET /todos/:id` - Get a specific todo
   - `POST /todos` - Create a new todo
   - `PUT /todos/:id` - Update a todo
   - `DELETE /todos/:id` - Delete a todo

3. **Features**:
   - Filter todos by completed status
   - Search todos by title
   - Pagination support

4. **Tests**:
   - Write tests for all endpoints
   - Test edge cases (invalid input, not found, etc.)

## Files to Create

- `app.py` - Main application file
- `database.py` - Database operations
- `test_app.py` - Tests
- `requirements.txt` - Dependencies

## Notes

- Use Flask for the web framework
- Use SQLite for the database
- Keep it simple and clean
