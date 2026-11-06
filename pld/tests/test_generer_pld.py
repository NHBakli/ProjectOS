"""Tests du squelette du générateur de PLD : config, période, fiches stories, ligne de commande. Sans réseau."""
import datetime as dt
import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
import config as cm  # noqa: E402
import fiche_story as fs  # noqa: E402
import generer_pld as gp  # noqa: E402

import yaml  # noqa: E402

EXEMPLE = RACINE / "pld.example.yml"
MODELE_ISSUE = RACINE / "modeles" / "carte-pld.yml"


def donnees(**pld):
    d = yaml.safe_load(EXEMPLE.read_text(encoding="utf-8"))
    d["pld"].update(pld)
    return d


class Config(unittest.TestCase):
    def test_exemple_valide(self):
        cfg = cm.lire_config(donnees())
        self.assertEqual(cfg.espace, "mon-espace")
        self.assertEqual(cfg.projets_github, [1, 2, 3])
        self.assertEqual(cfg.remise_suivante, dt.date(2026, 12, 1))
        self.assertEqual(cfg.membres, {"pseudo-exemple": "Prénom Nom"})

    def test_valeurs_par_defaut(self):
        cfg = cm.lire_config({"plane": {"espace": "e", "projet_id": "00000000-0000-0000-0000-000000000000"}})
        self.assertEqual((cfg.org, cfg.projet, cfg.projets_github), ("Flowly-PBS", "Flowly", [1, 2, 3, 4, 5]))
        self.assertEqual(cfg.membres, {})
        self.assertIsNone(cfg.remise_suivante)

    def test_erreurs(self):
        cas = {
            "projet_id": {"plane": {"espace": "e", "projet_id": "pas-un-id"}},
            "date": donnees(remise_suivante="02/12/2026"),
            "nom vide": donnees(membres={"abc": " "}),
            "pseudo": donnees(membres={"a b": "X"}),
            "membre et ignoré": donnees(membres={"abc": "A"}, ignores=["abc"]),
            "vide": None,
        }
        for nom, d in cas.items():
            with self.subTest(nom), self.assertRaises(cm.ErreurConfig):
                cm.lire_config(d)

    def test_fichier_absent(self):
        with self.assertRaises(cm.ErreurConfig):
            cm.charger("/nulle/part/pld.yml")


class Periode(unittest.TestCase):
    cfg = cm.lire_config(donnees())

    def test_defaut_depuis_config(self):
        p = cm.choisir_periode(self.cfg)
        self.assertEqual((p.du, p.au, p.origine), (dt.date(2026, 10, 1), dt.date(2026, 12, 1), "pld.yml"))

    def test_dates_en_ligne_de_commande(self):
        p = cm.choisir_periode(self.cfg, "2026-10-02", "2026-11-20")
        self.assertEqual((p.du, p.au), (dt.date(2026, 10, 2), dt.date(2026, 11, 20)))
        self.assertEqual(str(p), "2026-10-02 → 2026-11-20")

    def test_une_seule_date_complete_par_la_config(self):
        p = cm.choisir_periode(self.cfg, au="2026-11-15")
        self.assertEqual((p.du, p.au), (dt.date(2026, 10, 1), dt.date(2026, 11, 15)))

    def test_sprints(self):
        p = cm.choisir_periode(self.cfg, sprints=["Sprint N°2", "Sprint N°3"])
        self.assertEqual(p.sprints, ["Sprint N°2", "Sprint N°3"])
        self.assertIsNone(p.du)

    def test_erreurs(self):
        sans_dates = cm.lire_config(donnees(debut_par_defaut=None, remise_suivante=None))
        cas = [
            (self.cfg, {"du": "2026-12-05", "au": "2026-12-01"}),
            (self.cfg, {"du": "2026-10-01", "sprints": ["Sprint N°2"]}),
            (self.cfg, {"sprints": ["A", "A"]}),
            (sans_dates, {}),
            (sans_dates, {"du": "2026-10-01"}),
        ]
        for cfg, kw in cas:
            with self.subTest(kw), self.assertRaises(cm.ErreurConfig):
                cm.choisir_periode(cfg, **kw)


class FicheStory(unittest.TestCase):
    def test_modele_plane(self):
        texte = (
            "En tant que : utilisateur de Flowly\nJe veux : démarrer une session\nAfin de : rester concentré\n\n"
            "Description : écran desktop\n\nDefinition of Done :\n- bouton Démarrer\n- tests\n\nPoints bloquants : aucun"
        )
        r = fs.extraire(texte)
        self.assertEqual(r["en_tant_que"], "utilisateur de Flowly")
        self.assertEqual(r["je_veux"], "démarrer une session")
        self.assertEqual(r["dod"], "- bouton Démarrer\n- tests")
        self.assertEqual(r["bloquants"], "aucun")
        self.assertEqual(fs.manquantes(r), [])

    def test_modele_plane_non_rempli(self):
        r = fs.extraire("En tant que : utilisateur de Flowly\nJe veux : …\nAfin de : …\n\nDefinition of Done :\n- …\n")
        self.assertEqual(fs.manquantes(r), ["je_veux", "afin_de", "dod"])

    def test_formulaire_github(self):
        corps = (
            "### En tant que\n\nutilisateur\n\n### Je veux\n\nune pause\n\n### Afin de\n\nme reposer\n\n"
            "### Description\n\n_No response_\n\n### Definition of Done\n\n- [x] timer\n\n### Points bloquants\n\naucun"
        )
        r = fs.extraire(corps)
        self.assertEqual(r["afin_de"], "me reposer")
        self.assertEqual(r["description"], "")
        self.assertEqual(r["dod"], "- [x] timer")
        self.assertEqual(fs.manquantes(r), [])

    def test_issue_traduite_par_n8n(self):
        corps = (
            "As a: Flowly user\nI want: to start a session\nSo that: I stay focused\n\nDefinition of Done:\n- done\n\n"
            "<details><summary>Original (FR)</summary>\n\n**Titre**\n\nEn tant que : autre chose\n\n</details>\n\n"
            "---\nPlane ticket: https://plane.exemple.fr/x\n<!-- plane-work-item: 123 -->"
        )
        r = fs.extraire(corps)
        self.assertEqual(r["en_tant_que"], "Flowly user")
        self.assertEqual(r["afin_de"], "I stay focused")
        self.assertEqual(r["dod"], "- done")

    def test_texte_libre_sans_rubrique(self):
        r = fs.extraire("Corriger le bouton. Description du bug plus bas.\nRepris de ClickUp (tâche abc).")
        self.assertEqual(r, {})
        self.assertEqual(fs.manquantes(r), list(fs.OBLIGATOIRES))

    def test_gras_et_accents(self):
        r = fs.extraire("**En tant que :** étudiant\n**Définition of done**\n- ok")
        self.assertEqual(r["en_tant_que"], "étudiant")
        self.assertEqual(r["dod"], "- ok")

    def test_modele_issue_lisible_par_le_parseur(self):
        """Les libellés du formulaire GitHub doivent être reconnus, sinon les fiches seraient vides."""
        modele = yaml.safe_load(MODELE_ISSUE.read_text(encoding="utf-8"))
        champs = [b for b in modele["body"] if b["type"] != "markdown"]
        corps = "\n\n".join(f"### {c['attributes']['label']}\n\nvaleur {c['id']}" for c in champs)
        r = fs.extraire(corps)
        for c in champs:
            self.assertEqual(r.get(c["id"]), f"valeur {c['id']}", c["id"])


class LigneDeCommande(unittest.TestCase):
    def lancer(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            try:
                code = gp.main(list(argv))
            except SystemExit as e:
                code = e.code
        return code, out.getvalue(), err.getvalue()

    def test_aide(self):
        code, out, _ = self.lancer("--aide")
        self.assertEqual(code, 0)
        self.assertIn("--sprints", out)
        self.assertIn("--du", out)

    def test_squelette_avec_exemple(self):
        with tempfile.TemporaryDirectory() as d:
            code, out, err = self.lancer("2", "--config", str(EXEMPLE), "--sortie", d, "--du", "2026-10-02")
        self.assertEqual(code, 0, err)
        self.assertIn("Période : 2026-10-02 → 2026-12-01", out)
        self.assertIn("PLD_MonProjet_Sprint2.docx", out)
        self.assertIn("Suivi_Taches_Sprint2.xlsx", out)
        self.assertIn("Membres : 1 (comptes ignorés : 1)", out)
        self.assertNotIn("Prénom Nom", out)  # aucun nom de membre dans la sortie

    def test_erreur_de_periode(self):
        code, _, err = self.lancer("2", "--config", str(EXEMPLE), "--du", "2026-12-05")
        self.assertEqual(code, 1)
        self.assertIn("Période à l'envers", err)

    def test_numero_invalide(self):
        code, _, _ = self.lancer("0", "--config", str(EXEMPLE))
        self.assertEqual(code, 2)


if __name__ == "__main__":
    unittest.main()
