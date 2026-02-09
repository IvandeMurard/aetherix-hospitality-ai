#!/usr/bin/env python3
"""
Alternative startup script using Python HTTP proxy instead of nginx.
This avoids HuggingFace Spaces issues with nginx and POST requests.
"""
import subprocess
import time
import signal
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import http.client
import threading

# Ports
FASTAPI_PORT = 8000
STREAMLIT_PORT = 8501
PROXY_PORT = 7860

# Process handles
fastapi_process = None
streamlit_process = None


class ProxyHandler(BaseHTTPRequestHandler):
    """HTTP proxy that routes API requests to FastAPI and everything else to Streamlit."""
    
    def log_message(self, format, *args):
        """Override to use print instead of stderr."""
        print(f"[PROXY] {format % args}")
    
    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.send_header('Access-Control-Max-Age', '3600')
        self.end_headers()
    
    def _route_to_fastapi(self):
        """Route request to FastAPI backend."""
        try:
            # Parse request
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            query = parsed_path.query
            
            # Connect to FastAPI
            conn = http.client.HTTPConnection('localhost', FASTAPI_PORT, timeout=300)
            
            # Get request body if present
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            # Forward headers (exclude hop-by-hop headers)
            headers = {}
            for header, value in self.headers.items():
                if header.lower() not in ('host', 'connection', 'proxy-connection'):
                    headers[header] = value
            
            # Build full path with query
            full_path = path
            if query:
                full_path += '?' + query
            
            # Forward request
            conn.request(self.command, full_path, body, headers)
            response = conn.getresponse()
            
            # Forward response
            self.send_response(response.status)
            
            # Forward response headers
            for header, value in response.getheaders():
                if header.lower() not in ('connection', 'transfer-encoding'):
                    self.send_header(header, value)
            
            # Add CORS headers if not present
            if 'access-control-allow-origin' not in [h.lower() for h in response.getheaders()]:
                self.send_header('Access-Control-Allow-Origin', '*')
            
            self.end_headers()
            
            # Forward response body
            self.wfile.write(response.read())
            conn.close()
            
        except Exception as e:
            print(f"[PROXY] Error routing to FastAPI: {e}")
            self.send_error(502, f"Bad Gateway: {e}")
    
    def _route_to_streamlit(self):
        """Route request to Streamlit."""
        try:
            # Parse request
            parsed_path = urlparse(self.path)
            path = parsed_path.path
            query = parsed_path.query
            
            # Connect to Streamlit
            conn = http.client.HTTPConnection('localhost', STREAMLIT_PORT, timeout=60)
            
            # Get request body if present
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else None
            
            # Forward headers
            headers = {}
            for header, value in self.headers.items():
                if header.lower() not in ('host', 'connection', 'proxy-connection'):
                    headers[header] = value
            
            # Build full path with query
            full_path = path
            if query:
                full_path += '?' + query
            
            # Forward request
            conn.request(self.command, full_path, body, headers)
            response = conn.getresponse()
            
            # Forward response
            self.send_response(response.status)
            
            # Forward response headers
            for header, value in response.getheaders():
                if header.lower() not in ('connection', 'transfer-encoding'):
                    self.send_header(header, value)
            
            self.end_headers()
            
            # Forward response body
            self.wfile.write(response.read())
            conn.close()
            
        except Exception as e:
            print(f"[PROXY] Error routing to Streamlit: {e}")
            self.send_error(502, f"Bad Gateway: {e}")
    
    def do_GET(self):
        """Handle GET requests."""
        path = urlparse(self.path).path
        
        # Route API endpoints to FastAPI
        if path.startswith(('/predict', '/api/', '/health', '/diagnostic', '/docs', '/redoc', '/openapi.json', '/test/')):
            self._route_to_fastapi()
        else:
            self._route_to_streamlit()
    
    def do_POST(self):
        """Handle POST requests."""
        path = urlparse(self.path).path
        
        # Route API endpoints to FastAPI
        if path.startswith(('/predict', '/api/')):
            self._route_to_fastapi()
        else:
            self._route_to_streamlit()
    
    def do_PUT(self):
        """Handle PUT requests."""
        path = urlparse(self.path).path
        
        # Route API endpoints to FastAPI
        if path.startswith(('/predict', '/api/')):
            self._route_to_fastapi()
        else:
            self._route_to_streamlit()
    
    def do_DELETE(self):
        """Handle DELETE requests."""
        path = urlparse(self.path).path
        
        # Route API endpoints to FastAPI
        if path.startswith(('/predict', '/api/')):
            self._route_to_fastapi()
        else:
            self._route_to_streamlit()


def start_fastapi():
    """Start FastAPI backend."""
    global fastapi_process
    print("[STARTUP] Starting FastAPI on port 8000...")
    fastapi_process = subprocess.Popen(
        ['uvicorn', 'backend.main:app', '--host', '0.0.0.0', '--port', str(FASTAPI_PORT)],
        cwd='/app'
    )
    print(f"[STARTUP] FastAPI started (PID: {fastapi_process.pid})")
    
    # Wait for FastAPI to be ready
    import requests
    for i in range(10):
        try:
            response = requests.get(f'http://localhost:{FASTAPI_PORT}/health', timeout=2)
            if response.status_code == 200:
                print("[STARTUP] FastAPI health check OK")
                return
        except:
            pass
        time.sleep(1)
    print("[STARTUP] WARNING: FastAPI health check failed")


def start_streamlit():
    """Start Streamlit dashboard."""
    global streamlit_process
    print("[STARTUP] Starting Streamlit on port 8501...")
    streamlit_process = subprocess.Popen(
        ['streamlit', 'run', 'app.py', '--server.address', '0.0.0.0', '--server.port', str(STREAMLIT_PORT)],
        cwd='/app/frontend'
    )
    print(f"[STARTUP] Streamlit started (PID: {streamlit_process.pid})")
    
    # Wait for Streamlit to be ready
    import requests
    for i in range(10):
        try:
            response = requests.get(f'http://localhost:{STREAMLIT_PORT}', timeout=2)
            if response.status_code == 200:
                print("[STARTUP] Streamlit health check OK")
                return
        except:
            pass
        time.sleep(2)
    print("[STARTUP] WARNING: Streamlit health check failed")


def signal_handler(sig, frame):
    """Handle shutdown signals."""
    print("\n[SHUTDOWN] Shutting down services...")
    if fastapi_process:
        fastapi_process.terminate()
    if streamlit_process:
        streamlit_process.terminate()
    sys.exit(0)


def main():
    """Main entry point."""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("[STARTUP] Starting services...")
    
    # Start FastAPI
    start_fastapi()
    time.sleep(2)
    
    # Start Streamlit
    start_streamlit()
    time.sleep(3)
    
    # Start proxy server
    print(f"[STARTUP] Starting Python HTTP proxy on port {PROXY_PORT}...")
    print("[STARTUP] Routing:")
    print("[STARTUP]   - /predict, /api/*, /health -> FastAPI:8000")
    print("[STARTUP]   - /, /_stcore/stream -> Streamlit:8501")
    
    server = HTTPServer(('0.0.0.0', PROXY_PORT), ProxyHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Shutting down...")
        server.shutdown()
        signal_handler(None, None)


if __name__ == '__main__':
    main()
