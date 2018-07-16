import argparse
import glob
import json
import sys
from urllib.parse import unquote
from http.server import SimpleHTTPRequestHandler, HTTPServer
from http import HTTPStatus

"""
This server is very specific and very basic. Ultimately it tries to solve the
the problem of finding out what files are available and their content
but exposing this via HTTP. This way, one container can talk to another
container about what mail/*.eml files were created and their content.

To hack on this locally, run::

    cd mail
    python mailfileserver.py
    # or...
    python mailfileserver.py --bind 0.0.0.0 9898

Now, ask it which *.eml file exist (using httpie)::

    http http://localhost:8000/

Or grep for the contents of one of those files:

    http --check-status http://localhost:8000/grep/Does%20this%20exist

"""


class MyRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        files = glob.glob("*.eml")
        if self.path == "/":
            output = json.dumps({"files": files}).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json;charset=utf-8")
            self.send_header("Content-Length", int(len(output)))
            self.end_headers()
            self.wfile.write(output)
        elif self.path.startswith("/grep/"):
            grep = unquote(self.path).replace("/grep/", "", 1)
            # Search all files for a line containing this string.
            finds = []
            for file in files:
                with open(file) as f:
                    for i, line in enumerate(f):
                        if grep in line:
                            finds.append(f"{i + 1}:{line}")
                            break
            output = json.dumps({
                "matches": finds,
                "grep": grep,
            }).encode("utf-8")
            if finds:
                self.send_response(HTTPStatus.OK)
            else:
                self.send_response(HTTPStatus.NOT_FOUND)
            self.send_header("Content-Type", "application/json;charset=utf-8")
            self.send_header("Content-Length", int(len(output)))
            self.end_headers()
            self.wfile.write(output)
        elif self.path.startswith("/debug"):
            all_files = {}
            for file in files:
                with open(file) as f:
                    all_files[file] = f.read()
            output = json.dumps({"all": all_files}).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json;charset=utf-8")
            self.send_header("Content-Length", int(len(output)))
            self.end_headers()
            self.wfile.write(output)
        else:
            super().do_GET()


def run(port, bind, klass=MyRequestHandler, protocol="HTTP/1.0"):
    server_address = (bind, port)

    klass.protocol_version = protocol
    with HTTPServer(server_address, klass) as httpd:
        host, port = httpd.socket.getsockname()
        print(
            f"Serving HTTP on {host} port {port} (http://{host}:{port}/) ..."
        )
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nKeyboard interrupt received, exiting.")
            return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--bind",
        "-b",
        default="",
        metavar="ADDRESS",
        help="Specify alternate bind address " "[default: all interfaces]",
    )
    parser.add_argument(
        "port",
        action="store",
        default=8000,
        type=int,
        nargs="?",
        help="Specify alternate port [default: 8000]",
    )
    args = parser.parse_args()
    sys.exit(run(args.port, args.bind))
