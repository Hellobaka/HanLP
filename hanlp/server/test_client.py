# -*- coding:utf-8 -*-
# Author: Claude Code
# Date: 2025-09-25
"""
Test script for HanLP RESTful API Server
"""

import requests
import json
import threading
import time

def test_server():
    """Test the HanLP RESTful API server"""

    # Server configuration
    server_url = "http://localhost:8000"
    auth_token = "test-token"

    # Test text
    test_text = "HanLP是一个强大的自然语言处理工具包，支持多种语言和任务。"

    # Test POST request
    print("Testing POST request...")
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    data = {
        "text": test_text,
        "tasks": ["tok", "pos"]
    }

    try:
        response = requests.post(server_url, headers=headers, json=data)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("Response:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

    # Test GET request
    print("\nTesting GET request...")
    params = {
        "text": test_text,
        "tasks": "tok,pos"
    }

    headers = {
        "Authorization": f"Bearer {auth_token}"
    }

    try:
        response = requests.get(server_url, headers=headers, params=params)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print("Response:")
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Error: {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    test_server()