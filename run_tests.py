#!/usr/bin/env python
"""Run database tests with proper setup."""
import subprocess
import sys
import os

def run_tests():
    """Run the test suite."""
    print("Running Stripe Invoice Sync Database Tests...")
    print("=" * 50)
    
    # Set test environment
    os.environ["DATABASE_URL"] = "sqlite:///test_stripe_invoice_sync.db"
    
    # Test commands
    test_commands = [
        # Run all database tests
        ["pytest", "tests/test_db/", "-v"],
        
        # Run with coverage
        ["pytest", "tests/test_db/", "--cov=app.db", "--cov-report=term-missing"],
        
        # Run specific test categories
        ["pytest", "tests/test_db/test_duplicate_detection.py", "-v"],
        ["pytest", "tests/test_db/test_retry_queue.py", "-v"],
        ["pytest", "tests/test_db/test_processing_history.py", "-v"],
    ]
    
    print("\nSelect test to run:")
    print("1. Run all database tests")
    print("2. Run with coverage report")
    print("3. Test duplicate detection only")
    print("4. Test retry queue only")
    print("5. Test processing history only")
    print("6. Run all tests in sequence")
    
    choice = input("\nEnter your choice (1-6): ").strip()
    
    if choice == "6":
        # Run all tests in sequence
        for i, cmd in enumerate(test_commands[:5]):
            print(f"\n{'='*50}")
            print(f"Running test {i+1}/5: {' '.join(cmd)}")
            print(f"{'='*50}")
            subprocess.run(cmd)
    elif choice in ["1", "2", "3", "4", "5"]:
        cmd = test_commands[int(choice) - 1]
        print(f"\nRunning: {' '.join(cmd)}")
        subprocess.run(cmd)
    else:
        print("Invalid choice. Exiting.")
        sys.exit(1)
    
    # Clean up test database
    if os.path.exists("test_stripe_invoice_sync.db"):
        os.remove("test_stripe_invoice_sync.db")
        print("\nTest database cleaned up.")

if __name__ == "__main__":
    run_tests()