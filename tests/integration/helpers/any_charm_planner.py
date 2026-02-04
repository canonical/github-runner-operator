import sys
from http.server import BaseHTTPRequestHandler, HTTPServer


def run_server(address):
    server = HTTPServer(server_address=(address, 80), RequestHandlerClass=MockPlannerHandler)
    server.serve_forever()

class MockPlannerHandler(BaseHTTPRequestHandler):
    last_payload = None

    def do_POST(self):
        if self.path.startswith("/api/v1/auth/token/"):
            content_length = int(self.headers["Content-Length"])
            MockPlannerHandler.last_payload = self.rfile.read(content_length)

            self.send_response(200)
            self.end_headers()
            return
        self.send_response(404)
        self.end_headers()

    def do_GET(self):
        if MockPlannerHandler.last_payload is None:
            self.send_response(404)
            self.end_headers()
            return

        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.last_payload)

if __name__ == "__main__":
    run_server(sys.argv[1])
