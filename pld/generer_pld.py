#!/usr/bin/env python3
"""Générateur du PLD Epitech de Flowly, depuis Plane (historique) et GitHub (cartes, preuves).

Lancer par ./scripts/generer-pld.sh (environnement Python isolé, dépendances épinglées).
Lecture seule : rien n'est modifié dans Plane ni dans GitHub. Plan : docs/plan-pld.md.

État : étapes 1 et 2. Lit la config, choisit la période ; avec --extraire, lit Plane
(lecture seule) et enregistre un JSON sans secret dans ~/projectos-pld/plane/.
La lecture de GitHub arrive à l'étape 3.
"""
import argparse
import datetime as dt
import getpass
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg_mod  # noqa: E402
import source_plane  # noqa: E402

EXTRACTIONS = Path.home() / "projectos-pld" / "plane"

EXEMPLES = """\
exemples :
  ./scripts/generer-pld.sh 2
      période de pld.yml (pld.debut_par_defaut → pld.remise_suivante)
  ./scripts/generer-pld.sh 2 --du 2026-10-02 --au 2026-12-02
  ./scripts/generer-pld.sh 2 --sprints "Sprint N°2" "Sprint N°3"
  ./scripts/generer-pld.sh 2 --extraire
      lit Plane (lecture seule, clé API demandée), enregistre ~/projectos-pld/plane/plane-….json
"""


def analyser_arguments(argv):
    p = argparse.ArgumentParser(
        prog="generer-pld.sh",
        description="Génère le PLD Epitech (Word + Excel + rapport de cohérence) depuis Plane et GitHub.",
        epilog=EXEMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        add_help=False,
    )
    p.add_argument("-h", "--aide", "--help", action="help", help="affiche cette aide")
    p.add_argument("numero", type=int, help="numéro du PLD (Sprint_N dans les noms de fichiers)")
    p.add_argument("--du", metavar="AAAA-MM-JJ", help="début de la période (défaut : pld.debut_par_defaut)")
    p.add_argument("--au", metavar="AAAA-MM-JJ", help="fin de la période (défaut : pld.remise_suivante)")
    p.add_argument("--sprints", nargs="+", metavar="NOM", help="sprints à inclure (noms des cycles Plane), à la place des dates")
    p.add_argument("--config", type=Path, default=cfg_mod.CONFIG, help=f"fichier de configuration (défaut : {cfg_mod.CONFIG})")
    p.add_argument("--sortie", type=Path, help="dossier de sortie (défaut : pld.sortie, sinon ~/projectos-pld/PLD)")
    p.add_argument("--extraire", action="store_true",
                   help="lire Plane (GET seulement) et enregistrer l'extraction JSON (clé : PLANE_API_KEY, sinon demandée)")
    args = p.parse_args(argv)
    if args.numero < 1:
        p.error("le numéro du PLD doit être 1 ou plus")
    return args


def fichiers_sortie(cfg, numero, sortie=None):
    dossier = (sortie.expanduser() if sortie else cfg.sortie) / f"Sprint_{numero}"
    return {
        "dossier": dossier,
        "docx": dossier / f"PLD_{cfg.projet}_Sprint{numero}.docx",
        "xlsx": dossier / f"Suivi_Taches_Sprint{numero}.xlsx",
        "rapport": dossier / "rapport-coherence.md",
    }


def main(argv=None):
    args = analyser_arguments(sys.argv[1:] if argv is None else argv)
    try:
        cfg = cfg_mod.charger(args.config)
        periode = cfg_mod.choisir_periode(cfg, args.du, args.au, args.sprints)
    except cfg_mod.ErreurConfig as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1

    sortie = fichiers_sortie(cfg, args.numero, args.sortie)
    print(f"PLD n°{args.numero} — {cfg.projet}")
    print(f"Période : {periode} ({periode.origine})")
    if periode.sprints:
        print("  Les dates des sprints seront lues dans Plane (étape 2).")
    print(f"Plane : espace « {cfg.espace} », projet {cfg.projet_id[:8]}…")
    print(f"GitHub : {cfg.org}, projets {', '.join(map(str, cfg.projets_github))}")
    print(f"Membres : {len(cfg.membres)} (comptes ignorés : {len(cfg.ignores)})")
    manque = False
    for nom, chemin in (("Modèle Word", cfg.modele_docx), ("Modèle Excel", cfg.modele_xlsx)):
        ok = chemin.is_file()
        manque |= not ok
        print(f"{nom} : {'✓' if ok else '✗ introuvable'} {chemin}")
    print(f"Sortie : {sortie['dossier']}/")
    for cle in ("docx", "xlsx", "rapport"):
        print(f"  {sortie[cle].name}")
    if not cfg.membres:
        print("⚠ Aucun membre dans pld.membres : le PLD affichera les pseudos GitHub.")
    if manque:
        print("⚠ Modèle Epitech introuvable : indiquer son chemin dans pld.modeles.")
    print()
    if not args.extraire:
        print("Plane non lu : ajouter --extraire. GitHub : pas encore écrit (étape 3 de docs/plan-pld.md).")
        print("Rien n'a été lu ni écrit.")
        return 0
    try:
        chemin, extraction = extraire_plane(cfg)
        du, au = periode.du, periode.au
        if periode.sprints:
            du, au = source_plane.sprints_vers_periode(extraction, periode.sprints)
            print(f"Période des sprints : {du} → {au}")
    except source_plane.ErreurPlane as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    for ligne in source_plane.resume(extraction, du, au):
        print(ligne)
    print(f"Extraction : {chemin} ({extraction['requetes']} requêtes, lecture seule)")
    print("GitHub : pas encore lu (étape 3). Aucun fichier de PLD écrit.")
    return 0


def extraire_plane(cfg, dossier=None, maintenant=None):
    """Lit Plane et enregistre le JSON (droits 600). Renvoie (chemin, extraction)."""
    dossier = dossier or EXTRACTIONS  # lu à l'appel (remplacé dans les tests)
    url = source_plane.url_plane(cfg)
    cle = os.environ.get("PLANE_API_KEY") or getpass.getpass("Clé API Plane (saisie masquée) : ")
    if not cle.strip():
        raise source_plane.ErreurPlane("Clé API Plane vide")
    plane = source_plane.PlaneLecture(url, cle.strip(), cfg.espace, cfg.projet_id)
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    extraction = source_plane.extraire(plane, cfg.org, maintenant)
    dossier.mkdir(parents=True, exist_ok=True, mode=0o700)
    chemin = dossier / f"plane-{maintenant.strftime('%Y%m%dT%H%M%SZ')}.json"
    fd = os.open(chemin, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(extraction, f, ensure_ascii=False, indent=1)
    return chemin, extraction


if __name__ == "__main__":
    sys.exit(main())
