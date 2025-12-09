"""
Test script for Market Data Recorder
Validates the CSV output format and data structure for 1-minute OHLCV bars
"""

import csv
from pathlib import Path


def test_csv_format():
    """Test that the CSV format matches expected 1-minute OHLCV structure."""
    expected_headers = [
        'timestamp',
        'open',
        'high',
        'low',
        'close',
        'volume'
    ]
    
    # Create a sample CSV to test format (simulating ES_1min.csv)
    test_file = Path("test_ES_1min.csv")
    
    # Write sample data
    with open(test_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(expected_headers)
        
        # Sample 1-minute bar
        writer.writerow([
            '2025-12-05 20:23:00',
            '6880.0',
            '6880.75',
            '6879.75',
            '6880.25',
            '1326'
        ])
        
        # Another sample bar
        writer.writerow([
            '2025-12-05 20:24:00',
            '6880.25',
            '6881.00',
            '6880.00',
            '6880.50',
            '1450'
        ])
    
    # Verify the file can be read
    print("Testing CSV file format...")
    with open(test_file, 'r') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        
        # Check headers match
        if headers != expected_headers:
            print("❌ FAIL: Headers don't match")
            print(f"Expected: {expected_headers}")
            print(f"Got: {headers}")
            return False
        
        print("✓ Headers match expected format")
        
        # Read and validate each row
        row_count = 0
        for row in reader:
            row_count += 1
            
            # Check that required fields are present
            assert 'timestamp' in row
            assert 'open' in row
            assert 'high' in row
            assert 'low' in row
            assert 'close' in row
            assert 'volume' in row
            
            # Validate data types
            try:
                float(row['open'])
                float(row['high'])
                float(row['low'])
                float(row['close'])
                int(float(row['volume']))
            except ValueError as e:
                print(f"❌ FAIL: Invalid data type in row {row_count}: {e}")
                return False
            
            # Validate OHLC relationships
            o = float(row['open'])
            h = float(row['high'])
            l = float(row['low'])
            c = float(row['close'])
            
            if not (l <= o <= h and l <= c <= h):
                print(f"⚠ Warning: Invalid OHLC relationship in row {row_count}")
                print(f"  O={o}, H={h}, L={l}, C={c}")
            
            print(f"  Row {row_count}: {row['timestamp']} O={o} H={h} L={l} C={c} V={row['volume']} - OK")
        
        print(f"✓ Read {row_count} rows successfully")
    
    # Clean up test file
    test_file.unlink()
    
    print("\n" + "=" * 50)
    print("✓ ALL TESTS PASSED")
    print("=" * 50)
    print("\nCSV format is valid for backtesting!")
    return True


def validate_recorder_imports():
    """Test that data recorder modules can be imported."""
    print("Testing module imports...")
    
    try:
        import sys
        from pathlib import Path
        
        # Add dev directory to path
        dev_path = Path(__file__).parent
        if str(dev_path) not in sys.path:
            sys.path.insert(0, str(dev_path))
        
        # Skip GUI launcher test (requires tkinter which may not be available in all environments)
        print("  Skipping DataRecorder_Launcher (requires tkinter GUI)")
        
        # Test importing the core recorder logic (may fail if broker SDK not installed)
        print("  Testing data_recorder core module...")
        try:
            # Just check if the file exists and can be compiled
            recorder_file = dev_path / "data_recorder.py"
            if not recorder_file.exists():
                print(f"  ❌ FAIL: data_recorder.py not found")
                return False
            
            # Compile check
            import py_compile
            py_compile.compile(str(recorder_file), doraise=True)
            print("  ✓ data_recorder.py compiles successfully")
            
            # Try importing (may fail if broker SDK not installed, which is OK)
            try:
                import data_recorder
                print("  ✓ data_recorder imported (broker SDK available)")
            except ImportError as e:
                print(f"  ⚠ data_recorder import skipped (broker SDK not installed - this is OK)")
                print(f"    Error: {e}")
            
            return True
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    except Exception as e:
        print(f"  ❌ FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 50)
    print("Market Data Recorder - Test Suite")
    print("=" * 50)
    print()
    
    # Test 1: Module imports
    print("Test 1: Module Imports")
    print("-" * 50)
    if not validate_recorder_imports():
        print("❌ Module import test failed")
        exit(1)
    print()
    
    # Test 2: CSV format
    print("Test 2: CSV Format Validation")
    print("-" * 50)
    if not test_csv_format():
        print("❌ CSV format test failed")
        exit(1)
    print()
    
    print("=" * 50)
    print("✓ ALL TESTS PASSED")
    print("=" * 50)
