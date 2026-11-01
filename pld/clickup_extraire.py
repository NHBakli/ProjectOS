#!/usr/bin/env python3
"""Extrait un espace de travail ClickUp vers un fichier JSON local. Lecture seule.

Le script ne fait que des requêtes GET. Le token est lu dans CLICKUP_TOKEN,
sinon demandé en masqué. Il n'est jamais écrit ni affiché.
"""
import argparse
import datetime as dt
import getpass
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path

API = os.environ.get("CLICKUP_API_URL", "https://api.clickup.com/api/v2").rstrip("/")
SORTIE_PAR_DEFAUT = Path.home() / "projectos-pld" / "clickup"
attendre = time.sleep  # remplacé dans les tests


class ErreurClickUp(Exception):
    pass


class Client:
    def __init__(self, token):
        self.token = token
        self.appels = 0

    def get(self, chemin, **params):
        url = f"{API}{chemin}"
        if params:
            url += "?" + urllib.parse.urlencode(params)
        for essai in range(5):
            req = urllib.request.Request(url, headers={"Authorization": self.token, "Accept": "application/json"})
            self.appels += 1
            try:
                with urllib.request.urlopen(req, timeout=60) as rep:
                    return json.load(rep)
            except urllib.error.HTTPError as e:
                if e.code == 429 and essai < 4:
                    # Limite de débit : attendre la date donnée par ClickUp (secondes epoch).
                    reset = e.headers.get("X-RateLimit-Reset")
                    pause = max(1, int(reset) - int(time.time())) if reset and reset.isdigit() else 60
                    print(f"  Limite ClickUp atteinte, pause de {min(pause, 120)} s…", file=sys.stderr)
                    attendre(min(pause, 120))
                    continue
                if e.code in (401, 403):
                    raise ErreurClickUp(f"Accès refusé ({e.code}) : token invalide ou sans droit sur {chemin}")
                raise ErreurClickUp(f"Erreur {e.code} sur {chemin}")
            except urllib.error.URLError as e:
                raise ErreurClickUp(f"ClickUp injoignable : {e.reason}")
        raise ErreurClickUp(f"Trop de refus (429) sur {chemin}")


def listes_de(client, espace):
    """Toutes les listes d'un espace (dans un dossier ou non), archivées comprises."""
    listes = []
    for archive in ("false", "true"):
        for dossier in client.get(f"/space/{espace['id']}/folder", archived=archive).get("folders", []):
            for archive_liste in ("false", "true"):
                for liste in client.get(f"/folder/{dossier['id']}/list", archived=archive_liste).get("lists", []):
                    liste["_dossier"] = {"id": dossier["id"], "name": dossier.get("name")}
                    listes.append(liste)
        for liste in client.get(f"/space/{espace['id']}/list", archived=archive).get("lists", []):
            liste["_dossier"] = None
            listes.append(liste)
    uniques = {}
    for liste in listes:
        liste["_espace"] = {"id": espace["id"], "name": espace.get("name")}
        uniques.setdefault(liste["id"], liste)
    return list(uniques.values())


def taches_de(client, liste):
    taches = []
    for archive in ("false", "true"):
        page = 0
        while True:
            rep = client.get(
                f"/list/{liste['id']}/task",
                archived=archive, include_closed="true", subtasks="true",
                include_markdown_description="true", page=page,
            )
            lot = rep.get("tasks", [])
            taches.extend(lot)
            if rep.get("last_page", True) or not lot:
                break
            page += 1
    return taches


def date_ms(valeur):
    if not valeur:
        return "—"
    return dt.datetime.fromtimestamp(int(valeur) / 1000, dt.timezone.utc).strftime("%Y-%m-%d")


def resume(donnees):
    """Résumé sans donnée personnelle (pas d'e-mail), à coller pour préparer l'import."""
    taches = donnees["taches"]
    lignes = [f"Espace de travail : {donnees['equipe']['name']}", ""]
    lignes.append("Listes (espace / dossier / liste : début → fin, tâches, fermées) :")
    par_liste = Counter(t["list"]["id"] for t in taches)
    fermees = Counter(t["list"]["id"] for t in taches if t.get("date_closed"))
    for l in sorted(donnees["listes"], key=lambda l: (l["_espace"]["name"] or "", l.get("start_date") or "0")):
        dossier = l["_dossier"]["name"] if l["_dossier"] else "-"
        arch = " (archivée)" if l.get("archived") else ""
        lignes.append(
            f"  {l['_espace']['name']} / {dossier} / {l['name']}{arch} : "
            f"{date_ms(l.get('start_date'))} → {date_ms(l.get('due_date'))}, "
            f"{par_liste[l['id']]} tâches, {fermees[l['id']]} fermées"
        )
    lignes += ["", "Statuts (nom [type] : nombre) :"]
    for (nom, typ), n in sorted(Counter((t["status"]["status"], t["status"].get("type")) for t in taches).items()):
        lignes.append(f"  {nom} [{typ}] : {n}")
    tags = Counter(tag["name"] for t in taches for tag in t.get("tags", []))
    lignes += ["", "Tags : " + (", ".join(f"{k} ({v})" for k, v in sorted(tags.items())) or "aucun")]
    champs = Counter(c["name"] for t in taches for c in t.get("custom_fields", []) if c.get("value") not in (None, ""))
    lignes.append("Champs personnalisés remplis : " + (", ".join(f"{k} ({v})" for k, v in sorted(champs.items())) or "aucun"))
    assignes = {a["id"] for t in taches for a in t.get("assignees", [])}
    lignes += [
        "",
        f"Tâches : {len(taches)} (sous-tâches : {sum(1 for t in taches if t.get('parent'))})",
        f"Avec points : {sum(1 for t in taches if t.get('points') is not None)}, "
        f"avec estimation de temps : {sum(1 for t in taches if t.get('time_estimate'))}",
        f"Avec date de début : {sum(1 for t in taches if t.get('start_date'))}, "
        f"avec échéance : {sum(1 for t in taches if t.get('due_date'))}",
        f"Personnes assignées : {len(assignes)}",
        f"Sans assigné : {sum(1 for t in taches if not t.get('assignees'))}",
    ]
    return "\n".join(lignes)


def analyser_arguments(argv):
    p = argparse.ArgumentParser(
        prog="clickup_extraire.py", add_help=False,
        description="Extrait ClickUp vers un fichier JSON local (lecture seule).",
    )
    p.add_argument("-h", "--aide", action="help", help="afficher cette aide")
    p.add_argument("--equipe", help="ID de l'espace de travail ClickUp (si tu en as plusieurs)")
    p.add_argument("--sortie", type=Path, default=SORTIE_PAR_DEFAUT,
                   help=f"dossier du fichier produit (défaut : {SORTIE_PAR_DEFAUT})")
    return p.parse_args(argv)


def main(argv=None):
    args = analyser_arguments(argv)
    token = os.environ.get("CLICKUP_TOKEN") or getpass.getpass("Token ClickUp (saisie masquée) : ")
    if not token.strip():
        print("Aucun token saisi.", file=sys.stderr)
        return 2
    client = Client(token.strip())
    try:
        equipes = client.get("/team").get("teams", [])
        if args.equipe:
            equipes = [e for e in equipes if str(e["id"]) == args.equipe]
        if len(equipes) != 1:
            print("Choisis l'espace de travail avec --equipe :", file=sys.stderr)
            for e in client.get("/team").get("teams", []):
                print(f"  --equipe {e['id']}   ({e.get('name')})", file=sys.stderr)
            return 2
        equipe = equipes[0]
        print(f"Lecture de « {equipe.get('name')} »…", file=sys.stderr)
        espaces = client.get(f"/team/{equipe['id']}/space", archived="false").get("spaces", [])
        listes, taches = [], []
        for espace in espaces:
            for liste in listes_de(client, espace):
                listes.append(liste)
                taches.extend(taches_de(client, liste))
    except ErreurClickUp as e:
        print(f"Échec : {e}", file=sys.stderr)
        return 1

    # Une tâche peut apparaître plusieurs fois (archives, listes multiples) : on garde la 1re.
    uniques = {}
    for t in taches:
        uniques.setdefault(t["id"], t)
    donnees = {
        "extrait_le": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "source": "clickup",
        "equipe": {"id": equipe["id"], "name": equipe.get("name"), "members": equipe.get("members", [])},
        "espaces": espaces,
        "listes": listes,
        "taches": list(uniques.values()),
    }

    args.sortie.mkdir(parents=True, exist_ok=True, mode=0o700)
    fichier = args.sortie / f"clickup-{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}.json"
    fd = os.open(fichier, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(donnees, f, ensure_ascii=False, indent=1)

    print(resume(donnees))
    print(f"\nFichier : {fichier}  ({client.appels} requêtes, lecture seule)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
