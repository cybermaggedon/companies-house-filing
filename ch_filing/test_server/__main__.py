#!/usr/bin/env python3

import argparse
import signal
import sys
from .server import TestServer

def main():
    parser = argparse.ArgumentParser(
        description="Test server for Companies House filing API"
    )
    parser.add_argument('--port', '-p', type=int, default=8080,
                        help='Port to listen on (default: 8080)')
    parser.add_argument('--presenter-id', default='TEST_PRESENTER',
                        help='Expected presenter ID (default: TEST_PRESENTER)')
    parser.add_argument('--authentication', default='TEST_AUTH',
                        help='Expected authentication value (default: TEST_AUTH)')
    parser.add_argument('--company-auth-code', default='TEST1234',
                        help='Expected company authentication code (default: TEST1234)')
    parser.add_argument('--fail-auth', action='store_true',
                        help='Always fail authentication checks')
    parser.add_argument('--delay', type=float, default=0.0,
                        help='Add delay (in seconds) to responses')
    
    args = parser.parse_args()
    
    server = TestServer(
        port=args.port,
        presenter_id=args.presenter_id,
        authentication=args.authentication,
        company_auth_code=args.company_auth_code,
        fail_auth=args.fail_auth,
        delay=args.delay
    )
    
    def signal_handler(sig, frame):
        print("\nShutting down test server...")
        server.stop()
        sys.exit(0)
        
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"Starting Companies House test server on port {args.port}")
    print(f"URL: {server.get_url()}")
    print(f"Presenter ID: {args.presenter_id}")
    print(f"Authentication: {args.authentication}")
    print(f"Company Auth Code: {args.company_auth_code}")
    print(f"Fail Auth: {args.fail_auth}")
    print(f"Response Delay: {args.delay}s")
    print("\nPress Ctrl+C to stop")
    
    server.start()
    
    # Keep the main thread alive
    signal.pause()

if __name__ == "__main__":
    main()