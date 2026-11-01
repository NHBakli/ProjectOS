#!/usr/bin/env python3
"""Fausses API Plane, GitHub et DeepL pour tester le workflow. Journalise chaque appel."""
import json
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

LOG = sys.argv[1]  # usage : faux-plane-github.py JOURNAL ADRESSE
links = {}  # issue_id -> [url]
counter = {"n": 0}


def log(entry):
    with open(LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


class H(BaseHTTPRequestHandler):
    def _send(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        log({"m": "GET", "p": self.path, "key": self.headers.get("X-Api-Key")})
        if "/links/" in self.path:
            issue = self.path.split("/work-items/")[1].split("/")[0]
            return self._send(200, {"results": [{"url": u} for u in links.get(issue, [])]})
        self._send(404, {})

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        log({"m": "POST", "p": self.path, "body": data,
             "auth": self.headers.get("Authorization"), "key": self.headers.get("X-Api-Key"),
             "accept": self.headers.get("Accept")})
        if "/links/" in self.path:
            issue = self.path.split("/work-items/")[1].split("/")[0]
            links.setdefault(issue, []).append(data["url"])
            return self._send(201, {"id": "lien", **data})
        if self.path.endswith("/issues"):
            counter["n"] += 1
            repo = self.path.split("/")[-2]
            n = counter["n"]
            return self._send(201, {"number": n, "node_id": f"I_node{n}",
                                    "html_url": f"https://github.com/Flowly-PBS/{repo}/issues/{n}"})
        if self.path.endswith("/v2/translate"):
            if any("PANNE" in t for t in data["text"]):
                return self._send(456, {"message": "Quota exceeded"})
            return self._send(200, {"translations": [{"detected_source_language": "FR", "text": "EN: " + t}
                                                     for t in data["text"]]})
        if self.path.endswith("/graphql"):
            if data["variables"]["p"] == "PVT_kwDOD8weaM4BjzeI":  # Mobile : simule l'auto-add
                return self._send(200, {"errors": [{"type": "UNPROCESSABLE",
                                                    "message": "Content already exists in this project"}]})
            return self._send(200, {"data": {"addProjectV2ItemById": {"item": {"id": "PVTI_x"}}}})
        self._send(404, {})

    def log_message(self, *a):
        pass


HTTPServer((sys.argv[2], 8099), H).serve_forever()
