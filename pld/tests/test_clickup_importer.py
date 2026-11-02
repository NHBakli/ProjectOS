"""Tests de l'import ClickUp → Plane face à un faux Plane local. Aucun accès réseau externe."""
import datetime as dt
import io
import json
import re
import sys
import tempfile
import threading
import unittest
import uuid
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import clickup_importer as ci  # noqa: E402

AUJOURD_HUI = dt.date(2026, 11, 2)
ESPACE, PROJET = "flowly", "11111111-2222-3333-4444-555555555555"


def ms(jour):
    return str(int(dt.datetime.fromisoformat(jour + "T12:00:00+00:00").timestamp() * 1000))


def tache(id_, nom, parent=None, statut="complete", typ="closed", **extra):
    t = {"id": id_, "name": nom, "status": {"status": statut, "type": typ}, "parent": parent,
         "top_level_parent": parent, "orderindex": "1", "tags": [], "priority": None,
         "assignees": [{"id": 7, "email": "secret@exemple.fr"}], "text_content": f"Texte de {nom}"}
    t.update(extra)
    return t


EXTRACTION = {"taches": [
    tache("S1", "Sprint N°1", start_date=ms("2026-09-15"), due_date=ms("2026-10-02")),
    tache("S2", "Sprint N°2", statut="to do", typ="open", start_date=ms("2026-10-02"), due_date=ms("2026-10-23")),
    tache("a", "Écran de focus", "S1", date_done=ms("2026-10-05"), tags=[{"name": "inchangeable"}],
          priority={"priority": "urgent"}),
    tache("b", "API de session <b>", "S1", date_done=ms("2026-10-05")),
    tache("c", "Pauses Pomodoro", "S2", statut="to do", typ="open",
          start_date=ms("2026-10-10"), due_date=ms("2026-10-01")),  # début après l'échéance
]}

TABLE = {
    "fin_cycle_en_cours": "2026-11-13",
    "taches": [
        {"clickup_id": "a", "issues": ["Frontend#5"]},
        {"clickup_id": "b", "issues": ["Backend#4", "Backend#5"], "a_verifier": True},
        {"clickup_id": "c", "issues": []},
    ],
}


class FauxPlane(BaseHTTPRequestHandler):
    """Reproduit les règles de Plane v1.4.2 utiles à l'import (409, cycles terminés, liens en double)."""

    def log_message(self, *a):
        pass

    @classmethod
    def reinitialiser(cls):
        cls.appels, cls.tickets, cls.liens, cls.cycles, cls.membres = [], {}, {}, {}, {}
        cls.refus_429 = 1
        cls.etats = [{"id": "e-todo", "group": "unstarted", "sequence": 25000},
                     {"id": "e-backlog", "group": "backlog", "sequence": 15000},
                     {"id": "e-done", "group": "completed", "sequence": 45000},
                     {"id": "e-done2", "group": "completed", "sequence": 50000}]

    def _send(self, code, obj=None, headers=None):
        body = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _corps(self):
        n = int(self.headers.get("Content-Length") or 0)
        return json.loads(self.rfile.read(n)) if n else None

    def _page(self, elements):
        self._send(200, {"results": elements, "next_page_results": False, "next_cursor": None})

    @staticmethod
    def termine(cycle):
        return cycle["end_date"][:10] < AUJOURD_HUI.isoformat()

    def _traiter(self, methode):
        corps = self._corps()
        chemin = urlparse(self.path).path
        FauxPlane.appels.append((methode, chemin, corps))
        if self.headers.get("X-Api-Key") != "cle-de-test":
            return self._send(401, {"detail": "invalid"})
        if FauxPlane.refus_429:
            FauxPlane.refus_429 -= 1
            return self._send(429, {"detail": "throttled"}, {"Retry-After": "1"})
        prefixe = f"/api/v1/workspaces/{ESPACE}/projects/{PROJET}"
        if not chemin.startswith(prefixe):
            return self._send(404, {"error": "not found"})
        r = chemin[len(prefixe):]
        T, C = FauxPlane.tickets, FauxPlane.cycles

        if methode == "GET" and r == "/":
            return self._send(200, {"name": "Flowly", "identifier": "FLOW", "cycle_view": True, "timezone": "UTC"})
        if methode == "GET" and r == "/states/":
            return self._page(FauxPlane.etats)
        if r == "/work-items/":
            if methode == "GET":
                return self._page(list(T.values()))
            for t in T.values():
                if (t["external_source"], t["external_id"]) == (corps["external_source"], corps["external_id"]):
                    return self._send(409, {"error": "exists", "id": t["id"]})
            t = dict(corps, id=str(uuid.uuid4()))
            T[t["id"]] = t
            return self._send(201, t)
        m = re.fullmatch(r"/work-items/([^/]+)/links/", r)
        if m:
            liens = FauxPlane.liens.setdefault(m.group(1), [])
            if methode == "GET":
                return self._page(liens)
            if any(l["url"] == corps["url"] for l in liens):
                return self._send(400, {"error": "URL already exists for this Issue"})
            liens.append(corps)
            return self._send(201, corps)
        if r == "/cycles/":
            if methode == "GET":
                return self._page(list(C.values()))
            for c in C.values():
                if c["external_id"] == corps["external_id"]:
                    return self._send(409, {"error": "exists", "id": c["id"]})
            c = dict(corps, id=str(uuid.uuid4()))
            C[c["id"]] = c
            return self._send(201, c)
        m = re.fullmatch(r"/cycles/([^/]+)/", r)
        if m:
            c = C[m.group(1)]
            if methode == "GET":
                return self._send(200, c)
            if self.termine(c):
                return self._send(400, {"error": "The Cycle has already been completed so it cannot be edited"})
            c.update(corps)
            return self._send(200, c)
        m = re.fullmatch(r"/cycles/([^/]+)/cycle-issues/", r)
        if m:
            membres = FauxPlane.membres.setdefault(m.group(1), [])
            if methode == "GET":
                return self._page([{"id": i} for i in membres])
            if self.termine(C[m.group(1)]):
                return self._send(400, {"code": "CYCLE_COMPLETED"})
            membres.extend(i for i in corps["issues"] if i not in membres)
            return self._send(200, [])
        return self._send(404, {"error": "route inconnue " + r})

    def do_GET(self):
        self._traiter("GET")

    def do_POST(self):
        self._traiter("POST")

    def do_PATCH(self):
        self._traiter("PATCH")

    def do_DELETE(self):
        self._traiter("DELETE")


class TestPlan(unittest.TestCase):
    def test_cycles_et_tickets(self):
        plan = ci.construire_plan(EXTRACTION, TABLE, AUJOURD_HUI)
        self.assertEqual(plan["erreurs"], [])
        self.assertEqual([(c["nom"], str(c["debut"]), str(c["fin"]), c["en_cours"]) for c in plan["cycles"]],
                         [("Sprint N°1", "2026-09-15", "2026-10-02", False),
                          ("Sprint N°2", "2026-10-02", "2026-11-13", True)])
        a, b, c = plan["tickets"]
        self.assertEqual((a["groupe"], a["priorite"], str(a["termine_le"])), ("completed", "urgent", "2026-10-05"))
        self.assertIn("Terminé le : 2026-10-05", a["description_html"])
        self.assertIn("Tags ClickUp : inchangeable", a["description_html"])
        self.assertIn("&lt;b&gt;", b["description_html"])  # HTML échappé
        self.assertEqual(a["liens"], [{"url": "https://github.com/Flowly-PBS/Frontend/issues/5",
                                       "title": "GitHub Flowly-PBS/Frontend#5"}])
        self.assertEqual((c["groupe"], c["debut"], c["termine_le"]), ("unstarted", None, None))
        self.assertTrue(any("à vérifier" in w for w in plan["avertissements"]))

    def test_erreurs_de_table(self):
        table = {"taches": [{"clickup_id": "a", "issues": ["Front#5"]}, {"clickup_id": "S1"},
                            {"clickup_id": "zz"}, {"clickup_id": "c"}]}
        erreurs = "\n".join(ci.construire_plan(EXTRACTION, table, AUJOURD_HUI)["erreurs"])
        self.assertIn("absente de pld.yml : b", erreurs)
        self.assertIn("absente de l'extraction : zz", erreurs)
        self.assertIn("tâche parente (cycle)", erreurs)
        self.assertIn("Front#5", erreurs)
        self.assertIn("fin_cycle_en_cours", erreurs)  # Sprint 2 dépassé et pas de nouvelle fin

    def test_aucune_donnee_personnelle(self):
        plan = ci.construire_plan(EXTRACTION, TABLE, AUJOURD_HUI)
        self.assertNotIn("secret@exemple.fr", json.dumps(plan, default=str))


class TestImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = HTTPServer(("127.0.0.1", 0), FauxPlane)
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()
        cls.url = f"http://127.0.0.1:{cls.serveur.server_port}"
        ci.attendre = lambda s: None

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def setUp(self):
        FauxPlane.reinitialiser()
        self.dossier = tempfile.TemporaryDirectory()
        d = Path(self.dossier.name)
        (d / "extraction.json").write_text(json.dumps(EXTRACTION))
        cfg = {"plane": {"url": self.url, "espace": ESPACE, "projet_id": PROJET},
               "clickup_import": dict(TABLE, fichier=str(d / "extraction.json"))}
        (d / "pld.yml").write_text(ci.yaml.safe_dump(cfg, allow_unicode=True))
        self.config = d / "pld.yml"

    def tearDown(self):
        self.dossier.cleanup()

    def lancer(self, *options):
        out, err = io.StringIO(), io.StringIO()
        ci.os.environ["PLANE_API_KEY"] = "cle-de-test"
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = ci.main(["--config", str(self.config), *options], aujourd_hui=AUJOURD_HUI)
        finally:
            del ci.os.environ["PLANE_API_KEY"]
        return code, out.getvalue(), err.getvalue()

    def test_plan_hors_ligne_sans_requete(self):
        code, out, _ = self.lancer("--plan")
        self.assertEqual(code, 0)
        self.assertIn("2 cycles, 3 tickets, 3 liens GitHub", out)
        self.assertEqual(FauxPlane.appels, [])

    def test_essai_a_blanc_lecture_seule(self):
        code, out, _ = self.lancer()
        self.assertEqual(code, 0)
        self.assertEqual({m for m, _, _ in FauxPlane.appels}, {"GET"})
        self.assertIn("Ticket à créer : Écran de focus", out)
        self.assertIn("Cycle à créer : Sprint N°1", out)
        self.assertEqual(FauxPlane.tickets, {})

    def test_import_puis_relance_idempotente(self):
        code, out, err = self.lancer("--appliquer", "--oui")
        self.assertEqual(code, 0, err)
        self.assertIn("3 ticket(s), 3 lien(s), 2 cycle(s) créés", out)

        tickets = {t["external_id"]: t for t in FauxPlane.tickets.values()}
        for t in tickets.values():
            self.assertEqual(t["external_source"], "clickup")
            self.assertNotIn("labels", t)       # pas d'étiquette d'équipe : n8n ne crée rien
            self.assertNotIn("assignees", t)
        self.assertEqual(tickets["a"]["state"], "e-done")   # 1er état du groupe terminé
        self.assertEqual(tickets["c"]["state"], "e-todo")
        self.assertEqual(tickets["c"].get("target_date"), "2026-10-01")
        self.assertNotIn("start_date", tickets["c"])
        self.assertEqual([l["title"] for l in FauxPlane.liens[tickets["b"]["id"]]],
                         ["GitHub Flowly-PBS/Backend#4", "GitHub Flowly-PBS/Backend#5"])

        cycles = {c["external_id"]: c for c in FauxPlane.cycles.values()}
        s1, s2 = cycles["S1"], cycles["S2"]
        self.assertEqual((s1["start_date"][:10], s1["end_date"][:10]), ("2026-09-15", "2026-10-02"))
        self.assertEqual(s2["end_date"][:10], "2026-11-13")
        self.assertCountEqual(FauxPlane.membres[s1["id"]], [tickets["a"]["id"], tickets["b"]["id"]])
        self.assertEqual(FauxPlane.membres[s2["id"]], [tickets["c"]["id"]])
        # Sprint 1 créé avec une fin future, tickets ajoutés, puis vraies dates.
        creation = next(c for m, p, c in FauxPlane.appels if m == "POST" and p.endswith("/cycles/")
                        and c["external_id"] == "S1")
        self.assertGreater(creation["end_date"][:10], AUJOURD_HUI.isoformat())

        FauxPlane.appels.clear()
        code, out, _ = self.lancer("--appliquer", "--oui")
        self.assertEqual(code, 0)
        self.assertIn("Rien à faire", out)
        self.assertEqual({m for m, _, _ in FauxPlane.appels}, {"GET"})

    def test_cycle_deja_termine_incomplet(self):
        FauxPlane.cycles["x"] = {"id": "x", "name": "Sprint N°1", "external_source": "clickup",
                                 "external_id": "S1", "start_date": "2026-09-15T00:00:00Z",
                                 "end_date": "2026-10-02T00:00:00Z"}
        code, _, err = self.lancer("--appliquer", "--oui")
        self.assertEqual(code, 1)
        self.assertIn("déjà terminé dans Plane", err)
        self.assertEqual(FauxPlane.tickets, {})  # arrêté dès l'essai à blanc

    def test_mauvaise_cle(self):
        out, err = io.StringIO(), io.StringIO()
        ci.os.environ["PLANE_API_KEY"] = "fausse"
        try:
            with redirect_stdout(out), redirect_stderr(err):
                code = ci.main(["--config", str(self.config)], aujourd_hui=AUJOURD_HUI)
        finally:
            del ci.os.environ["PLANE_API_KEY"]
        self.assertEqual(code, 1)
        self.assertIn("Accès refusé", err.getvalue())


if __name__ == "__main__":
    unittest.main()
