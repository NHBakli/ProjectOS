"""Tests : lecture GitHub (faux gh), croisement Plane ↔ GitHub, contrôles, rapport,
classeur et PLD Word (ces deux derniers seulement si openpyxl / python-docx et les modèles Epitech sont là)."""
import datetime as dt
import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
import analyse as an  # noqa: E402
import config as cm  # noqa: E402
import rapport  # noqa: E402
import source_github as sg  # noqa: E402

DU, AU, AUJOURD_HUI = dt.date(2026, 10, 2), dt.date(2026, 12, 2), dt.date(2026, 11, 6)
CFG = cm.lire_config({
    "plane": {"espace": "e", "projet_id": "00000000-0000-0000-0000-000000000000"},
    "pld": {"projet": "Flowly", "membres": {"alice-gh": "Alice", "bruno-gh": "Bruno", "sans-carte": "Chloé"},
            "ignores": ["prof-gh"], "debut_par_defaut": "2026-10-02", "remise_suivante": "2026-12-02"},
})
FICHE = {"en_tant_que": "utilisateur", "je_veux": "X", "afin_de": "Y", "dod": "- ok", "bloquants": "aucun"}


def item(depot, num, titre, etat="OPEN", status="Backlog", assignes=(), pr=(), champs=None, corps="",
         fermee=None, raison=None, etiquettes=(), creee="2026-10-05T10:00:00Z"):
    valeurs = [{"name": status, "field": {"name": "Status"}}] if status else []
    for k, v in (champs or {}).items():
        valeurs.append({("number" if isinstance(v, (int, float)) else "date"): v, "field": {"name": k}})
    return {"type": "ISSUE", "fieldValues": {"nodes": valeurs + [{}]}, "content": {
        "number": num, "title": titre, "url": f"https://github.com/Flowly-PBS/{depot}/issues/{num}", "state": etat,
        "stateReason": raison, "createdAt": creee, "closedAt": fermee, "body": corps, "repository": {"name": depot},
        "assignees": {"nodes": [{"login": a} for a in assignes]}, "labels": {"nodes": [{"name": e} for e in etiquettes]},
        "closedByPullRequestsReferences": {"nodes": [
            {"number": n, "url": f"https://github.com/Flowly-PBS/{depot}/pull/{n}", "title": "pr", "mergedAt": m,
             "author": {"login": a}, "repository": {"name": depot}} for n, m, a in pr]}}}


PROJETS = {
    1: [item("Frontend", 5, "Écran focus", "CLOSED", "Done", ["alice-gh"], [(14, "2026-10-20T10:00:00Z", "alice-gh")],
             fermee="2026-10-20T10:00:00Z", raison="COMPLETED"),
        item("Frontend", 30, "Durée de session", status="In progress", assignes=["bruno-gh"],
             champs={"Estimate": 2, "Start date": "2026-10-10", "Target date": "2026-10-20"},
             corps="### En tant que\n\nutilisateur\n\n### Je veux\n\nchoisir\n\n### Afin de\n\nfocus\n\n"
                   "### Definition of Done\n\n- fait\n\n### Points bloquants\n\nattente de l'API"),
        item("Backend", 40, "Issue seule GitHub", status="In review", assignes=["inconnu-gh"], champs={"Estimate": 6}),
        item("Backend", 41, "Annulée", "CLOSED", "Done", ["alice-gh"], fermee="2026-10-12T00:00:00Z", raison="NOT_PLANNED"),
        item("Backend", 42, "Seulement le prof", status="Backlog", assignes=["prof-gh"], champs={"Estimate": 1}),
        item("Backend", 43, "Sans estimation", status="In progress", assignes=["alice-gh"],
             champs={"Start date": "2026-10-10", "Target date": "2026-12-01"}),
        {"type": "DRAFT_ISSUE", "fieldValues": {"nodes": []}, "content": {"title": "brouillon"}}],
    2: [item("Frontend", 5, "Écran focus", "CLOSED", None, ["alice-gh"], fermee="2026-10-20T10:00:00Z", raison="COMPLETED",
             champs={"Estimate": 1.5})],  # même issue dans 2 projets
}
HORS_PROJETS = {"Backend#3": item("Backend", 3, "Schéma SQL", "CLOSED", None, ["bruno-gh"], fermee="2026-09-25T00:00:00Z",
                                  raison="COMPLETED")["content"]}
PR = [{"number": 14, "title": "pr", "url": "u", "mergedAt": "2026-10-20T10:00:00Z", "author": {"login": "alice-gh"},
       "repository": {"name": "Frontend"}, "closingIssuesReferences": {"nodes": [{"number": 5, "repository": {"name": "Frontend"}}]}},
      {"number": 99, "title": "Refonte sans issue", "url": "u2", "mergedAt": "2026-11-01T10:00:00Z", "author": {"login": "bruno-gh"},
       "repository": {"name": "Backend"}, "closingIssuesReferences": {"nodes": []}}]


def faux_gh(appels):
    def executer(args):
        appels.append(args)
        requete = next(a for a in args if a.startswith("query="))[6:]
        variables = dict(a.split("=", 1) for a in args[args.index("-f") + 2:] if "=" in a and not a.startswith("query="))
        if "projectV2" in requete:
            num = int(variables["num"])
            if num not in PROJETS:
                return json.dumps({"data": {"organization": {"projectV2": None}}})
            return json.dumps({"data": {"organization": {"projectV2": {"title": f"Projet {num}", "number": num, "items": {
                "pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": PROJETS[num]}}}}})
        if "search(" in requete:
            return json.dumps({"data": {"search": {"pageInfo": {"hasNextPage": False, "endCursor": None}, "nodes": PR}}})
        data, erreurs = {}, []
        for alias, depot, num in re.findall(r'(i\d+): repository\(owner:"[^"]+", name:"([^"]+)"\) \{ issue\(number:(\d+)\)', requete):
            issue = HORS_PROJETS.get(f"{depot}#{num}")
            data[alias] = {"issue": issue}
            if not issue:
                erreurs.append({"type": "NOT_FOUND", "message": f"Could not resolve to an Issue with the number of {num}."})
        return json.dumps({"data": data, "errors": erreurs} if erreurs else {"data": data})
    return executer


def plane_ticket(id_, seq, titre, groupe="unstarted", github=(), cycle=None, parent=None, est_parent=False,
                 fiche=None, termine_le=None, estimation=None, debut=None, fin=None, etiquettes=()):
    return {"id": id_, "ref": f"FLOWL-{seq}", "titre": titre, "etat": groupe, "groupe": groupe, "parent": parent,
            "est_parent": est_parent, "cycle": cycle, "debut": debut, "fin": fin, "termine_le": termine_le,
            "estimation": estimation, "etiquettes": list(etiquettes), "assignes": [], "source": None, "liens": [],
            "github": list(github), "fiche": fiche or {}, "fiche_manquante": [], "texte": ""}


PLANE = {"extrait_le": "2026-11-06T12:00:00+00:00", "projet": {"nom": "Flowly", "identifiant": "FLOWL"}, "estimations": False,
         "cycles": [{"id": "c1", "nom": "Sprint N°1", "debut": "2026-09-15", "fin": "2026-10-02", "tickets": ["t1", "t2"]},
                    {"id": "c2", "nom": "Sprint N°2", "debut": "2026-10-02", "fin": "2026-10-23", "tickets": ["t3", "t4", "t5"]}],
         "tickets": [
             plane_ticket("p1", 1, "Sprint N°1", est_parent=True),
             plane_ticket("t1", 2, "Schéma SQL", "completed", ["Backend#3"], "c1", "p1", termine_le="2026-10-05"),
             plane_ticket("t2", 3, "Doc ClickUp", "completed", [], "c1", "p1", termine_le="2026-09-30"),
             plane_ticket("t3", 4, "Écran focus", "unstarted", ["Frontend#5"], "c2", fiche=FICHE),
             plane_ticket("t4", 5, "Durée", "unstarted", ["Frontend#30", "Frontend#5"], "c2"),
             plane_ticket("t5", 6, "Lien cassé", "unstarted", ["Frontend#999"], "c2", estimation="2"),
             plane_ticket("t6", 7, "Future", "unstarted", [], None, debut="2027-01-10", fin="2027-01-12"),
         ]}


def extraire_github():
    appels = []
    gl = sg.GithubLecture("Flowly-PBS", executer=faux_gh(appels))
    refs = [r for t in PLANE["tickets"] for r in t["github"]]
    return sg.extraire(gl, [1, 2], refs, DU, AU), appels


class SourceGithub(unittest.TestCase):
    def test_extraction(self):
        gh, appels = extraire_github()
        i = gh["issues"]
        self.assertEqual(i["Frontend#5"]["projets"], ["Projet 1", "Projet 2"])  # fusionnée, comptée une fois
        self.assertEqual(i["Frontend#5"]["champs"]["Status"], "Done")
        self.assertEqual(i["Frontend#5"]["champs"]["Estimate"], 1.5)  # complété par le 2e projet
        self.assertEqual(i["Frontend#30"]["champs"]["Start date"], "2026-10-10")
        self.assertIn("Backend#3", i)  # hors projets, citée par Plane
        self.assertEqual(gh["absentes"], ["Frontend#999"])
        self.assertEqual(gh["brouillons"], 1)
        self.assertEqual([p["ref"] for p in gh["pr_fusionnees"]], ["Frontend#14", "Backend#99"])
        self.assertTrue(all(a[:2] == ["api", "graphql"] for a in appels))
        self.assertTrue(all(next(x for x in a if x.startswith("query=")).startswith("query=query") for a in appels))

    def test_pas_de_mutation(self):
        gl = sg.GithubLecture("Flowly-PBS", executer=lambda a: "{}")
        with self.assertRaises(RuntimeError):
            gl.graphql("mutation { deleteIssue(input:{}) { clientMutationId } }")

    def test_projet_introuvable(self):
        gl = sg.GithubLecture("Flowly-PBS", executer=faux_gh([]))
        with self.assertRaises(sg.ErreurGithub):
            sg.lire_projets(gl, [7])


class Croisement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gh, _ = extraire_github()
        cls.a = an.analyser(CFG, PLANE, cls.gh, DU, AU, AUJOURD_HUI)
        cls.c = {c.cle: c for c in cls.a.cartes}
        cls.messages = [(x.niveau, x.critere, x.carte, x.message) for x in cls.a.controles]

    def controle(self, carte, morceau):
        return any(c == carte and morceau in m for _, _, c, m in self.messages)

    def test_regles(self):
        c = self.c
        self.assertNotIn("FLOWL-1", c)  # règle 5 : ticket parent
        self.assertEqual(c["FLOWL-4"].etat, an.TERMINE)  # règle 1 : GitHub (fermée) l'emporte sur Plane (à faire)
        self.assertEqual(c["FLOWL-4"].responsable, "Alice")
        self.assertEqual([p["ref"] for p in c["FLOWL-4"].preuves], ["Frontend#14"])
        self.assertEqual(c["FLOWL-4"].termine_le, dt.date(2026, 10, 20))
        self.assertIn("Backend#40", c)  # règle 2 : issue de projet citée par aucun ticket
        self.assertNotIn("Frontend#30", c)  # citée par FLOWL-5 : pas de carte en double
        self.assertEqual(c["FLOWL-3"].origine, "plane")  # règle 3
        self.assertEqual(c["FLOWL-3"].responsable, an.EQUIPE)
        self.assertTrue(self.controle(None, "Frontend#5 citée par 2 tickets"))  # règle 4
        self.assertEqual(c["FLOWL-2"].termine_le, dt.date(2026, 9, 25))  # fermeture GitHub, pas la date ClickUp

    def test_etats_et_charges(self):
        c = self.c
        self.assertEqual(c["FLOWL-5"].etat, an.BLOQUE)  # « Points bloquants » rempli dans l'issue
        self.assertEqual(c["FLOWL-5"].bloquants, "attente de l'API")
        self.assertEqual(c["FLOWL-5"].charge, 3.5)  # Estimate 2 + 1,5
        self.assertEqual(c["FLOWL-5"].fiche["je_veux"], "choisir")  # fiche prise dans l'issue
        self.assertEqual(c["Backend#40"].avancement, an.AVANCEMENT_REVUE)
        self.assertEqual(c["Backend#41"].etat, an.ANNULE)
        self.assertEqual(c["Backend#42"].responsable, an.EQUIPE)  # seul assigné : compte ignoré
        self.assertEqual(c["FLOWL-6"].charge, 2)

    def test_periode(self):
        c = self.c
        self.assertFalse(c["FLOWL-3"].dans_periode)  # finie le 30/09
        self.assertFalse(c["FLOWL-2"].dans_periode)  # finie le 25/09
        self.assertTrue(c["FLOWL-4"].dans_periode)
        self.assertNotIn("FLOWL-7", c)  # commence après la période : pas affichée
        intervalle_fin_sur_du = an.Carte(cle="x", origine="plane", titre="x", etat=an.TERMINE,
                                         debut=dt.date(2026, 9, 20), termine_le=DU)
        self.assertFalse(an.dans_periode(intervalle_fin_sur_du, DU, AU))  # finie le jour où la période commence
        commence_le_du = an.Carte(cle="y", origine="plane", titre="y", etat=an.TERMINE, debut=DU, termine_le=DU)
        self.assertTrue(an.dans_periode(commence_le_du, DU, AU))

    def test_numerotation(self):
        self.assertEqual(self.a.membres[:3], ["Alice", "Bruno", "Chloé"])
        self.assertEqual(self.a.membres[-1], an.EQUIPE)
        self.assertEqual(self.c["FLOWL-4"].id_pld.split(".")[0], "1")
        self.assertEqual(self.c["FLOWL-2"].id_pld.split(".")[0], "2")  # Bruno, 2e membre avec des cartes
        ids = [c.id_pld for c in self.a.cartes]
        self.assertEqual(len(ids), len(set(ids)))

    def test_chaque_controle_se_declenche(self):
        self.assertTrue(self.controle("Backend#43", "Carte sans estimation"))
        self.assertTrue(self.controle("Backend#40", "hors de 0,5–4 j"))
        self.assertTrue(self.controle("Backend#42", "Carte sans responsable"))
        self.assertTrue(self.controle("Backend#40", "Dates de début ou de fin prévues manquantes"))
        self.assertTrue(self.controle("Backend#40", "Fiche story incomplète"))
        self.assertTrue(self.controle("FLOWL-5", "Fin prévue le 20/10/2026 dépassée"))  # Target date de l'issue
        self.assertTrue(self.controle(None, "PR Backend#99 fusionnée"))
        self.assertTrue(self.controle("FLOWL-6", "Frontend#999 citée par Plane mais introuvable"))
        self.assertTrue(self.controle(None, "« inconnu-gh » absent de pld.membres"))
        self.assertTrue(self.controle(None, "Chloé : 0 j sur la période"))
        self.assertTrue(self.controle("FLOWL-4", "État Plane « À faire », GitHub « Terminé »"))
        termine_sans_pr = an.Carte(cle="z", origine="github", titre="z", etat=an.TERMINE, issues=["Frontend#1"],
                                   dans_periode=True, charge=1, responsable="Alice", pseudo="alice-gh", fiche=FICHE,
                                   debut=DU, fin=AU)
        avec_autre_auteur = an.Carte(cle="w", origine="github", titre="w", etat=an.TERMINE, issues=["Frontend#2"],
                                     dans_periode=True, charge=1, responsable="Alice", pseudo="alice-gh", fiche=FICHE,
                                     debut=DU, fin=AU, preuves=[{"ref": "Frontend#3", "auteur": "bruno-gh"}])
        autres = an.controler([termine_sans_pr, avec_autre_auteur], ["Alice"], DU, AU, [], AUJOURD_HUI, 4)
        textes = [x.message for x in autres]
        self.assertTrue(any("Terminé sans PR fusionnée" in t for t in textes))
        self.assertTrue(any("Responsable alice-gh, PR par bruno-gh" in t for t in textes))

    def test_rapport(self):
        with tempfile.TemporaryDirectory() as d:
            chemin = Path(d) / "rapport-coherence.md"
            nombre = rapport.ecrire(chemin, self.a, 2, "Flowly", "tests")
            texte = chemin.read_text(encoding="utf-8")
        self.assertGreater(nombre["erreur"], 0)
        self.assertIn("## ✗ À corriger", texte)
        self.assertIn("à ne pas remettre", texte)
        self.assertIn("| Alice |", texte)


MODELES = (Path.home() / "Downloads" / "PLD_Template.docx", Path.home() / "Downloads" / "PLD_Suivi_Taches.xlsx")
try:
    import docx  # noqa: F401
    import openpyxl  # noqa: F401
    LIBS = True
except ImportError:
    LIBS = False


@unittest.skipUnless(LIBS and all(m.is_file() for m in MODELES),
                     "python-docx/openpyxl ou modèles Epitech absents (lancer avec le venv du générateur)")
class Sorties(unittest.TestCase):
    """Génération complète, de la ligne de commande aux fichiers, avec faux Plane (fichier) et faux gh."""

    @classmethod
    def setUpClass(cls):
        import generer_pld as gp
        cls.dossier = tempfile.TemporaryDirectory()
        d = Path(cls.dossier.name)
        (d / "plane.json").write_text(json.dumps(PLANE), encoding="utf-8")
        conf = d / "pld.yml"
        conf.write_text(
            "plane: {espace: e, projet_id: '00000000-0000-0000-0000-000000000000'}\n"
            "github: {org: Flowly-PBS, projets: [1, 2]}\n"
            "pld:\n  projet: Flowly\n  debut_par_defaut: '2026-10-02'\n  remise_suivante: '2026-12-02'\n"
            "  membres: {alice-gh: Alice, bruno-gh: Bruno, sans-carte: Chloé}\n  ignores: [prof-gh]\n"
            "  textes:\n    resume: Résumé de test.\n    schema: {tableau: [[A, B], [a, b]], note: Note.}\n",
            encoding="utf-8")
        out = io.StringIO()
        with mock.patch.object(sg, "gh", faux_gh([])), redirect_stdout(out), redirect_stderr(io.StringIO()):
            cls.code = gp.main(["2", "--config", str(conf), "--plane", str(d / "plane.json"), "--sortie", str(d)])
        cls.sortie, cls.base = out.getvalue(), d / "Sprint_2"

    @classmethod
    def tearDownClass(cls):
        cls.dossier.cleanup()

    def test_fichiers(self):
        self.assertEqual(self.code, 0, self.sortie)
        for nom in ("PLD_Flowly_Sprint2.docx", "Suivi_Taches_Sprint2.xlsx", "rapport-coherence.md", "cartes.json"):
            self.assertTrue((self.base / nom).is_file(), nom)
        self.assertNotIn("Texte d'exemple resté", self.sortie)

    def test_classeur(self):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            wb = openpyxl.load_workbook(self.base / "Suivi_Taches_Sprint2.xlsx")
        ws = wb["Avancement des tâches"]
        lignes = list(ws.iter_rows(min_row=4, values_only=True))
        self.assertEqual(lignes[0][0], "► Alice")
        self.assertEqual(lignes[1][:3], ("1.1", "Alice", "Écran focus"))
        self.assertIn("► Chloé", [l[0] for l in lignes])
        self.assertNotIn("mentions légales", json.dumps([l for l in lignes], default=str))  # exemple du modèle
        bord = [r[0] for r in wb["Tableau de bord"].iter_rows(min_row=3, values_only=True)]
        self.assertEqual(bord[0], "Alice")
        self.assertEqual(bord[-1], "TOTAL")

    def test_word(self):
        from docx.oxml.ns import qn
        d = docx.Document(str(self.base / "PLD_Flowly_Sprint2.docx"))
        corps = d.element.body
        texte = "\n".join(t.text or "" for t in corps.iter(qn("w:t")))
        for exemple in ("mentions légales", "[Rôle]", "[NOM DU PROJET]", "[Titre du sprint]", "[Membre 1]"):
            self.assertNotIn(exemple, texte)
        self.assertIn("Résumé de test.", texte)
        self.assertIn("Écran focus", texte)
        signets = {b.get(qn("w:name")) for b in corps.iter(qn("w:bookmarkStart"))}
        ancres = {h.get(qn("w:anchor")) for h in corps.iter(qn("w:hyperlink")) if h.get(qn("w:anchor"))}
        champs = {m for i in corps.iter(qn("w:instrText")) for m in re.findall(r'HYPERLINK\s+\\l\s+"([^"]+)"', i.text or "")}
        self.assertFalse((ancres | champs) - signets, "liens internes sans signet")
        self.assertIsNotNone(d.settings.element.find(qn("w:updateFields")))


if __name__ == "__main__":
    unittest.main()
