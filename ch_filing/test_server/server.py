import http.server
import socketserver
import socket
import threading
import time
from typing import Optional
from .handlers import RequestHandler
from .data import TestData

class TestServer:
    def __init__(self, 
                 port: int = 8080,
                 presenter_id: str = "TEST_PRESENTER",
                 authentication: str = "TEST_AUTH",
                 company_auth_code: str = "TEST1234",
                 fail_auth: bool = False,
                 delay: float = 0.0):
        self.port = port
        self.presenter_id = presenter_id
        self.authentication = authentication
        self.company_auth_code = company_auth_code
        self.fail_auth = fail_auth
        self.delay = delay
        self.data = TestData()
        self.server: Optional[socketserver.TCPServer] = None
        self.thread: Optional[threading.Thread] = None
        
    def start(self):
        """Start the test server in a background thread"""
        handler = self._create_handler()
        
        # Create a custom TCP server with SO_REUSEADDR set before bind
        class ReuseAddrTCPServer(socketserver.TCPServer):
            allow_reuse_address = True
            
        self.server = ReuseAddrTCPServer(("", self.port), handler)
        
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
        # Give the server a moment to start
        time.sleep(0.1)
        
    def stop(self):
        """Stop the test server"""
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join()
            
    def _create_handler(self):
        """Create a handler class with access to server config"""
        server_config = self
        
        class ConfiguredHandler(RequestHandler):
            def __init__(self, *args, **kwargs):
                self.config = server_config
                super().__init__(*args, **kwargs)
                
        return ConfiguredHandler
        
    def get_url(self):
        """Get the URL for this test server"""
        return f"http://localhost:{self.port}/v1-0/xmlgw/Gateway"
        
    def reset(self):
        """Reset the test data"""
        self.data.reset()
        
    def __enter__(self):
        """Context manager support"""
        self.start()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup"""
        self.stop()