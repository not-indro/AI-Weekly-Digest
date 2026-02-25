import http.server
import socketserver
import importlib
import sys
import os
import json

PORT = 8000

class VercelHandler(http.server.SimpleHTTPRequestHandler):
    def _handle_api(self):
        # basic route translation: /api/search_section?key=val -> module api.search_section
        base_path = self.path.split('?')[0]
        if base_path.startswith('/api/'):
            mod_name = base_path[5:] 
            try:
                mod = importlib.import_module(f"api.{mod_name}")
                # The vercel python runtime uses `handler(BaseHTTPRequestHandler)`
                # We can just instantiate it and let it run
                # But BaseHTTPRequestHandler requires (request, client_address, server) which we pass from self
                handler_instance = mod.handler(self.request, self.client_address, self.server)
                # Call the corresponding method
                if self.command == "GET":
                    handler_instance.do_GET()
                elif self.command == "POST":
                    handler_instance.do_POST()
                elif self.command == "OPTIONS":
                    handler_instance.do_OPTIONS()
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(str(e).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path.startswith('/api/'):
            self._handle_api()
        else:
            # serve files from public by default
            if self.path == '/':
                self.path = '/public/index.html'
            elif not self.path.startswith('/public/'):
                self.path = '/public' + self.path
            super().do_GET()

    def do_POST(self):
        self._handle_api()

    def do_OPTIONS(self):
        self._handle_api()

import os
os.chdir(os.path.dirname(os.path.abspath(__file__)))

with socketserver.TCPServer(("", PORT), VercelHandler) as httpd:
    print("Serving at port", PORT)
    httpd.serve_forever()
