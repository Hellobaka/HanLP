# HanLP RESTful API Server

A RESTful API server for HanLP that provides concurrent processing with queue management and authentication.

## Features

1. **Command-line Configuration**: Start the server with customizable IP and port
2. **Bearer Token Authentication**: Secure your API with token-based authentication
3. **Concurrent Processing**: Handles up to 5 concurrent requests with queue management
4. **Timeout Handling**: Automatically terminates requests that exceed 3 minutes
5. **JSON Responses**: All responses are formatted as JSON

## Usage

### Starting the Server

```bash
# Start with default settings (localhost:8000)
python -m hanlp.server

# Start with custom host and port
python -m hanlp.server --host 0.0.0.0 --port 8080

# Start with authentication tokens
python -m hanlp.server --host 0.0.0.0 --port 8080 --tokens my-secret-token another-token
```

### API Endpoints

#### POST /

Process text with HanLP.

**Headers:**
- `Authorization: Bearer <token>` (required if tokens are configured)
- `Content-Type: application/json`

**Body:**
```json
{
  "text": "Your text here",
  "tasks": ["tok", "pos"],        // Optional
  "skip_tasks": ["ner"],          // Optional
  "language": "zh"                // Optional
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
- `Authorization: Bearer <token>` (required if tokens are configured)

**Query Parameters:**
- `text`: Text to process (required)
- `tasks`: Comma-separated list of tasks (optional)
- `skip_tasks`: Comma-separated list of tasks to skip (optional)
- `language`: Language of the text (optional)

**Example:**
```
GET /?text=Hello%20world&tasks=tok,pos
```

## Authentication

When starting the server with tokens, all requests must include a valid Bearer token in the Authorization header:

```
Authorization: Bearer my-secret-token
```

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
- Timeout errors: `400 Bad Request`