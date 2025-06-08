#!/usr/bin/env python
"""Test script to verify database implementation and duplicate detection."""
import asyncio
import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health_check():
    """Test health endpoint with database status."""
    print("Testing health check...")
    response = requests.get(f"{BASE_URL}/health")
    data = response.json()
    
    print(f"Status: {response.status_code}")
    print(f"Database: {data.get('database', {}).get('status', 'unknown')}")
    print(f"Database Type: {data.get('database', {}).get('type', 'unknown')}")
    print(f"Providers: {list(data.get('providers', {}).keys())}")
    print()

def test_duplicate_detection():
    """Test duplicate invoice detection."""
    print("Testing duplicate detection...")
    
    # Test invoice data
    test_invoice = {
        "source_type": "stripe_charge",
        "source_id": "ch_test_duplicate_123",
        "provider": "anaf",
        "customer_tax_id": "RO12345678",
        "metadata": {
            "test": "duplicate_detection"
        }
    }
    
    # First request - should process
    print("1. Sending first request...")
    response1 = requests.post(f"{BASE_URL}/api/invoices/process", json=test_invoice)
    
    if response1.status_code == 200:
        data1 = response1.json()
        print(f"   Status: {data1['status']}")
        print(f"   Message: {data1['message']}")
    else:
        print(f"   Error: {response1.status_code} - {response1.text}")
    
    # Wait a moment
    time.sleep(1)
    
    # Second request with same data - should detect duplicate
    print("\n2. Sending duplicate request...")
    response2 = requests.post(f"{BASE_URL}/api/invoices/process", json=test_invoice)
    
    if response2.status_code == 200:
        data2 = response2.json()
        print(f"   Status: {data2['status']}")
        print(f"   Message: {data2['message']}")
        
        # Check if duplicate was detected
        if "already processed" in data2.get('message', '').lower():
            print("   ✓ Duplicate detection working!")
        else:
            print("   ✗ Duplicate not detected")
    else:
        print(f"   Error: {response2.status_code} - {response2.text}")
    print()

def test_invoice_history():
    """Test invoice history retrieval."""
    print("Testing invoice history...")
    
    # Get history for the test invoice
    stripe_id = "ch_test_duplicate_123"
    response = requests.get(f"{BASE_URL}/api/invoices/history/{stripe_id}")
    
    if response.status_code == 200:
        data = response.json()
        invoices = data.get('invoices', [])
        
        if invoices:
            print(f"Found {len(invoices)} invoice(s) for {stripe_id}")
            for inv in invoices:
                invoice_info = inv.get('invoice', {})
                print(f"  - Provider: {invoice_info.get('provider')}")
                print(f"    Status: {invoice_info.get('status')}")
                print(f"    Attempts: {invoice_info.get('attempts')}")
                print(f"    History entries: {len(inv.get('history', []))}")
        else:
            print("No invoices found in history")
    else:
        print(f"Error: {response.status_code} - {response.text}")
    print()

def test_statistics():
    """Test processing statistics."""
    print("Testing processing statistics...")
    
    response = requests.get(f"{BASE_URL}/api/invoices/statistics")
    
    if response.status_code == 200:
        stats = response.json()
        print(f"Total invoices: {stats.get('total', 0)}")
        print(f"Completed: {stats.get('completed', 0)}")
        print(f"Failed: {stats.get('failed', 0)}")
        print(f"Pending: {stats.get('pending', 0)}")
        print(f"Success rate: {stats.get('success_rate', 0)}%")
        print(f"Average attempts: {stats.get('average_attempts', 0)}")
    else:
        print(f"Error: {response.status_code} - {response.text}")
    print()

def test_batch_processing():
    """Test batch processing with duplicate detection."""
    print("Testing batch processing...")
    
    batch_request = {
        "provider": "anaf",
        "async_processing": False,
        "invoices": [
            {
                "source_type": "stripe_charge",
                "source_id": "ch_test_batch_001",
                "customer_tax_id": "RO12345678"
            },
            {
                "source_type": "stripe_charge",
                "source_id": "ch_test_batch_002",
                "customer_tax_id": "RO87654321"
            },
            {
                "source_type": "stripe_charge",
                "source_id": "ch_test_duplicate_123",  # This should be detected as duplicate
                "customer_tax_id": "RO12345678"
            }
        ]
    }
    
    response = requests.post(f"{BASE_URL}/api/invoices/process/batch", json=batch_request)
    
    if response.status_code == 200:
        results = response.json()
        print(f"Processed {len(results)} invoices:")
        
        for result in results:
            print(f"  - {result['source_id']}: {result['status']}")
            if "already processed" in result.get('message', '').lower():
                print(f"    (Duplicate detected)")
    else:
        print(f"Error: {response.status_code} - {response.text}")
    print()

def main():
    """Run all tests."""
    print("=== Database Implementation Tests ===\n")
    
    # Check if server is running
    try:
        requests.get(BASE_URL, timeout=2)
    except requests.exceptions.ConnectionError:
        print("Error: Server is not running. Please start the FastAPI application first.")
        return
    
    # Run tests
    test_health_check()
    test_duplicate_detection()
    test_invoice_history()
    test_statistics()
    test_batch_processing()
    
    print("\n=== Tests Complete ===")

if __name__ == "__main__":
    main()