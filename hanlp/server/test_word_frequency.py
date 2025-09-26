# -*- coding:utf-8 -*-
"""
Test script for word-frequency endpoint with async queue processing
"""

import requests
import json
import time

def test_word_frequency():
    """Test the word-frequency endpoint"""

    # Server configuration
    server_url = "http://localhost:8000"
    admin_token = "test-admin-token"

    print("Testing word-frequency endpoint with async queue processing...")

    # First, request a user token using admin token
    print("\n1. Requesting user token...")
    admin_headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }

    token_request_data = {
        "user_id": 12345
    }

    response = requests.post(f"{server_url}/token/request", headers=admin_headers, json=token_request_data)
    if response.status_code == 200:
        token_response = response.json()
        test_token = token_response["token"]
        print(f"Successfully obtained token: {test_token}")
    else:
        print(f"Failed to get token. Status code: {response.status_code}")
        print(f"Error: {response.text}")
        return

    # Test word frequency endpoint
    print("\n2. Testing word frequency endpoint...")
    headers = {
        "Authorization": f"Bearer {test_token}",
        "Content-Type": "application/json"
    }

    word_freq_data = {
        "text": "HanLP是一个强大的自然语言处理工具包，支持多种语言和任务。HanLP可以进行分词、词性标注、命名实体识别等任务。",
        "max_words": 10
    }

    response = requests.post(f"{server_url}/word-frequency", headers=headers, json=word_freq_data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Word frequency response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")

if __name__ == "__main__":
    test_word_frequency()