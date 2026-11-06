"""Tests de la lecture de Plane (étape 2) face à un faux Plane local. Aucun accès réseau externe."""
import datetime as dt
import io
import json
import os
import stat
import sys
import tempfile
import threading
import unittest
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from unittest import mock
from urllib.parse import parse_qs, urlparse

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
import config as cm  # noqa: E402
import generer_pld as gp  # noqa: E402
import source_plane as sp  # noqa: E402

ESPACE, PROJET = "flowly", "11111111-2222-3333-4444-555555555555"
CLE = "cle-de-lecture"
MAINTENANT = dt.datetime(2026, 11, 6, 12, 0, tzinfo=dt.timezone.utc)

FICHE_HTML = (
    "<p>En tant que : utilisateur de Flowly</p><p>Je veux : démarrer une session</p>"
    "<p>Afin de : rester concentré</p><p>Definition of Done :</p>"
    "<ul><li><p>bouton Démarrer</p></li><li><p>tests</p></li></ul><p>Points bloquants : aucun</p>"
)


def ticket(id_, seq, nom, etat="e-done", **extra):
    t = {"id": id_, "sequence_id": seq, "name": nom, "state": etat, "parent": None, "start_date": None,
         "target_date": None, "completed_at": None, "estimate_point": None, "labels": [], "assignees": [],
         "external_source": None, "external_id": None, "description_html": "<p></p>"}
    t.update(extra)
    return t


TICKETS = [
    ticket("p1", 1, "Sprint N°1", external_source="clickup", external_id="S1"),
    ticket("t1", 2, "Écran de focus", parent="p1", start_date="2026-09-15", target_date="2026-10-02",
           external_source="clickup", external_id="a", completed_at="2026-11-02T20:10:00Z",
           description_html="<p>Texte</p><p><em>Repris de ClickUp (tâche a).</em></p><p>Terminé le : 2026-10-01</p>"),
    ticket("t2", 3, "API de session", parent="p1", completed_at="2026-10-20T23:30:00Z", labels=["l-back"]),
    ticket("t3", 4, "Pauses Pomodoro", etat="e-todo", estimate_point="pt-2", assignees=["u1"],
           start_date="2026-11-10", target_date="2026-11-14", description_html=FICHE_HTML),
    ticket("t4", 5, "Hors période", etat="e-todo", start_date="2026-01-05", target_date="2026-01-09"),
]
LIENS = {
    "t1": [{"url": "https://github.com/Flowly-PBS/Frontend/issues/5", "title": "GitHub Flowly-PBS/Frontend#5"}],
    "t2": [{"url": "https://github.com/Flowly-PBS/Backend/issues/4", "title": "x"},
           {"url": "https://github.com/Flowly-PBS/Backend/issues/4/", "title": "doublon"},
           {"url": "https://github.com/autre-org/Backend/issues/9", "title": "autre organisation"},
           {"url": "https://figma.com/maquette", "title": "maquette"}],
}
CYCLES = [
    {"id": "c2", "name": "Sprint N°2", "start_date": "2026-10-01T22:00:00Z", "end_date": "2026-10-22T22:00:00Z"},
    {"id": "c1", "name": "Sprint N°1", "start_date": "2026-09-14T22:00:00Z", "end_date": "2026-10-01T22:00:00Z"},
    {"id": "c3", "name": "Brouillon", "start_date": None, "end_date": None},
]
CYCLE_TICKETS = {"c1": ["t1", "t2"], "c2": [], "c3": []}


class FauxPlane(BaseHTTPRequestHandler):
    """Répond comme l'API publique de Plane v1.4.2 aux GET utiles ; refuse tout le reste (405)."""

    def log_message(self, *a):
        pass

    @classmethod
    def reinitialiser(cls, estimations=True):
        cls.appels, cls.refus_429, cls.estimations = [], 1, estimations

    def _send(self, code, obj=None, headers=None):
        body = json.dumps(obj).encode() if obj is not None else b""
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _page(self, elements, taille=2):
        """Pagination par curseur, 2 éléments par page, pour tester la boucle."""
        q = parse_qs(urlparse(self.path).query)
        debut = int((q.get("cursor") or ["0"])[0])
        suite = debut + taille < len(elements)
        self._send(200, {"results": elements[debut:debut + taille], "next_page_results": suite,
                         "next_cursor": str(debut + taille) if suite else None})

    def do_POST(self):
        FauxPlane.appels.append(("POST", self.path))
        self._send(405)

    do_PATCH = do_PUT = do_DELETE = do_POST

    def do_GET(self):
        chemin = urlparse(self.path).path
        FauxPlane.appels.append(("GET", chemin))
        if self.headers.get("X-Api-Key") != CLE:
            return self._send(401, {"detail": "invalid"})
        if FauxPlane.refus_429:
            FauxPlane.refus_429 -= 1
            return self._send(429, {"detail": "throttled"}, {"Retry-After": "1"})
        prefixe = f"/api/v1/workspaces/{ESPACE}/projects/{PROJET}"
        if not chemin.startswith(prefixe):
            return self._send(404, {"error": "not found"})
        r = chemin[len(prefixe):]
        if r == "/":
            return self._send(200, {"name": "Flowly", "identifier": "FLOWL", "timezone": "Europe/Paris"})
        if r == "/states/":
            return self._page([{"id": "e-done", "name": "Terminé", "group": "completed"},
                               {"id": "e-todo", "name": "À faire", "group": "unstarted"}])
        if r == "/labels/":
            return self._page([{"id": "l-back", "name": "Backend"}])
        if r == "/members/":  # liste simple, avec e-mail : ne doit pas sortir
            return self._send(200, [{"id": "u1", "display_name": "pseudo-plane", "first_name": "A",
                                     "last_name": "B", "email": "secret@exemple.fr", "avatar": "x"}])
        if r == "/estimates/":
            if not FauxPlane.estimations:
                return self._send(404, {"error": "Estimate not found"})
            return self._send(200, {"id": "est", "name": "Jours", "type": "points"})
        if r == "/estimates/est/estimate-points/":
            return self._send(200, [{"id": "pt-1", "value": "1"}, {"id": "pt-2", "value": "2.5"}])
        if r == "/cycles/":
            return self._page(CYCLES)
        if r.startswith("/cycles/") and r.endswith("/cycle-issues/"):
            cid = r.split("/")[2]
            return self._page([{"id": i} for i in CYCLE_TICKETS[cid]])
        if r == "/work-items/":
            return self._page(TICKETS)
        if r.startswith("/work-items/") and r.endswith("/links/"):
            return self._page(LIENS.get(r.split("/")[2], []))
        return self._send(404, {"error": "not found"})


class AvecFauxPlane(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.serveur = HTTPServer(("127.0.0.1", 0), FauxPlane)
        cls.url = f"http://127.0.0.1:{cls.serveur.server_port}"
        threading.Thread(target=cls.serveur.serve_forever, daemon=True).start()
        sp.attendre = lambda s: None

    @classmethod
    def tearDownClass(cls):
        cls.serveur.shutdown()
        cls.serveur.server_close()

    def setUp(self):
        FauxPlane.reinitialiser()

    def plane(self, cle=CLE):
        return sp.PlaneLecture(self.url, cle, ESPACE, PROJET)

    def extraire(self):
        with redirect_stderr(io.StringIO()):
            return sp.extraire(self.plane(), "Flowly-PBS", MAINTENANT, journal=lambda *_: None)

    def test_extraction(self):
        ex = self.extraire()
        t = {x["id"]: x for x in ex["tickets"]}
        self.assertEqual([c["nom"] for c in ex["cycles"]], ["Brouillon", "Sprint N°1", "Sprint N°2"])  # tri par début
        self.assertEqual(ex["projet"], {"nom": "Flowly", "identifiant": "FLOWL", "fuseau": "Europe/Paris"})
        self.assertTrue(t["p1"]["est_parent"])
        self.assertFalse(t["t1"]["est_parent"])
        self.assertEqual(t["t1"]["ref"], "FLOWL-2")
        self.assertEqual(t["t1"]["cycle"], "c1")
        self.assertEqual(t["t1"]["source"], "clickup:a")
        self.assertEqual(t["t1"]["github"], ["Frontend#5"])
        self.assertEqual(t["t1"]["termine_le"], "2026-10-01")  # date ClickUp, pas celle de l'import
        self.assertEqual(t["t2"]["termine_le"], "2026-10-21")  # completed_at, fuseau Europe/Paris
        self.assertEqual(t["t2"]["github"], ["Backend#4"])  # doublon, autre org, Figma écartés
        self.assertEqual(len(t["t2"]["liens"]), 4)
        self.assertEqual(t["t2"]["etiquettes"], ["Backend"])
        self.assertEqual(t["t3"]["estimation"], "2.5")
        self.assertEqual(t["t3"]["assignes"], ["pseudo-plane"])
        self.assertEqual(t["t3"]["fiche"]["je_veux"], "démarrer une session")
        self.assertEqual(t["t3"]["fiche"]["dod"], "- bouton Démarrer\n- tests")
        self.assertEqual(t["t3"]["fiche_manquante"], [])
        self.assertEqual(t["t1"]["fiche_manquante"], ["en_tant_que", "je_veux", "afin_de", "dod"])
        self.assertTrue(ex["estimations"])

    def test_cycles_dates_dans_le_fuseau_du_projet(self):
        c = {x["nom"]: x for x in self.extraire()["cycles"]}
        self.assertEqual((c["Sprint N°1"]["debut"], c["Sprint N°1"]["fin"]), ("2026-09-15", "2026-10-02"))
        self.assertEqual(c["Sprint N°1"]["tickets"], ["t1", "t2"])
        self.assertIsNone(c["Brouillon"]["debut"])

    def test_lecture_seule_et_pagination(self):
        self.extraire()
        self.assertTrue(FauxPlane.appels)
        self.assertEqual({m for m, _ in FauxPlane.appels}, {"GET"})
        pages_tickets = [c for m, c in FauxPlane.appels if c.endswith("/work-items/")]
        self.assertEqual(len(pages_tickets), 3)  # 5 tickets, 2 par page

    def test_aucun_email_ni_cle_dans_l_extraction(self):
        texte = json.dumps(self.extraire(), ensure_ascii=False)
        self.assertNotIn("secret@exemple.fr", texte)
        self.assertNotIn(CLE, texte)
        self.assertNotIn("avatar", texte)

    def test_sans_systeme_d_estimation(self):
        FauxPlane.reinitialiser(estimations=False)
        ex = self.extraire()
        self.assertFalse(ex["estimations"])
        self.assertIsNone({x["id"]: x for x in ex["tickets"]}["t3"]["estimation"])

    def test_cle_refusee(self):
        with self.assertRaises(sp.ErreurPlane) as e, redirect_stderr(io.StringIO()):
            sp.extraire(self.plane("mauvaise"), "Flowly-PBS", MAINTENANT, journal=lambda *_: None)
        self.assertIn("401", str(e.exception))

    def test_periode_des_sprints(self):
        ex = self.extraire()
        self.assertEqual(sp.sprints_vers_periode(ex, ["Sprint N°1", "Sprint N°2"]),
                         (dt.date(2026, 9, 15), dt.date(2026, 10, 23)))
        with self.assertRaises(sp.ErreurPlane):
            sp.sprints_vers_periode(ex, ["Sprint N°9"])
        with self.assertRaises(sp.ErreurPlane):
            sp.sprints_vers_periode(ex, ["Brouillon"])

    def test_resume(self):
        lignes = "\n".join(sp.resume(self.extraire(), dt.date(2026, 10, 2), dt.date(2026, 12, 2)))
        self.assertIn("Tickets : 5 (1 parent(s), 4 carte(s))", lignes)
        self.assertIn("Liens GitHub : 2 (2 issues différentes)", lignes)
        self.assertIn("Fiches stories complètes : 1 / 4", lignes)
        # t1, t2 (cycle Sprint N°1 qui finit le 02/10) et t3 (novembre) ; pas t4 (janvier)
        self.assertIn("Cartes touchant la période 2026-10-02 → 2026-12-02 : 3", lignes)

    def test_ligne_de_commande_extraire(self):
        with tempfile.TemporaryDirectory() as d:
            conf = Path(d) / "pld.yml"
            conf.write_text(
                f"plane:\n  url: '{self.url}'\n  espace: '{ESPACE}'\n  projet_id: '{PROJET}'\n"
                "pld:\n  remise_suivante: '2026-12-02'\n  debut_par_defaut: '2026-10-02'\n", encoding="utf-8")
            sortie = Path(d) / "plane"
            out = io.StringIO()
            with mock.patch.dict(os.environ, {"PLANE_API_KEY": CLE}), mock.patch.object(gp, "EXTRACTIONS", sortie), \
                    redirect_stdout(out), redirect_stderr(io.StringIO()):
                code = gp.main(["2", "--config", str(conf), "--sortie", d, "--extraire", "--sprints", "Sprint N°1"])
            self.assertEqual(code, 0, out.getvalue())
            self.assertIn("Période des sprints : 2026-09-15 → 2026-10-02", out.getvalue())
            fichiers = list(sortie.glob("plane-*.json"))
            self.assertEqual(len(fichiers), 1)
            self.assertEqual(stat.S_IMODE(fichiers[0].stat().st_mode), 0o600)
            self.assertNotIn(CLE, fichiers[0].read_text(encoding="utf-8"))
            self.assertEqual({m for m, _ in FauxPlane.appels}, {"GET"})


class Conversions(unittest.TestCase):
    def test_html_vers_texte(self):
        h = ('<p>A &amp; B<br>suite</p><ul data-type="taskList"><li data-checked="true" data-type="taskItem">'
             '<label><input type="checkbox" checked></label><div><p>fait</p></div></li>'
             '<li data-checked="false" data-type="taskItem"><div><p>pas fait</p></div></li></ul><p></p><p>fin</p>')
        self.assertEqual(sp.html_vers_texte(h), "A & B\nsuite\n\n- [x] fait\n- [ ] pas fait\n\nfin")
        self.assertEqual(sp.html_vers_texte(None), "")

    def test_url_plane(self):
        base = cm.lire_config({"plane": {"espace": "e", "projet_id": PROJET}})
        with tempfile.TemporaryDirectory() as d:
            plat = Path(d) / "platform.yml"
            plat.write_text("projectos_base_domain: exemple.fr\n", encoding="utf-8")
            self.assertEqual(sp.url_plane(base, plat), "https://plane.exemple.fr")
            with self.assertRaises(sp.ErreurPlane):
                sp.url_plane(base, Path(d) / "absent.yml")
        base.plane_url = "https://plane.ailleurs.fr"
        self.assertEqual(sp.url_plane(base), "https://plane.ailleurs.fr")


if __name__ == "__main__":
    unittest.main()
