#!/usr/bin/env python3
"""Générateur du PLD Epitech de Flowly, depuis Plane (historique) et GitHub (cartes, preuves).

Lancer par ./scripts/generer-pld.sh (environnement Python isolé, dépendances épinglées).
Lecture seule : rien n'est modifié dans Plane ni dans GitHub. Plan : docs/plan-pld.md, guide : docs/08-pld.md.

Étapes : config et période → Plane (API, GET) → GitHub (gh api graphql, query) → croisement et
contrôles → rapport-coherence.md, Suivi_Taches_SprintN.xlsx, PLD_Projet_SprintN.docx.
"""
import argparse
import datetime as dt
import getpass
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import config as cfg_mod  # noqa: E402
import source_plane  # noqa: E402

EXTRACTIONS = Path.home() / "projectos-pld" / "plane"

EXEMPLES = """\
exemples :
  ./scripts/generer-pld.sh 2
      période de pld.yml (pld.debut_par_defaut → pld.remise_suivante), Plane lu (clé demandée)
  ./scripts/generer-pld.sh 2 --du 2026-10-02 --au 2026-12-02
  ./scripts/generer-pld.sh 2 --sprints "Sprint N°2" "Sprint N°3"
  ./scripts/generer-pld.sh 2 --plane ~/projectos-pld/plane/plane-20261106T150000Z.json
      réutilise une extraction Plane (pas de clé demandée)
  ./scripts/generer-pld.sh 2 --extraire     lit seulement Plane et enregistre l'extraction
  ./scripts/generer-pld.sh 2 --verifier     vérifie la config, ne lit rien
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
    p.add_argument("--titre", help="titre du sprint sur la page de titre (défaut : « Sprint N »)")
    p.add_argument("--config", type=Path, default=cfg_mod.CONFIG, help=f"fichier de configuration (défaut : {cfg_mod.CONFIG})")
    p.add_argument("--sortie", type=Path, help="dossier de sortie (défaut : pld.sortie, sinon ~/projectos-pld/PLD)")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--plane", type=Path, metavar="FICHIER", help="extraction Plane déjà enregistrée, au lieu de lire Plane")
    mode.add_argument("--extraire", action="store_true",
                      help="lire seulement Plane (GET) et enregistrer l'extraction (clé : PLANE_API_KEY, sinon demandée)")
    mode.add_argument("--verifier", action="store_true", help="vérifier la config et la période, sans rien lire")
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
        "cartes": dossier / "cartes.json",
    }


def _bilan_config(cfg, periode, sortie):
    print(f"Période : {periode} ({periode.origine})")
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
    return not manque


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
    modeles_ok = _bilan_config(cfg, periode, sortie)
    print()
    if args.verifier:
        print("Vérification seule : rien n'a été lu ni écrit.")
        return 0

    try:
        if args.plane:
            extraction = json.loads(args.plane.expanduser().read_text(encoding="utf-8"))
            print(f"Plane : extraction du {extraction.get('extrait_le', '?')} ({args.plane.name})")
        else:
            chemin, extraction = extraire_plane(cfg)
            print(f"Plane : {chemin} ({extraction['requetes']} requêtes, lecture seule)")
        du, au = periode.du, periode.au
        if periode.sprints:
            du, au = source_plane.sprints_vers_periode(extraction, periode.sprints)
            print(f"Période des sprints : {du} → {au}")
    except (source_plane.ErreurPlane, OSError, ValueError) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    if args.extraire:
        for ligne in source_plane.resume(extraction, du, au):
            print(ligne)
        print("Extraction seule : aucun fichier de PLD écrit.")
        return 0
    if not modeles_ok:
        print("✗ Modèles Epitech manquants : rien n'est généré.", file=sys.stderr)
        return 1
    return generer(cfg, args, extraction, du, au, sortie, periode)


def generer(cfg, args, extraction, du, au, sortie, periode, aujourd_hui=None):
    import analyse as an
    import rapport
    import sortie_docx
    import sortie_xlsx
    import source_github

    aujourd_hui = aujourd_hui or dt.date.today()
    try:
        gl = source_github.GithubLecture(cfg.org)
        refs = [r for t in extraction["tickets"] for r in t["github"]]
        github = source_github.extraire(gl, cfg.projets_github, refs, du, au)
    except source_github.ErreurGithub as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    print(f"GitHub : {len(github['issues'])} issues, {len(github['pr_fusionnees'])} PR fusionnées sur la période "
          f"({github['requetes']} requêtes, lecture seule)")

    a = an.analyser(cfg, extraction, github, du, au, aujourd_hui)
    s = a.stats
    titre = args.titre or f"Sprint {args.numero}"
    version = f"{args.numero}.0"
    auteurs = list(cfg.membres.values()) or sorted({c.responsable for c in a.cartes})
    revisions = list(cfg.revisions)
    if not any(r.get("version") == version for r in revisions):
        revisions.append({"date": f"{aujourd_hui:%d/%m/%Y}", "version": version, "auteurs": ", ".join(auteurs),
                          "sections": "Toutes", "commentaires": f"PLD n°{args.numero} ({du:%d/%m/%Y} → {au:%d/%m/%Y}), "
                          "généré depuis Plane et GitHub"})
    textes = cfg.textes
    chiffres = (f"Du {du:%d/%m/%Y} au {au:%d/%m/%Y} : {s['periode']} cartes, dont {s['terminees']} terminées, "
                f"{s['en_cours']} en cours et {s['a_faire']} à faire ; {s['pr']} pull requests fusionnées.")
    resume = textes.get("resume")
    resume = (f"{resume.strip()} {chiffres}" if isinstance(resume, str) and resume.strip() else resume or chiffres)
    bloquees = [c for c in a.cartes if c.dans_periode and (c.etat == an.BLOQUE or c.bloquants)]
    bloquants = "\n".join(f"{c.id_pld} {c.titre} : {c.bloquants or 'bloquée'}" for c in bloquees) \
        or "Aucun point bloquant signalé dans les cartes."
    if isinstance(textes.get("bloquants"), str) and textes["bloquants"].strip():
        bloquants += "\n" + textes["bloquants"].strip()
    commentaire = (f"{s['periode']} cartes sur la période : {s['terminees']} terminées, {s['en_cours']} en cours, "
                   f"{s['a_faire']} à faire, {s['bloquees']} bloquées. Charge prévue {s['charge_prevue']:g} j, "
                   f"réalisée {s['charge_realisee']:g} j ({s['sans_estimation']} cartes sans estimation). "
                   f"{s['pr']} pull requests fusionnées.").replace(".5 j", ",5 j")
    if isinstance(textes.get("commentaire"), str) and textes["commentaire"].strip():
        commentaire += "\n" + textes["commentaire"].strip()

    sortie["dossier"].mkdir(parents=True, exist_ok=True)
    sources = (f"Plane (extraction du {extraction.get('extrait_le', '?')[:16].replace('T', ' ')}), "
               f"GitHub {cfg.org} projets {', '.join(map(str, cfg.projets_github))}")
    nombre = rapport.ecrire(sortie["rapport"], a, args.numero, cfg.projet, sources)
    try:
        sortie_xlsx.ecrire(sortie["xlsx"], cfg.modele_xlsx, a, cfg.projet, titre, version, revisions)
        restes = sortie_docx.ecrire(sortie["docx"], cfg.modele_docx, a, {
            "projet": cfg.projet, "titre_periode": titre, "date": f"{au:%d/%m/%Y}", "auteurs": auteurs,
            "mise_a_jour": f"{aujourd_hui:%d/%m/%Y}",
            "responsable": cfg.responsable, "email": cfg.email, "promotion": cfg.promotion, "version": version,
            "revisions": revisions, "resume": resume, "schema": textes.get("schema"),
            "plan_alpha_beta": textes.get("plan_alpha_beta"), "bloquants": bloquants, "commentaire": commentaire})
    except (sortie_xlsx.ErreurXlsx, sortie_docx.ErreurDocx) as e:
        print(f"✗ {e}", file=sys.stderr)
        return 1
    donnees = {"periode": [du.isoformat(), au.isoformat()], "stats": s,
               "cartes": [asdict(c) for c in a.cartes], "controles": [asdict(c) for c in a.controles]}
    sortie["cartes"].write_text(json.dumps(donnees, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

    print()
    print(f"Cartes : {s['cartes']} dans le PLD, {s['periode']} sur la période ({s['terminees']} terminées, "
          f"{s['en_cours']} en cours, {s['a_faire']} à faire, {s['bloquees']} bloquées)")
    print(f"Contrôles : {nombre['erreur']} à corriger, {nombre['attention']} à vérifier, {nombre['info']} pour information")
    if restes:
        print(f"⚠ Texte d'exemple resté dans le Word : {', '.join(restes)}")
    print("Fichiers :")
    for cle in ("docx", "xlsx", "rapport"):
        print(f"  {sortie[cle]}")
    print("Relire rapport-coherence.md, corriger dans GitHub ou Plane, puis relancer.")
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
