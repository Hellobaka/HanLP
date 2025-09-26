# -*- coding:utf-8 -*-
# Author: Claude Code
# Date: 2025-09-25
"""
Test script for HanLP RESTful API Server with new features
"""

import requests
import json
import time

def test_server():
    """Test the HanLP RESTful API server with new features"""

    # Server configuration
    server_url = "http://localhost:8000"
    admin_token = "test-admin-token"

    print("Testing HanLP Server with new features...")

    # 1. Test token request
    print("\n1. Testing token request...")
    request_data = {
        "user_id": 12345
    }

    response = requests.post(f"{server_url}/token/request", json=request_data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        token_response = response.json()
        print("Token request response:")
        print(json.dumps(token_response, indent=2, ensure_ascii=False))
        user_token = token_response["token"]
        reissued = token_response["reissued"]
    else:
        print(f"Error: {response.text}")
        return

    # 2. Test text processing with user token
    print("\n2. Testing text processing with user token...")
    headers = {
        "Authorization": f"Bearer {user_token}",
        "Content-Type": "application/json"
    }

    process_data = {
        "text": "HanLP是一个强大的自然语言处理工具包，支持多种语言和任务。",
        "tasks": ["tok", "pos"]
    }

    response = requests.post(server_url, headers=headers, json=process_data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Text processing response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")

    # 3. Test admin token addition
    print("\n3. Testing admin token addition...")
    admin_headers = {
        "Authorization": f"Bearer {admin_token}",
        "Content-Type": "application/json"
    }

    add_token_data = {
        "token": "new-test-token",
        "applicant_id": 67890,
        "is_admin": False
    }

    response = requests.post(f"{server_url}/token/add", headers=admin_headers, json=add_token_data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Token addition response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")

    # 4. Test text processing with new token
    print("\n4. Testing text processing with new token...")
    new_token_headers = {
        "Authorization": "Bearer new-test-token",
        "Content-Type": "application/json"
    }

    response = requests.post(server_url, headers=new_token_headers, json=process_data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Text processing with new token response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")

    # 5. Test admin token deletion
    print("\n5. Testing admin token deletion...")
    delete_token_data = {
        "token": "new-test-token"
    }

    response = requests.post(f"{server_url}/token/delete", headers=admin_headers, json=delete_token_data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Token deletion response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")

    # 6. Test statistics endpoint
    print("\n6. Testing statistics endpoint...")
    response = requests.post(f"{server_url}/stats", headers=admin_headers)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 200:
        result = response.json()
        print("Statistics response:")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Error: {response.text}")

    # 7. Test that deleted token no longer works
    print("\n7. Testing that deleted token no longer works...")
    response = requests.post(server_url, headers=new_token_headers, json=process_data)
    print(f"Status Code: {response.status_code}")
    if response.status_code == 401:
        print("Correctly rejected deleted token")
    else:
        print(f"Unexpected response: {response.status_code} - {response.text}")

    print("\nAll tests completed!")

if __name__ == "__main__":
    test_server()