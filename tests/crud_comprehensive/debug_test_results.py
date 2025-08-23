#!/usr/bin/env python3
"""
Debug test results from JSON output
"""
import json
import sys

def main():
    try:
        with open('test-results.json', 'r') as f:
            data = json.load(f)
        
        print('Exit code:', data.get('exitcode', 'unknown'))
        print('Duration:', data.get('duration', 'unknown'), 'seconds')
        print('Summary:', data.get('summary', {}))
        print()
        
        # Find error tests
        error_tests = [test for test in data.get('tests', []) if test.get('outcome') == 'error']
        
        if error_tests:
            print(f"Found {len(error_tests)} error test(s):")
            for test in error_tests:
                print(f"\n=== ERROR TEST: {test.get('nodeid', 'unknown')} ===")
                
                # Show setup errors
                setup = test.get('setup', {})
                if 'longrepr' in setup:
                    print("Setup Error:")
                    print(setup['longrepr'][:2000])
                    
                if 'crash' in setup:
                    print("Crash Info:", setup['crash'])
                    
                if 'traceback' in setup:
                    print("Traceback:", setup['traceback'])
        else:
            print("No error tests found")
            
    except FileNotFoundError:
        print("test-results.json not found")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()