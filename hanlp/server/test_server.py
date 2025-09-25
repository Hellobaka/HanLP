#!/usr/bin/env python
# -*- coding:utf-8 -*-
"""
Test script for HanLP RESTful API Server
"""

import argparse
import threading
import time
import requests
import json

def start_server():
    """Start the HanLP server in a separate thread"""
    from hanlp.server import main
    import sys
    # We won't actually start the server here as it would block
    # Instead, we'll test the server functionality directly
    print("Server module can be imported successfully")

def test_server_functionality():
    """Test the core server functionality"""
    print("Testing server functionality...")

    # Test TaskQueue functionality
    from hanlp.server.server import TaskQueue
    import time

    def slow_function(x):
        time.sleep(1)
        return x * 2

    # Create task queue
    queue = TaskQueue(max_workers=2, timeout=5)

    # Submit tasks
    task_id1 = queue.submit(slow_function, 5)
    task_id2 = queue.submit(slow_function, 10)
    task_id3 = queue.submit(slow_function, 15)  # This should be queued

    # Wait for results
    result1 = queue.wait_for_result(task_id1)
    result2 = queue.wait_for_result(task_id2)
    result3 = queue.wait_for_result(task_id3)

    print(f"Task 1 result: {result1}")
    print(f"Task 2 result: {result2}")
    print(f"Task 3 result: {result3}")

    # Test timeout functionality
    def very_slow_function():
        time.sleep(10)  # Longer than timeout
        return "done"

    task_id4 = queue.submit(very_slow_function)
    result4 = queue.wait_for_result(task_id4)
    print(f"Timeout task result: {result4}")

    print("Server functionality test completed!")

def main():
    parser = argparse.ArgumentParser(description='Test HanLP RESTful API Server')
    parser.add_argument('--functionality', action='store_true',
                       help='Test server functionality')

    args = parser.parse_args()

    if args.functionality:
        test_server_functionality()
    else:
        start_server()

if __name__ == '__main__':
    main()