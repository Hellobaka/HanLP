# HanLP RESTful API Server

A RESTful API server for HanLP that provides concurrent processing with queue management, token-based authentication, and advanced text analysis features.

## Features

1. **Command-line Configuration**: Start the server with customizable IP, port, and admin token
2. **SQLite-based Token Management**: Tokens stored in SQLite database with user tracking
3. **Dynamic Token Management**: Admin can delete tokens at runtime
4. **Token Request System**: Admin can request tokens for users with user ID
5. **Usage Statistics**: Automatic tracking of token usage and character processing
6. **Admin Statistics Interface**: View usage statistics for all tokens
7. **Text Processing**: Tokenization, word frequency analysis, and BM25 sparse vector calculation
8. **Concurrent Processing**: Handles up to 5 concurrent requests with queue management
9. **Timeout Handling**: Automatically terminates requests that exceed 3 minutes
10. **JSON Responses**: All responses are formatted as JSON

## Usage

### Starting the Server

```bash
# Start with default settings (localhost:8000)
python -m hanlp.server

# Start with custom host and port
python -m hanlp.server --host 0.0.0.0 --port 8080

# Start with admin token
python -m hanlp.server --admin-token my-admin-token

# Start with custom database path
python -m hanlp.server --db-path /path/to/tokens.db
```

### API Endpoints

#### POST /tokenize

Tokenize text with HanLP.

**Headers:**
- `Authorization: Bearer <token>` (required)
- `Content-Type: application/json`

**Body:**
```json
{
  "text": "Your text here",
  "tasks": ["tok", "pos"],        // Optional
  "skip_tasks": ["ner"],          // Optional
  "language": "zh",               // Optional
  "stopword": ["自定义停用词1", "自定义停用词2"]  // Optional, extends default stopwords
}
```

**Response:**
```json
{
  "tok": [...],
  "pos": [...],
  // ... other task results
}
```

#### GET /

Process text with HanLP using query parameters.

**Headers:**
- `Authorization: Bearer <token>` (required)

**Query Parameters:**
- `text`: Text to process (required)
- `tasks`: Comma-separated list of tasks (optional)
- `skip_tasks`: Comma-separated list of tasks to skip (optional)
- `language`: Language of the text (optional)

**Example:**
```
GET /?text=Hello%20world&tasks=tok,pos
```

#### POST /token/request

Request a new token for a user (admin only).

**Headers:**
- `Authorization: Bearer <admin-token>` (required)
- `Content-Type: application/json`

**Body:**
```json
{
  "user_id": 12345
}
```

**Response:**
```json
{
  "token": "generated-token-string",
  "reissued": true,
  "message": "Token issued successfully"
}
```

If the user already had tokens, they will be invalidated and a new one issued (reissued=true).

#### POST /token/delete

Delete a token (admin only).

**Headers:**
- `Authorization: Bearer <admin-token>` (required)
- `Content-Type: application/json`

**Body:**
```json
{
  "token": "token-to-delete"
}
```

**Response:**
```json
{
  "message": "Token deleted successfully"
}
```

#### POST /word-frequency

Get word frequency count for text.

**Headers:**
- `Authorization: Bearer <token>` (required)
- `Content-Type: application/json`

**Body:**
```json
{
  "text": "Your text here",
  "max_words": 100,  // Optional, default 100
  "stopword": ["自定义停用词1", "自定义停用词2"]  // Optional, extends default stopwords
}
```

**Response:**
```json
{
  "word_frequency": [
    {
      "word": "token",
      "count": 5
    },
    {
      "word": "text",
      "count": 3
    }
  ]
}
```

#### GET /stats or POST /stats

Get usage statistics for all tokens (admin only).

**Headers:**
- `Authorization: Bearer <admin-token>` (required)

**Response:**
```json
{
  "stats": [
    {
      "token": "token-string",
      "user_id": 12345,
      "created_at": "2023-01-01 12:00:00",
      "usage_count": 42,
      "char_count": 12345,
      "is_valid": true,
      "is_admin": false
    }
  ]
}
```

## Authentication

All requests (except token request) must include a valid Bearer token in the Authorization header:

```
Authorization: Bearer my-secret-token
```

Admin endpoints require a valid admin token.

## Concurrency and Queue Management

The server:
- Processes up to 5 requests concurrently
- Queues additional requests when all workers are busy
- Automatically terminates requests that take longer than 3 minutes
- Returns a 400 error for timed-out requests

## Response Format

All responses are JSON formatted:
- Successful responses: `200 OK` with result data
- Authentication errors: `401 Unauthorized`
- Processing errors: `500 Internal Server Error`
- Timeout errors: `400 Bad Request"
- Invalid endpoint errors: `404 Not Found"