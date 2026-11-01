"""Tests de l'extraction ClickUp face à un faux ClickUp local. Aucun accès réseau externe."""
import io
import json
import os
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import clickup_extraire as ce  # noqa: E402

TOKEN = "pk_faux_token_de_test"


def tache(id_, liste, statut="to do", typ="open", **extra):
    t = {"id": id_, "name": f"Tâche {id_}", "status": {"status": statut, "type": typ},
         "list": {"id": liste}, "assignees": [{"id": 1, "email": "secret@exemple.fr"}],
         "tags": [{"name": "front"}], "custom_fields": [], "parent": None}
    t.update(extra)
    return t


# Espace 10 : dossier « Sprints » (liste 100 active, liste 101 archivée), liste hors dossier 200.
TACHES = {
    ("100", "false"): [tache(f"a{i}", "100") for i in range(150)],  # 2 pages
    ("101", "true"): [tache("b1", "101", "done", "closed", date_closed="1760000000000", points=2)],
    ("200", "false"): [tache("c1", "200", start_date="1759000000000"), tache("a0", "200")],  # a0 en double
}


class FauxClickUp(BaseHTTPRequestHandler):
    appels = []
    refus_429 = 1  # premier appel /team refusé une fois

    def log_message(self, *a):
        pass

    def _send(self, code, obj, headers=None):
        body = json.dumps(obj).encode()
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        FauxClickUp.appels.append(("POST", self.path))
        self._send(405, {})

    do_PUT = do_DELETE = do_PATCH = do_POST

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        FauxClickUp.appels.append(("GET", u.path))
        if self.headers.get("Authorization") != TOKEN:
            return self._send(401, {"err": "Token invalid"})
        p = u.path.removeprefix("/api/v2")
        if p == "/team":
            if FauxClickUp.refus_429:
                FauxClickUp.refus_429 -= 1
                return self._send(429, {}, {"X-RateLimit-Reset": "0"})
            return self._send(200, {"teams": [{"id": "9", "name": "Flowly", "members": []}]})
        if p == "/team/9/space":
            return self._send(200, {"spaces": [{"id": "10", "name": "Dev"}]})
        if p == "/space/10/folder":
            return self._send(200, {"folders": [{"id": "50", "name": "Sprints"}] if q["archived"] == "false" else []})
        if p == "/folder/50/list":
            if q["archived"] == "false":
                return self._send(200, {"lists": [{"id": "100", "name": "Sprint 1", "start_date": "1758000000000",
                                                   "due_date": "1759200000000"}]})
            return self._send(200, {"lists": [{"id": "101", "name": "Sprint 0", "archived": True}]})
        if p == "/space/10/list":
            return self._send(200, {"lists": [{"id": "200", "name": "Backlog"}] if q["archived"] == "false" else []})
        if p.startswith("/list/") and p.endswith("/task"):
            assert q["include_closed"] == "true" and q["subtasks"] == "true"
            tout = TACHES.get((p.split("/")[2], q["archived"]), [])
            page = int(q["page"])
            lot = tout[page * 100:(page + 1) * 100]
            return self._send(200, {"tasks": lot, "last_page": (page + 1) * 100 >= len(tout)})
        self._send(404, {})


class TestExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = HTTPServer(("127.0.0.1", 0), FauxClickUp)
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()
        ce.API = f"http://127.0.0.1:{cls.serveur.server_port}/api/v2"
        ce.attendre = lambda s: None

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def lancer(self, token, *args):
        os.environ["CLICKUP_TOKEN"] = token
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as d, redirect_stdout(out), redirect_stderr(err):
            code = ce.main(["--sortie", d, *args])
            fichiers = list(Path(d).glob("clickup-*.json"))
            donnees = json.loads(fichiers[0].read_text()) if fichiers else None
            mode = oct(fichiers[0].stat().st_mode & 0o777) if fichiers else None
        return code, out.getvalue(), err.getvalue(), donnees, mode

    def test_extraction_complete(self):
        FauxClickUp.appels.clear()
        code, out, err, d, mode = self.lancer(TOKEN)
        self.assertEqual(code, 0, err)
        ids = [t["id"] for t in d["taches"]]
        self.assertEqual(len(ids), 152)  # 150 + b1 + c1, a0 dédoublonnée
        self.assertEqual(len(set(ids)), len(ids))
        self.assertIn("b1", ids)  # liste archivée lue
        self.assertEqual({l["id"] for l in d["listes"]}, {"100", "101", "200"})
        self.assertEqual(mode, "0o600")
        self.assertTrue(all(m == "GET" for m, _ in FauxClickUp.appels))  # lecture seule
        self.assertIn("Sprint 1 : 2025-09-16 → 2025-09-30, 150 tâches, 0 fermées", out)
        self.assertIn("done [closed] : 1", out)
        self.assertNotIn("secret@exemple.fr", out + err)  # pas d'e-mail dans le résumé
        self.assertNotIn(TOKEN, out + err)

    def test_token_refuse(self):
        code, out, err, d, _ = self.lancer("pk_mauvais")
        self.assertEqual(code, 1)
        self.assertIn("Accès refusé (401)", err)
        self.assertIsNone(d)
        self.assertNotIn("pk_mauvais", out + err)

    def test_equipe_inconnue(self):
        code, _, err, d, _ = self.lancer(TOKEN, "--equipe", "123")
        self.assertEqual(code, 2)
        self.assertIn("--equipe 9", err)
        self.assertIsNone(d)


if __name__ == "__main__":
    unittest.main()
