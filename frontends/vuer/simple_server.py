import http.server
import socketserver
from pathlib import Path

class VuerFrontendHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        # Serve from the current directory
        super().__init__(*args, directory=str(Path(__file__).parent), **kwargs)
    
    def do_GET(self):
        # Serve custom_index.html as the default page
        if self.path == '/':
            self.path = '/custom_index.html'
        super().do_GET()
    
    def end_headers(self):
        # Add CORS headers
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        super().end_headers()

def serve_frontend(port=3000):
    """Serve the custom Vuer frontend."""
    with socketserver.TCPServer(("", port), VuerFrontendHandler) as httpd:
        print(f"Custom Vuer frontend running at http://localhost:{port}")
        print(f"Backend should be running at ws://localhost:8012")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")

if __name__ == "__main__":
    serve_frontend(3000) 