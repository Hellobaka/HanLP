# -*- coding:utf-8 -*-
# Author: Claude Code
# Date: 2025-09-25
"""
HanLP RESTful API Server Implementation
"""
import argparse
import json
import threading
import time
import queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import uuid

from hanlp_common.document import Document
import hanlp


class TaskQueue:
    """Manages concurrent processing with queue and timeout"""

    def __init__(self, max_workers=5, timeout=180):
        self.max_workers = max_workers
        self.timeout = timeout
        self.task_queue = queue.Queue()
        self.workers = []
        self.results = {}
        self.lock = threading.Lock()

        # Start worker threads
        for i in range(max_workers):
            worker = threading.Thread(target=self._worker, daemon=True)
            worker.start()
            self.workers.append(worker)

    def _worker(self):
        """Worker thread function"""
        while True:
            try:
                task_id, func, args, kwargs = self.task_queue.get(timeout=1)
                try:
                    result = func(*args, **kwargs)
                    with self.lock:
                        self.results[task_id] = {'status': 'completed', 'result': result}
                except Exception as e:
                    with self.lock:
                        self.results[task_id] = {'status': 'error', 'error': str(e)}
                finally:
                    self.task_queue.task_done()
            except queue.Empty:
                continue

    def submit(self, func, *args, **kwargs):
        """Submit a task for processing"""
        task_id = str(uuid.uuid4())
        with self.lock:
            self.results[task_id] = {'status': 'queued'}
        self.task_queue.put((task_id, func, args, kwargs))
        return task_id

    def get_result(self, task_id):
        """Get result of a task"""
        with self.lock:
            return self.results.get(task_id, None)

    def wait_for_result(self, task_id):
        """Wait for result with timeout"""
        start_time = time.time()
        while time.time() - start_time < self.timeout:
            result = self.get_result(task_id)
            if result and result['status'] in ['completed', 'error']:
                return result
            time.sleep(0.1)
        # Timeout reached
        with self.lock:
            if task_id in self.results:
                self.results[task_id] = {'status': 'timeout', 'error': 'Processing timeout'}
        return {'status': 'timeout', 'error': 'Processing timeout'}


class HanLPHandler(BaseHTTPRequestHandler):
    """HTTP request handler for HanLP RESTful API"""

    task_queue = TaskQueue(max_workers=5, timeout=180)  # 3 minutes timeout
    model = None
    valid_tokens = set()  # In production, use a proper token management system

    @classmethod
    def initialize_model(cls):
        """Initialize the HanLP model"""
        if cls.model is None:
            # Load a default model - in production you might want to make this configurable
            # Using a simpler model that should be available
            cls.model = hanlp.load('CTB9_TOK_ELECTRA_BASE')

    def _send_response(self, data, status_code=200):
        """Send JSON response"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _send_error(self, message, status_code=400):
        """Send error response"""
        self._send_response({'error': message}, status_code)

    def _check_auth(self):
        """Check Bearer token authentication"""
        auth_header = self.headers.get('Authorization')
        if not auth_header:
            return False

        if not auth_header.startswith('Bearer '):
            return False

        token = auth_header[7:]  # Remove 'Bearer ' prefix
        return token in self.valid_tokens

    def do_OPTIONS(self):
        """Handle CORS preflight requests"""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        """Handle POST requests"""
        # Check authentication
        if not self._check_auth():
            self._send_error('Unauthorized: Invalid or missing Bearer token', 401)
            return

        # Parse request
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            self._send_error('Missing request body')
            return

        try:
            post_data = self.rfile.read(content_length)
            request_data = json.loads(post_data.decode('utf-8'))
        except json.JSONDecodeError:
            self._send_error('Invalid JSON in request body')
            return

        # Extract parameters
        text = request_data.get('text')
        tasks = request_data.get('tasks')
        skip_tasks = request_data.get('skip_tasks')
        language = request_data.get('language')

        if not text:
            self._send_error('Missing "text" parameter')
            return

        # Submit task to queue
        task_id = self.task_queue.submit(
            self._process_text,
            text=text,
            tasks=tasks,
            skip_tasks=skip_tasks,
            language=language
        )

        # Wait for result with timeout
        result = self.task_queue.wait_for_result(task_id)

        if result['status'] == 'completed':
            self._send_response(result['result'])
        elif result['status'] == 'timeout':
            self._send_error('Request timeout: Processing took too long', 400)
        else:
            self._send_error(f'Processing error: {result["error"]}', 500)

    def _process_text(self, text, tasks=None, skip_tasks=None, language=None):
        """Process text with HanLP model"""
        try:
            result = self.model(text, tasks=tasks, skip_tasks=skip_tasks, language=language)
            # Convert Document to dict for JSON serialization
            if isinstance(result, Document):
                return result.to_dict()
            return result
        except Exception as e:
            raise Exception(f"Processing failed: {str(e)}")

    def do_GET(self):
        """Handle GET requests"""
        # Parse query parameters
        parsed_url = urlparse(self.path)
        query_params = parse_qs(parsed_url.query)

        # Extract parameters
        text = query_params.get('text', [None])[0]
        tasks = query_params.get('tasks', [None])[0]
        skip_tasks = query_params.get('skip_tasks', [None])[0]
        language = query_params.get('language', [None])[0]

        if not text:
            # Show API documentation
            self._send_response({
                'message': 'HanLP RESTful API Server',
                'endpoints': {
                    'POST /': 'Process text with HanLP',
                    'GET /': 'API documentation'
                },
                'parameters': {
                    'text': 'Text to process (required)',
                    'tasks': 'Tasks to run (optional)',
                    'skip_tasks': 'Tasks to skip (optional)',
                    'language': 'Language of text (optional)'
                },
                'authentication': 'Bearer token required in Authorization header'
            })
            return

        # Check authentication
        if not self._check_auth():
            self._send_error('Unauthorized: Invalid or missing Bearer token', 401)
            return

        # Submit task to queue
        task_id = self.task_queue.submit(
            self._process_text,
            text=text,
            tasks=tasks.split(',') if tasks else None,
            skip_tasks=skip_tasks.split(',') if skip_tasks else None,
            language=language
        )

        # Wait for result with timeout
        result = self.task_queue.wait_for_result(task_id)

        if result['status'] == 'completed':
            self._send_response(result['result'])
        elif result['status'] == 'timeout':
            self._send_error('Request timeout: Processing took too long', 400)
        else:
            self._send_error(f'Processing error: {result["error"]}', 500)


class HanLPServer:
    """HanLP RESTful API Server"""

    def __init__(self, host='localhost', port=8000, tokens=None, tokens_file=None):
        self.host = host
        self.port = port
        self.tokens = tokens or []
        self.tokens_file = tokens_file
        self.server = None

        # Load tokens from file if provided
        if self.tokens_file:
            self._load_tokens_from_file()

        # Set valid tokens
        if self.tokens:
            HanLPHandler.valid_tokens.update(self.tokens)

    def _load_tokens_from_file(self):
        """Load tokens from a file"""
        try:
            with open(self.tokens_file, 'r') as f:
                for line in f:
                    token = line.strip()
                    # Skip empty lines and comments
                    if token and not token.startswith('#'):
                        self.tokens.append(token)
        except FileNotFoundError:
            print(f"Warning: Tokens file {self.tokens_file} not found")
        except Exception as e:
            print(f"Error loading tokens from file: {e}")

    def start(self):
        """Start the server"""
        # Initialize model before starting server
        print("Initializing HanLP model...")
        HanLPHandler.initialize_model()
        print("Model initialization completed.")

        self.server = HTTPServer((self.host, self.port), HanLPHandler)
        print(f"Starting HanLP RESTful API server on {self.host}:{self.port}")
        print(f"Authentication tokens: {', '.join(self.tokens) if self.tokens else 'None (no authentication)'}")
        print("Press Ctrl+C to stop the server")

        try:
            self.server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down server...")
            self.server.shutdown()

    @classmethod
    def from_args(cls):
        """Create server from command line arguments"""
        parser = argparse.ArgumentParser(description='HanLP RESTful API Server')
        parser.add_argument('--host', type=str, default='localhost',
                          help='Host to bind to (default: localhost)')
        parser.add_argument('--port', type=int, default=8000,
                          help='Port to bind to (default: 8000)')
        parser.add_argument('--tokens', type=str, nargs='*',
                          help='Bearer tokens for authentication')
        parser.add_argument('--tokens-file', type=str,
                          help='File containing Bearer tokens for authentication')

        args = parser.parse_args()

        return cls(host=args.host, port=args.port, tokens=args.tokens, tokens_file=args.tokens_file)


def main():
    """Main entry point"""
    server = HanLPServer.from_args()
    server.start()


if __name__ == '__main__':
    main()