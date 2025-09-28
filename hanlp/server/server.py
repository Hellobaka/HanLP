# -*- coding:utf-8 -*-
# Author: Claude Code
# Date: 2025-09-25
"""
HanLP RESTful API Server Implementation

A secure, efficient, and maintainable implementation with:
- Reduced code duplication through reusable helper methods
- Robust input validation and error handling
- Proper authentication and authorization
- Thread-safe concurrent processing
- Comprehensive security measures
"""
import argparse
import json
import threading
import time
import queue
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from .stopwords import DEFAULT_STOPWORDS
import uuid

from hanlp_common.document import Document
import hanlp
import threading
import socket

class HTTPServerV6(HTTPServer):
  address_family = socket.AF_INET6

class TaskQueue:
    """Manages concurrent processing with queue and timeout"

    This class provides a thread-safe task queue for processing HTTP requests
    with a configurable number of worker threads and timeout handling.
    """

    def __init__(self, max_workers=5, timeout=180):
        """Initialize the task queue with specified parameters.

        Args:
            max_workers (int): Maximum number of concurrent worker threads (default: 5)
            timeout (int): Maximum processing time in seconds before timeout (default: 180)
        """
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
        """Worker thread function that processes tasks from the queue.

        This method runs in a continuous loop, processing tasks from the queue
        with a timeout. It handles both successful completions and exceptions.
        """
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
        """Submit a task for asynchronous processing.

        Args:
            func: The function to execute
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function

        Returns:
            str: A unique task ID for tracking the result
        """
        task_id = str(uuid.uuid4())
        with self.lock:
            self.results[task_id] = {'status': 'queued'}
        self.task_queue.put((task_id, func, args, kwargs))
        return task_id

    def get_result(self, task_id):
        """Get the result of a submitted task.

        Args:
            task_id (str): The unique task ID

        Returns:
            dict or None: Task result or None if task doesn't exist
        """
        with self.lock:
            return self.results.get(task_id, None)

    def wait_for_result(self, task_id):
        """Wait for a task result with timeout.

        This method blocks until the task completes, errors, or times out.

        Args:
            task_id (str): The unique task ID

        Returns:
            dict: Task result with status (completed, error, or timeout) and result/error info
        """
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
    """HTTP request handler for HanLP RESTful API

    This handler implements all API endpoints with proper authentication,
    input validation, and concurrent processing using a task queue.
    """

    # Shared task queue for concurrent request processing
    task_queue = TaskQueue(max_workers=5, timeout=180)  # 3 minutes timeout

    # Shared model instance
    model = None

    # Database for token management
    token_db = None

    # Admin token for privileged operations
    admin_token = None

    @classmethod
    def initialize_model(cls):
        """Initialize the HanLP model.

        This method loads the default model once when the server starts.
        In production, this could be made configurable.
        """
        if cls.model is None:
            # Load a default model - in production you might want to make this configurable
            # Using a simpler model that should be available
            cls.model = hanlp.load('CTB9_TOK_ELECTRA_BASE')

    def _send_response(self, data, status_code=200):
        """Send a JSON response with appropriate headers.

        This method sets CORS headers for cross-origin requests and sends
        the response body as UTF-8 encoded JSON.

        Args:
            data: The data to serialize as JSON
            status_code (int): HTTP status code (default: 200)
        """
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def _send_error(self, message, status_code=400):
        """Send an error response in JSON format.

        This is a convenience method for sending error responses.

        Args:
            message (str): Error message to include in response
            status_code (int): HTTP status code (default: 400)
        """
        self._send_response({'error': message}, status_code)

    def _process_stopwords(self, stopword):
        """Process stopwords parameter and return a standardized stopword list.

        This method normalizes the stopword input to a consistent format.

        Args:
            stopword: Input stopword parameter (string, list, or None)

        Returns:
            list: A list of stopwords

        Raises:
            ValueError: If stopword is not a string, list, or None
        """
        # Apply stopword filtering if provided
        stopword_list = DEFAULT_STOPWORDS
        if stopword is not None:
            if isinstance(stopword, str):
                stopword_list += [stopword]
            elif isinstance(stopword, list):
                stopword_list += stopword
            else:
                raise ValueError('stopword must be a string or array of strings')
        return stopword_list

    def _parse_request_data(self):
        """Parse JSON request data with comprehensive error handling.

        This method handles request body parsing with proper validation
        and returns a tuple of (data, error_message) for easy handling.

        Returns:
            tuple: (request_data, error_message) where either data or error_message is None
        """
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length == 0:
            return None, 'Missing request body'

        try:
            post_data = self.rfile.read(content_length)
            # Try to decode as UTF-8, fallback to latin-1 if it fails
            try:
                decoded_data = post_data.decode('utf-8')
            except UnicodeDecodeError:
                decoded_data = post_data.decode('latin-1')
            request_data = json.loads(decoded_data)
            return request_data, None
        except json.JSONDecodeError:
            return None, 'Invalid JSON in request body'

    def _check_admin_auth(self):
        """Check if the request has admin privileges.

        This method validates the Authorization header and checks if the token
        is both valid and marked as admin.

        Returns:
            bool: True if request has admin privileges, False otherwise
        """
        auth_header = self.headers.get('Authorization')
        if not auth_header or not isinstance(auth_header, str) or not auth_header.startswith('Bearer '):
            return False

        token = auth_header[7:].strip()  # Remove 'Bearer ' prefix and trim whitespace
        if not token:
            return False

        if self.token_db and self.token_db.is_valid_token(token):
            return self.token_db.is_admin_token(token)
        return False

    def _check_auth(self):
        """Check Bearer token authentication.

        This method validates the Authorization header and checks if the token
        is valid (but not necessarily admin).

        Returns:
            bool: True if request is authenticated, False otherwise
        """
        auth_header = self.headers.get('Authorization')
        if not auth_header or not isinstance(auth_header, str) or not auth_header.startswith('Bearer '):
            return False

        token = auth_header[7:].strip()  # Remove 'Bearer ' prefix and trim whitespace
        if not token:
            return False

        if self.token_db:
            return self.token_db.is_valid_token(token)
        return False

    def do_OPTIONS(self):
        """Handle CORS preflight requests.

        This method responds to OPTIONS requests with appropriate CORS headers
        to enable cross-origin requests from web browsers.
        """
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        """Handle POST requests to various API endpoints.

        This method routes POST requests to appropriate handler methods
        based on the request path.
        """
        # Parse URL to determine endpoint
        parsed_url = urlparse(self.path)
        endpoint = parsed_url.path

        # Handle different endpoints
        if endpoint == '/token/request':
            return self._handle_token_request()
        elif endpoint == '/token/delete':
            return self._handle_token_delete()
        elif endpoint == '/stats':
            return self._handle_stats_request()
        elif endpoint == '/tokenize':
            return self._handle_text_processing()
        elif endpoint == '/word-frequency':
            return self._handle_word_frequency()
        else:
            # Default text processing endpoint
            self._send_error('Invalid endpoint', 404)

    def _handle_text_processing(self):
        """Handle text processing requests.

        This endpoint supports tokenization and other NLP tasks with
        optional stopword filtering and language specification.
        """
        # Check authentication
        if not self._check_auth():
            self._send_error('Unauthorized: Invalid or missing Bearer token', 401)
            return

        # Parse request
        request_data, error = self._parse_request_data()
        if error:
            self._send_error(error)
            return

        # Extract parameters
        text = request_data.get('text')
        tasks = request_data.get('tasks')
        can_duplicate = request_data.get('can_duplicate')
        skip_tasks = request_data.get('skip_tasks')
        language = request_data.get('language')
        stopword = request_data.get('stopword')  # Optional parameter for custom stopwords

        if not text:
            self._send_error('Missing "text" parameter')
            return

        # Get token for statistics
        auth_header = self.headers.get('Authorization')
        token = auth_header[7:] if auth_header and auth_header.startswith('Bearer ') else None

        # Submit task to queue
        task_id = self.task_queue.submit(
            self._process_text_with_stats,
            text=text,
            tasks=tasks,
            can_duplicate=can_duplicate, 
            skip_tasks=skip_tasks,
            language=language,
            token=token,
            stopword=stopword
        )

        # Wait for result with timeout
        result = self.task_queue.wait_for_result(task_id)

        if result['status'] == 'completed':
            self._send_response(result['result'])
        elif result['status'] == 'timeout':
            self._send_error('Request timeout: Processing took too long', 400)
        else:
            self._send_error(f'Processing error: {result["error"]}', 500)

    def _handle_word_frequency(self):
        """Handle word frequency counting requests.

        This endpoint calculates word frequencies in the provided text,
        with options for maximum words and custom stopwords.
        """
        # Check authentication
        if not self._check_auth():
            self._send_error('Unauthorized: Invalid or missing Bearer token', 401)
            return

        # Parse request
        request_data, error = self._parse_request_data()
        if error:
            self._send_error(error)
            return

        text = request_data.get('text')
        max_words = request_data.get('max_words', 100)  # Default to 100 words
        stopword = request_data.get('stopword')  # Optional parameter for custom stopwords

        if not text:
            self._send_error('Missing "text" parameter')
            return

        if not isinstance(max_words, int) or max_words < 1:
            self._send_error('max_words must be a positive integer')
            return

        # Get token for statistics
        auth_header = self.headers.get('Authorization')
        token = auth_header[7:] if auth_header and auth_header.startswith('Bearer ') else None

        # Submit task to queue
        task_id = self.task_queue.submit(
            self._process_word_frequency,
            text=text,
            max_words=max_words,
            token=token,
            stopword=stopword
        )

        # Wait for result with timeout
        result = self.task_queue.wait_for_result(task_id)

        if result['status'] == 'completed':
            self._send_response(result['result'])
        elif result['status'] == 'timeout':
            self._send_error('Request timeout: Processing took too long', 400)
        else:
            self._send_error(f'Processing error: {result["error"]}', 500)

    def _handle_token_request(self):
        """Handle token request endpoint (admin only).

        This endpoint allows admin users to request new tokens for other users.
        If the user already has tokens, they are invalidated.
        """
        # Check admin authentication
        if not self._check_admin_auth():
            self._send_error('Unauthorized: Admin privileges required', 401)
            return

        # Parse request
        request_data, error = self._parse_request_data()
        if error:
            self._send_error(error)
            return

        user_id = request_data.get('user_id')
        if not user_id:
            self._send_error('Missing "user_id" parameter')
            return

        # Generate a new token
        new_token = str(uuid.uuid4())

        # Check if user already has tokens and invalidate them
        existing_tokens = self.token_db.get_tokens_by_applicant(user_id)
        reissued = len(existing_tokens) > 0
        if reissued:
            self.token_db.invalidate_tokens_by_applicant(user_id)

        # Add new token to database
        success = self.token_db.add_token(new_token, user_id)
        if success:
            self._send_response({
                'token': new_token,
                'reissued': reissued,
                'message': 'Token issued successfully'
            })
        else:
            self._send_error('Failed to issue token', 500)

    def _handle_token_delete(self):
        """Handle token deletion (admin only).

        This endpoint allows admin users to delete specific tokens.
        """
        # Check admin authentication
        if not self._check_admin_auth():
            self._send_error('Unauthorized: Admin privileges required', 401)
            return

        # Parse request
        request_data, error = self._parse_request_data()
        if error:
            self._send_error(error)
            return

        token_to_delete = request_data.get('token')
        if not token_to_delete:
            self._send_error('Missing "token" parameter')
            return

        # Delete token from database
        success = self.token_db.delete_token(token_to_delete)
        if success:
            self._send_response({
                'message': 'Token deleted successfully'
            })
        else:
            self._send_error('Failed to delete token', 500)

    def _handle_stats_request(self):
        """Handle statistics request (admin only).

        This endpoint returns usage statistics for all tokens.
        """
        # Check admin authentication
        if not self._check_admin_auth():
            self._send_error('Unauthorized: Admin privileges required', 401)
            return

        # Get statistics from database
        stats = self.token_db.get_all_tokens_stats()

        # Format statistics for response
        formatted_stats = []
        for stat in stats:
            formatted_stats.append({
                'token': stat[0],
                'applicant_id': stat[1],
                'created_at': stat[2],
                'usage_count': stat[3],
                'char_count': stat[4],
                'is_valid': bool(stat[5]),
                'is_admin': bool(stat[6])
            })

        self._send_response({
            'stats': formatted_stats
        })

    def _process_text(self, text, can_duplicate = True, tasks=None, skip_tasks=None, language=None, stopword=None):
        """Process text with HanLP model.

        This method applies the HanLP model to perform NLP tasks on the input text.

        Args:
            text (str): Input text to process
            tasks (list): List of tasks to perform (e.g., ['tok', 'pos'])
            skip_tasks (list): List of tasks to skip
            language (str): Language of the text
            stopword: Custom stopwords (string, list, or None)

        Returns:
            dict: Processed results with tokenization and other task results

        Raises:
            Exception: If processing fails
        """
        try:
            # Apply stopword filtering if provided
            stopword_list = self._process_stopwords(stopword)

            # Get tokens
            tokens = self.model(text, tasks=["tok"], skip_tasks=skip_tasks, language=language)
            if isinstance(tokens, dict):
                tok_tokens = tokens.get("tok", [])
            else:
                tok_tokens = tokens

            # Filter out stopwords
            filtered_tokens = [token for token in tok_tokens if token not in stopword_list]

            # Create result with filtered tokens
            result = {}
            if tasks and "tok" in tasks:
                result["tok"] = filtered_tokens if can_duplicate else list(dict.fromkeys(filtered_tokens))
            elif not tasks:  # If no tasks specified, return default tokenization
                result["tok"] = filtered_tokens if can_duplicate else list(dict.fromkeys(filtered_tokens))

            # Process other tasks if specified
            if tasks and "pos" in tasks:
                pos_result = self.model(text, tasks=["pos"], skip_tasks=None, language=language)
                if isinstance(pos_result, dict):
                    result["pos"] = pos_result.get("pos", [])
            if tasks and "ner" in tasks:
                ner_result = self.model(text, tasks=["ner"], skip_tasks=None, language=language)
                if isinstance(ner_result, dict):
                    result["ner"] = ner_result.get("ner", [])

            # Convert Document to dict for JSON serialization
            if isinstance(result, Document):
                return result.to_dict()
            return result
        except Exception as e:
            raise Exception(f"Processing failed: {str(e)}")

    def _process_text_with_stats(self, text, can_duplicate = True, tasks=None, skip_tasks=None, language=None, token=None, stopword=None):
        """Process text with HanLP model and update usage statistics.

        This is a wrapper around _process_text that also updates usage statistics
        if a valid token is provided.

        Args:
            text (str): Input text to process
            tasks (list): List of tasks to perform
            skip_tasks (list): List of tasks to skip
            language (str): Language of the text
            token (str): Authentication token for usage tracking
            stopword: Custom stopwords (string, list, or None)

        Returns:
            dict: Processed results

        Raises:
            Exception: If processing fails
        """
        try:
            result = self._process_text(text, can_duplicate=can_duplicate, tasks=tasks, skip_tasks=skip_tasks, language=language, stopword=stopword)

            # Update usage statistics if token is provided
            if token and self.token_db:
                self.token_db.add_token_usage(token, len(text))

            return result
        except Exception as e:
            raise Exception(f"Processing failed: {str(e)}")

    def _process_word_frequency(self, text, max_words=100, token=None, stopword=None):
        """Process word frequency counting and update usage statistics.

        This method counts word frequencies in the input text and returns
        the most common words.

        Args:
            text (str): Input text to analyze
            max_words (int): Maximum number of words to return (default: 100)
            token (str): Authentication token for usage tracking
            stopword: Custom stopwords (string, list, or None)

        Returns:
            dict: Word frequency results with "word_frequency" key

        Raises:
            Exception: If processing fails
        """
        try:
            # Apply stopword filtering if provided
            stopword_list = self._process_stopwords(stopword)

            # Tokenize text
            # Use HanLP tokenizer to get tokens
            tokens = self.model(text, tasks=["tok"], skip_tasks=None, language=None)
            if isinstance(tokens, dict):
                tok_tokens = tokens.get("tok", [])
            else:
                tok_tokens = tokens

            # Filter out stopwords
            filtered_tokens = [token for token in tok_tokens if token not in stopword_list]

            # Count word frequencies
            from collections import Counter
            word_freq = Counter(filtered_tokens)

            # Get top N words
            top_words = word_freq.most_common(max_words)

            # Format response
            result = [
                {"word": word, "count": count}
                for word, count in top_words
            ]

            # Update usage statistics if token is provided
            if token and self.token_db:
                self.token_db.add_token_usage(token, len(text))

            return {"word_frequency": result}
        except Exception as e:
            raise Exception(f"Word frequency calculation failed: {str(e)}")

    def do_GET(self):
        """Handle GET requests.

        This method handles both API requests and documentation requests.
        For API requests, it processes text using query parameters.
        For the root path, it returns API documentation.
        """
        # Parse URL to determine endpoint
        parsed_url = urlparse(self.path)
        endpoint = parsed_url.path
        query_params = parse_qs(parsed_url.query)

        # Handle different endpoints
        if endpoint == '/stats':
            return self._handle_stats_request_get()
        else:
            # Default text processing endpoint
            # Extract parameters
            text_param = query_params.get('text')
            if not text_param or not isinstance(text_param[0], str) or not text_param[0].strip():
                # Show API documentation
                self._send_response({
                    'message': 'HanLP RESTful API Server',
                    'endpoints': {
                        'POST /tokenize': 'Tokenize text with HanLP (supports stopword filtering)',
                        'GET /': 'API documentation',
                        'POST /token/request': 'Request a new token (admin only)',
                        'POST /token/delete': 'Delete a token (admin only)',
                        'POST /stats': 'Get usage statistics (admin only)',
                        'POST /word-frequency': 'Get word frequency count (supports stopword filtering)'
                    },
                    'parameters': {
                        'text': 'Text to process (required)',
                        'tasks': 'Tasks to run (optional)',
                        'skip_tasks': 'Tasks to skip (optional)',
                        'language': 'Language of text (optional)',
                        'stopword': 'Custom stopwords to extend default list (optional)'
                    },
                    'authentication': 'Bearer token required in Authorization header'
                })
                return

            text = text_param[0].strip()
            tasks = query_params.get('tasks')
            skip_tasks = query_params.get('skip_tasks')
            language = query_params.get('language')

            # Check authentication
            if not self._check_auth():
                self._send_error('Unauthorized: Invalid or missing Bearer token', 401)
                return

            # Submit task to queue
            task_id = self.task_queue.submit(
                self._process_text,
                text=text,
                tasks=tasks[0].split(',') if tasks and isinstance(tasks[0], str) else None,
                skip_tasks=skip_tasks[0].split(',') if skip_tasks and isinstance(skip_tasks[0], str) else None,
                language=language[0] if language and isinstance(language[0], str) else None
            )

            # Wait for result with timeout
            result = self.task_queue.wait_for_result(task_id)

            if result['status'] == 'completed':
                self._send_response(result['result'])
            elif result['status'] == 'timeout':
                self._send_error('Request timeout: Processing took too long', 400)
            else:
                self._send_error(f'Processing error: {result["error"]}', 500)

    def _handle_stats_request_get(self):
        """Handle statistics request via GET (admin only).

        This endpoint returns usage statistics for all tokens.
        Includes additional validation to handle potential database inconsistencies.
        """
        # Check admin authentication
        if not self._check_admin_auth():
            self._send_error('Unauthorized: Admin privileges required', 401)
            return

        # Get statistics from database
        try:
            stats = self.token_db.get_all_tokens_stats()
        except Exception as e:
            self._send_error(f'Database error: {str(e)}', 500)
            return

        # Format statistics for response
        formatted_stats = []
        for stat in stats:
            # Validate that stat is a tuple with expected length
            if not isinstance(stat, (tuple, list)) or len(stat) < 7:
                continue  # Skip invalid records
            formatted_stats.append({
                'token': stat[0] if len(stat) > 0 else '',
                'applicant_id': stat[1] if len(stat) > 1 else None,
                'created_at': stat[2] if len(stat) > 2 else None,
                'usage_count': stat[3] if len(stat) > 3 else 0,
                'char_count': stat[4] if len(stat) > 4 else 0,
                'is_valid': bool(stat[5]) if len(stat) > 5 else False,
                'is_admin': bool(stat[6]) if len(stat) > 6 else False
            })

        self._send_response({
            'stats': formatted_stats
        })


class HanLPServer:
    """HanLP RESTful API Server

    This class provides the main server entry point with command-line argument
    parsing and server startup functionality.
    """

    def __init__(self, host='localhost', port=8000, admin_token=None, db_path="tokens.db"):
        """Initialize the server with configuration parameters.

        Args:
            host (str): Host address to bind to (default: 'localhost')
            port (int): Port number to bind to (default: 8000)
            admin_token (str): Admin token for privileged operations
            db_path (str): Path to SQLite database file (default: 'tokens.db')
        """
        self.host = host
        self.port = port
        self.admin_token = admin_token
        self.db_path = db_path
        self.server = None

    def run_ipv6_server(self):
        self.serverv6.serve_forever()

    def start(self):
        """Start the server.

        This method initializes the HanLP model and token database,
        then starts the HTTP server.
        """
        # Initialize model before starting server
        print("Initializing HanLP model...")
        HanLPHandler.initialize_model()
        print("Model initialization completed.")

        # Initialize token database
        from hanlp.server.db import TokenDB
        HanLPHandler.token_db = TokenDB(self.db_path)

        # Set admin token if provided
        HanLPHandler.admin_token = self.admin_token
        if self.admin_token:
            # Add admin token to database if it doesn't exist
            HanLPHandler.token_db.add_token(self.admin_token, 0, is_admin=True)

        if ':' in self.host:
            self.serverv6 = HTTPServerV6((self.host, self.port), HanLPHandler)
            print(f"Starting HanLP RESTful API IPV6 server on [{self.host}]:{self.port}")
            self.host = '0.0.0.0'
        self.server = HTTPServer((self.host, self.port), HanLPHandler) 
        print(f"Starting HanLP RESTful API server on {self.host}:{self.port}")
        print(f"Database: {self.db_path}")
        if self.admin_token:
            print(f"Admin token configured")
        print("Press Ctrl+C to stop the server")

        try:
            if self.serverv6 is not None:
               threading.Thread(target=self.run_ipv6_server, daemon=True).start()

            self.server.serve_forever()

        except KeyboardInterrupt:
            print("\nShutting down server...")
            self.server.shutdown()
            # if self.serverv6 is not None:
            #     self.serverv6.shutdown()

    @classmethod
    def from_args(cls):
        """Create server from command line arguments.

        This class method parses command line arguments and returns a
        configured HanLPServer instance.

        Returns:
            HanLPServer: Configured server instance
        """
        parser = argparse.ArgumentParser(description='HanLP RESTful API Server')
        parser.add_argument('--host', type=str, default='localhost',
                          help='Host to bind to (default: localhost)')
        parser.add_argument('--port', type=int, default=8000,
                          help='Port to bind to (default: 8000)')
        parser.add_argument('--admin-token', type=str,
                          help='Administrator token for privileged operations')
        parser.add_argument('--db-path', type=str, default='tokens.db',
                          help='Path to SQLite database file (default: tokens.db)')

        args = parser.parse_args()

        return cls(host=args.host, port=args.port, admin_token=args.admin_token, db_path=args.db_path)

# import debugpy

def main():
    """Main entry point.

    This function starts the server with debugging enabled on port 5678.
    """
    # debugpy.listen(('0.0.0.0', 5678))
    server = HanLPServer.from_args()
    server.start()


if __name__ == '__main__':
    main()