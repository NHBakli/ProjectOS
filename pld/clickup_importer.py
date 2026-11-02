#!/usr/bin/env python3
"""Importe l'historique ClickUp (extrait par clickup_extraire.py) dans un projet Plane.

Trois modes :
  --plan       hors ligne : affiche ce qui sera importé, sans contacter Plane ;
  (défaut)     essai à blanc : lit Plane (GET seulement) et dit ce qui serait créé ;
  --appliquer  crée réellement cycles, tickets et liens.

Règles (voir docs/07-import-clickup.md) :
- une tâche parente ClickUp = un cycle Plane, une sous-tâche = un ticket ;
- aucune étiquette d'équipe : le workflow n8n Plane → GitHub ne crée rien ;
- les issues GitHub déjà existantes sont reliées au ticket, au format de n8n ;
- relancer ne recrée rien (external_source = clickup, external_id = ID ClickUp) ;
- aucun assigné, rien n'est modifié ni supprimé dans Plane.

La clé API Plane est lue dans PLANE_API_KEY, sinon demandée en masqué.
"""
import argparse
import datetime as dt
import getpass
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("Module PyYAML absent : python3 -m pip install pyyaml")

CONFIG = Path.home() / ".config" / "projectos" / "pld.yml"
PLATFORM = Path.home() / ".config" / "projectos" / "platform.yml"
EXTRACTIONS = Path.home() / "projectos-pld" / "clickup"
SOURCE = "clickup"
ORG = "Flowly-PBS"
DEPOTS = {"Frontend", "Backend", "Mobile", "DevOps", "Contenu3D", "Documentation"}
FUSEAU = ZoneInfo("Europe/Paris")
PRIORITES = {"urgent": "urgent", "high": "high", "normal": "medium", "low": "low"}
FIN_PROVISOIRE_JOURS = 7  # un cycle passé est d'abord créé avec une fin future
attendre = time.sleep  # remplacé dans les tests


class ErreurImport(Exception):
    pass


# ---------------------------------------------------------------- plan (hors ligne)

def date_clickup(ms):
    if not ms:
        return None
    return dt.datetime.fromtimestamp(int(ms) / 1000, FUSEAU).date()


def description_html(tache, termine_le):
    texte = (tache.get("text_content") or "").strip()
    blocs = [f"<p>{html.escape(l)}</p>" for l in texte.splitlines() if l.strip()]
    blocs.append(f"<p><em>Repris de ClickUp (tâche {html.escape(tache['id'])}).</em></p>")
    if termine_le:
        blocs.append(f"<p>Terminé le : {termine_le.isoformat()}</p>")
    tags = [t["name"] for t in tache.get("tags") or []]
    if tags:
        blocs.append(f"<p>Tags ClickUp : {html.escape(', '.join(tags))}</p>")
    return "".join(blocs)


def lien_github(ref):
    m = re.fullmatch(r"([A-Za-z0-9_.-]+)#([0-9]+)", ref.strip())
    if not m or m.group(1) not in DEPOTS:
        raise ErreurImport(f"Issue GitHub mal écrite : « {ref} » (attendu : Frontend#12, Backend#3…)")
    depot, numero = m.groups()
    return {"url": f"https://github.com/{ORG}/{depot}/issues/{numero}", "title": f"GitHub {ORG}/{depot}#{numero}"}


def construire_plan(donnees, config, aujourd_hui):
    """Transforme l'extraction + la table de correspondance en cycles et tickets à créer."""
    taches = {t["id"]: t for t in donnees["taches"]}
    racine = lambda t: t.get("top_level_parent") or t.get("parent")  # noqa: E731
    parents = {racine(t) for t in taches.values() if racine(t)}
    table = {str(e["clickup_id"]): e for e in config.get("taches") or []}
    erreurs, avert = [], []

    a_importer = [t for t in taches.values() if t["id"] not in parents]
    for t in a_importer:
        if t["id"] not in table:
            erreurs.append(f"Tâche absente de pld.yml : {t['id']} « {t['name']} »")
    for cid in table:
        if cid not in taches:
            erreurs.append(f"pld.yml cite une tâche absente de l'extraction : {cid}")
        elif cid in parents:
            erreurs.append(f"pld.yml cite une tâche parente (cycle), pas un ticket : {cid}")

    fin_en_cours = config.get("fin_cycle_en_cours") or None
    if fin_en_cours:
        fin_en_cours = dt.date.fromisoformat(str(fin_en_cours))

    cycles, parents_tickets = [], []
    for pid in sorted(parents, key=lambda i: int(taches[i].get("start_date") or 0) if i in taches else 0):
        p = taches.get(pid)
        if not p:
            erreurs.append(f"Tâche parente {pid} absente de l'extraction")
            continue
        debut, fin = date_clickup(p.get("start_date")), date_clickup(p.get("due_date"))
        if p["status"].get("type") != "closed":  # sprint resté ouvert dans ClickUp : fin confirmée dans pld.yml
            if fin_en_cours:
                fin = fin_en_cours
            elif not fin or fin < aujourd_hui:
                erreurs.append(f"« {p['name']} » est encore ouvert dans ClickUp : confirme sa date de fin "
                                   f"(fin_cycle_en_cours dans pld.yml)")
        if not debut or not fin:
            erreurs.append(f"Cycle « {p['name']} » sans date de début ou de fin dans ClickUp")
        elif debut > fin:
            erreurs.append(f"Cycle « {p['name']} » : début {debut} après la fin {fin}")
        # Encore ouvert dans ClickUp ne veut pas dire en cours : c'est la date de fin qui décide.
        en_cours = bool(fin) and fin >= aujourd_hui
        cycles.append({"clickup_id": pid, "nom": p["name"], "debut": debut, "fin": fin, "en_cours": en_cours})
        # La tâche parente devient aussi un ticket parent (comme dans ClickUp), hors cycle.
        ferme = p["status"].get("type") == "closed"
        termine_le = date_clickup(p.get("date_done") or p.get("date_closed")) if ferme else None
        parents_tickets.append({
            "clickup_id": pid, "titre": p["name"].strip(), "cycle": None, "parent": None,
            "groupe": "completed" if ferme else "unstarted", "debut": debut, "fin": fin,
            "termine_le": termine_le,
            "priorite": PRIORITES.get(((p.get("priority") or {}).get("priority") or "").lower(), "none"),
            "description_html": description_html(p, termine_le), "liens": []})

    ordre = {c["clickup_id"]: i for i, c in enumerate(cycles)}
    par_id = {c["clickup_id"]: c for c in cycles}
    tickets = []
    for t in sorted(a_importer, key=lambda t: (ordre.get(racine(t), len(ordre)), float(t.get("orderindex") or 0))):
        entree = table.get(t["id"], {})
        if entree.get("a_verifier"):
            avert.append(f"Correspondance marquée à vérifier : « {t['name']} » → {entree.get('issues') or 'aucune'}")
        liens = []
        for ref in entree.get("issues") or []:
            try:
                liens.append(lien_github(str(ref)))
            except ErreurImport as e:
                erreurs.append(str(e))
        ferme = t["status"].get("type") == "closed"
        termine_le = date_clickup(t.get("date_done") or t.get("date_closed")) if ferme else None
        debut, fin = date_clickup(t.get("start_date")), date_clickup(t.get("due_date"))
        cycle = par_id.get(racine(t))
        if debut and fin and debut > fin:
            avert.append(f"« {t['name']} » : début après l'échéance, début ignoré")
        elif cycle:
            # Sans date propre : celles du sprint, pour placer le ticket dans le temps.
            debut, fin = debut or cycle["debut"], fin or cycle["fin"]
        if debut and fin and debut > fin:
            debut = None
        tickets.append({
            "clickup_id": t["id"],
            "titre": t["name"].strip(),
            "cycle": racine(t),
            "parent": racine(t),
            "groupe": "completed" if ferme else "unstarted",
            "debut": debut,
            "fin": fin,
            "termine_le": termine_le,
            "priorite": PRIORITES.get(((t.get("priority") or {}).get("priority") or "").lower(), "none"),
            "description_html": description_html(t, termine_le),
            "liens": liens,
        })
    return {"cycles": cycles, "parents": parents_tickets, "tickets": tickets,
            "erreurs": erreurs, "avertissements": avert}


def afficher_plan(plan):
    noms = {c["clickup_id"]: c for c in plan["cycles"]}
    print("Phases et sprints (ticket parent + cycle) :")
    for c in plan["cycles"]:
        n = sum(1 for t in plan["tickets"] if t["cycle"] == c["clickup_id"])
        etat = "en cours" if c["en_cours"] else "terminé"
        print(f"  {c['nom']} : {c['debut']} → {c['fin']} ({etat}), {n} sous-tickets")
    print("\nSous-tickets (sprint, état, dates, titre, issues GitHub reliées) :")
    for t in plan["tickets"]:
        c = noms.get(t["cycle"], {}).get("nom", "sans cycle")
        refs = ", ".join(l["title"].split("/", 1)[1] for l in t["liens"]) or "—"
        etat = "terminé" if t["groupe"] == "completed" else "à faire"
        dates = f"{t['debut'] or '…'} → {t['fin'] or '…'}"
        print(f"  [{c}] {etat:8} {dates:25} {t['titre'][:50]:50} {refs}")
    n_liens = sum(len(t["liens"]) for t in plan["tickets"])
    print(f"\nTotal : {len(plan['cycles'])} cycles, {len(plan['parents'])} tickets parents, "
          f"{len(plan['tickets'])} sous-tickets, {n_liens} liens GitHub.")
    for a in plan["avertissements"]:
        print(f"  ⚠ {a}")


# ---------------------------------------------------------------- Plane

class Plane:
    def __init__(self, url, cle, espace, projet, ecrire=False):
        self.base = f"{url.rstrip('/')}/api/v1/workspaces/{espace}/projects/{projet}"
        self.cle, self.ecrire, self.appels = cle, ecrire, 0

    def requete(self, methode, chemin, corps=None):
        if methode != "GET" and not self.ecrire:
            raise RuntimeError("Écriture interdite en essai à blanc")  # garde-fou
        url = self.base + chemin
        data = json.dumps(corps).encode() if corps is not None else None
        for essai in range(6):
            req = urllib.request.Request(url, data=data, method=methode, headers={
                "X-Api-Key": self.cle, "Accept": "application/json", "Content-Type": "application/json"})
            self.appels += 1
            try:
                with urllib.request.urlopen(req, timeout=60) as rep:
                    texte = rep.read()
                    return rep.status, (json.loads(texte) if texte else None)
            except urllib.error.HTTPError as e:
                if e.code == 429 and essai < 5:
                    pause = e.headers.get("Retry-After")
                    pause = int(pause) if pause and pause.isdigit() else 60
                    print(f"  Limite de Plane (60 requêtes/min), pause de {min(pause, 90)} s…", file=sys.stderr)
                    attendre(min(pause, 90))
                    continue
                try:
                    detail = json.loads(e.read() or b"null")
                except ValueError:
                    detail = None
                if e.code == 409:
                    return 409, detail
                if e.code in (401, 403):
                    raise ErreurImport(f"Accès refusé par Plane ({e.code}) : clé API fausse ou sans droit")
                if e.code == 404:
                    raise ErreurImport(f"Introuvable (404) : {methode} {chemin} — espace ou ID de projet faux ?")
                raise ErreurImport(f"Plane répond {e.code} sur {methode} {chemin} : {detail}")
            except urllib.error.URLError as e:
                raise ErreurImport(f"Plane injoignable : {e.reason}")
        raise ErreurImport(f"Trop de refus (429) sur {chemin}")

    def liste(self, chemin):
        resultats, curseur = [], None
        while True:
            params = {"per_page": 1000}
            if curseur:
                params["cursor"] = curseur
            _, rep = self.requete("GET", f"{chemin}?{urllib.parse.urlencode(params)}")
            if isinstance(rep, list):
                return rep
            resultats.extend(rep.get("results") or [])
            if not rep.get("next_page_results"):
                return resultats
            curseur = rep.get("next_cursor")


def date_plane(valeur, fuseau):
    """Date, dans le fuseau du projet, d'un datetime ISO renvoyé par Plane.

    Plane enregistre les dates de cycle à minuit dans le fuseau du projet, converti en UTC.
    """
    if not valeur:
        return None
    if len(valeur) == 10:
        return dt.date.fromisoformat(valeur)
    return dt.datetime.fromisoformat(valeur.replace("Z", "+00:00")).astimezone(fuseau).date()


def debut_jour(d):
    return f"{d.isoformat()}T00:00:00Z"


def executer(plane, plan, aujourd_hui, journal=print):
    """Crée ce qui manque. En essai à blanc (plane.ecrire = False), ne fait que des GET."""
    ecrire = plane.ecrire
    verbe = "créé" if ecrire else "à créer"
    bilan = {"tickets_crees": 0, "tickets_presents": 0, "tickets_completes": 0, "liens_crees": 0,
             "cycles_crees": 0, "actions": 0}

    projet = plane.requete("GET", "/")[1] or {}
    journal(f"Projet Plane : « {projet.get('name', '?')} » ({projet.get('identifier', '?')})")
    if projet.get("cycle_view") is False:
        raise ErreurImport("Les cycles sont désactivés dans ce projet : active « Cycles » dans les réglages du projet "
                           "(adresse …/settings/projects/ID-DU-PROJET/features)")
    fuseau = ZoneInfo(projet.get("timezone") or "UTC")

    etats = {}
    for e in sorted(plane.liste("/states/"), key=lambda e: e.get("sequence") or 0):
        etats.setdefault(e["group"], e["id"])
    for groupe in {t["groupe"] for t in plan["parents"] + plan["tickets"]}:
        if groupe not in etats:
            raise ErreurImport(f"Aucun état du groupe « {groupe} » dans le projet Plane")

    existants = {i["external_id"]: i for i in plane.liste("/work-items/") if i.get("external_source") == SOURCE}
    cycles_existants = {c["external_id"]: c for c in plane.liste("/cycles/") if c.get("external_source") == SOURCE}

    # 1. Tickets parents (phases, sprints), puis sous-tickets et liens
    ids = {}
    for t in plan["parents"] + plan["tickets"]:
        parent_id = ids.get(t["parent"]) if t["parent"] else None
        voulu = {"parent": parent_id,
                 "start_date": t["debut"].isoformat() if t["debut"] else None,
                 "target_date": t["fin"].isoformat() if t["fin"] else None}
        present = existants.get(t["clickup_id"])
        if present:
            ids[t["clickup_id"]] = present["id"]
            bilan["tickets_presents"] += 1
            # Import déjà fait : on complète ce qui manque (parent, dates), sans rien remplacer.
            manque = {k: v for k, v in voulu.items() if v and not present.get(k)}
            noms = [{"parent": "parent", "start_date": "début", "target_date": "fin"}[k] for k in manque]
            if t["parent"] and not parent_id and not present.get("parent"):
                noms.insert(0, "parent")  # essai à blanc : le ticket parent n'existe pas encore
            if noms:
                bilan["actions"] += 1
                if ecrire and manque:
                    plane.requete("PATCH", f"/work-items/{present['id']}/", manque)
                    bilan["tickets_completes"] += 1
                quoi = ", ".join(noms)
                journal(f"  Ticket {'complété' if ecrire else 'à compléter'} ({quoi}) : {t['titre'][:60]}")
        else:
            bilan["actions"] += 1
            if ecrire:
                corps = {
                    "name": t["titre"],
                    "description_html": t["description_html"],
                    "state": etats[t["groupe"]],
                    "priority": t["priorite"],
                    "external_source": SOURCE,
                    "external_id": t["clickup_id"],
                }
                corps.update({k: v for k, v in voulu.items() if v})
                code, rep = plane.requete("POST", "/work-items/", corps)
                ids[t["clickup_id"]] = rep["id"]
                if code == 409:
                    bilan["tickets_presents"] += 1
                else:
                    bilan["tickets_crees"] += 1
            genre = "Ticket parent" if t in plan["parents"] else "Ticket"
            journal(f"  {genre} {verbe} : {t['titre'][:70]}")
        if not t["liens"]:
            continue
        deja = set()
        if t["clickup_id"] in ids:
            deja = {l.get("url") for l in plane.liste(f"/work-items/{ids[t['clickup_id']]}/links/")}
        for lien in t["liens"]:
            if lien["url"] in deja:
                continue
            bilan["actions"] += 1
            if ecrire:
                plane.requete("POST", f"/work-items/{ids[t['clickup_id']]}/links/", lien)
                bilan["liens_crees"] += 1
            journal(f"    Lien {verbe} : {lien['title']}")

    # 2. Cycles : créés avec une fin future, tickets ajoutés, puis vraies dates.
    for c in plan["cycles"]:
        membres = [t["clickup_id"] for t in plan["tickets"] if t["cycle"] == c["clickup_id"]]
        cycle = cycles_existants.get(c["clickup_id"])
        fin_reelle_passee = c["fin"] < aujourd_hui
        if not cycle:
            bilan["actions"] += 1
            fin_creation = aujourd_hui + dt.timedelta(days=FIN_PROVISOIRE_JOURS) if fin_reelle_passee else c["fin"]
            journal(f"  Cycle {verbe} : {c['nom']} ({c['debut']} → {c['fin']}, {len(membres)} tickets)")
            if not ecrire:
                continue
            code, cycle = plane.requete("POST", "/cycles/", {
                "name": c["nom"], "start_date": debut_jour(c["debut"]), "end_date": debut_jour(fin_creation),
                "external_source": SOURCE, "external_id": c["clickup_id"]})
            if code == 409:
                cycle = plane.requete("GET", f"/cycles/{cycle['id']}/")[1]
            else:
                bilan["cycles_crees"] += 1
        dans_cycle = {i.get("id") or i.get("issue") for i in plane.liste(f"/cycles/{cycle['id']}/cycle-issues/")}
        manquants = [ids[m] for m in membres if m in ids and ids[m] not in dans_cycle]
        a_creer = [m for m in membres if m not in ids]  # essai à blanc : tickets pas encore créés
        fin_actuelle = date_plane(cycle.get("end_date"), fuseau)
        if manquants or a_creer:
            if fin_actuelle and fin_actuelle < aujourd_hui:
                raise ErreurImport(
                    f"Cycle « {c['nom']} » déjà terminé dans Plane : impossible d'y ajouter "
                    f"{len(manquants) + len(a_creer)} ticket(s). Le supprimer dans Plane puis relancer.")
            bilan["actions"] += 1
            journal(f"  Ajout au cycle « {c['nom']} » : {len(manquants) + len(a_creer)} ticket(s)")
            if ecrire and manquants:
                plane.requete("POST", f"/cycles/{cycle['id']}/cycle-issues/", {"issues": manquants})
        if fin_actuelle != c["fin"] or date_plane(cycle.get("start_date"), fuseau) != c["debut"]:
            if fin_actuelle and fin_actuelle < aujourd_hui:
                journal(f"  ⚠ Cycle « {c['nom']} » terminé avec d'autres dates que ClickUp : laissé tel quel")
                continue
            bilan["actions"] += 1
            journal(f"  Dates du cycle « {c['nom']} » : {c['debut']} → {c['fin']}")
            if ecrire:
                plane.requete("PATCH", f"/cycles/{cycle['id']}/", {
                    "start_date": debut_jour(c["debut"]), "end_date": debut_jour(c["fin"])})
    return bilan


# ---------------------------------------------------------------- lancement

def lire_config(chemin):
    if not chemin.exists():
        raise ErreurImport(f"Fichier absent : {chemin}")
    return yaml.safe_load(chemin.read_text(encoding="utf-8")) or {}


def url_plane(config):
    url = (config.get("plane") or {}).get("url")
    if url:
        return url
    if PLATFORM.exists():
        domaine = (yaml.safe_load(PLATFORM.read_text(encoding="utf-8")) or {}).get("projectos_base_domain")
        if domaine:
            return f"https://plane.{domaine}"
    raise ErreurImport("Adresse de Plane inconnue : ajoute plane.url dans pld.yml")


def analyser_arguments(argv):
    p = argparse.ArgumentParser(
        prog="clickup_importer.py", add_help=False,
        description="Importe l'historique ClickUp dans Plane. Par défaut : essai à blanc (lecture seule).")
    p.add_argument("-h", "--aide", action="help", help="afficher cette aide")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--plan", action="store_true", help="hors ligne : afficher le plan sans contacter Plane")
    mode.add_argument("--appliquer", action="store_true", help="créer réellement dans Plane")
    p.add_argument("--projet", help="ID d'un autre projet Plane (ex. projet jetable pour un essai)")
    p.add_argument("--config", type=Path, default=CONFIG, help=f"table de correspondance (défaut : {CONFIG})")
    p.add_argument("--oui", action="store_true", help="ne pas demander de confirmation (tests)")
    return p.parse_args(argv)


def main(argv=None, aujourd_hui=None):
    args = analyser_arguments(argv)
    aujourd_hui = aujourd_hui or dt.datetime.now(FUSEAU).date()
    try:
        config = lire_config(args.config)
        imp = config.get("clickup_import") or {}
        fichier = Path(imp.get("fichier") or "")
        if not fichier.is_absolute():
            fichier = EXTRACTIONS / fichier
        if not fichier.is_file():
            raise ErreurImport(f"Extraction ClickUp absente : {fichier}")
        donnees = json.loads(fichier.read_text(encoding="utf-8"))
        plan = construire_plan(donnees, imp, aujourd_hui)
    except (ErreurImport, ValueError) as e:
        print(f"Échec : {e}", file=sys.stderr)
        return 1

    afficher_plan(plan)
    if plan["erreurs"]:
        print("\nÀ corriger dans pld.yml avant l'import :", file=sys.stderr)
        for e in plan["erreurs"]:
            print(f"  ✗ {e}", file=sys.stderr)
        return 1
    if args.plan:
        return 0

    plane_cfg = config.get("plane") or {}
    projet = args.projet or plane_cfg.get("projet_id")
    try:
        url = url_plane(config)
        if not plane_cfg.get("espace") or not projet:
            raise ErreurImport("plane.espace ou plane.projet_id manquant dans pld.yml")
    except ErreurImport as e:
        print(f"Échec : {e}", file=sys.stderr)
        return 1
    cle = os.environ.get("PLANE_API_KEY") or getpass.getpass("Clé API Plane (saisie masquée) : ")
    if not cle.strip():
        print("Aucune clé saisie.", file=sys.stderr)
        return 2
    plane = Plane(url, cle.strip(), plane_cfg["espace"], projet, ecrire=False)

    print("\n=== Essai à blanc (lecture seule) ===")
    try:
        bilan = executer(plane, plan, aujourd_hui)
    except ErreurImport as e:
        print(f"Échec : {e}", file=sys.stderr)
        return 1
    print(f"\n{bilan['actions']} action(s) à faire, {bilan['tickets_presents']} ticket(s) déjà importé(s). "
          f"({plane.appels} requêtes, lecture seule)")
    if not args.appliquer or bilan["actions"] == 0:
        if bilan["actions"] == 0:
            print("Rien à faire : tout est déjà dans Plane.")
        return 0

    if not args.oui:
        rep = input(f"\nÉcrire dans le projet Plane {projet} ? Tape oui pour continuer : ")
        if rep.strip().lower() != "oui":
            print("Annulé, rien n'a été écrit.")
            return 0
    print("\n=== Import ===")
    plane.ecrire = True
    try:
        bilan = executer(plane, plan, aujourd_hui)
    except ErreurImport as e:
        print(f"Échec : {e}\nRelancer la même commande reprend là où l'import s'est arrêté.", file=sys.stderr)
        return 1
    print(f"\nTerminé : {bilan['tickets_crees']} ticket(s), {bilan['liens_crees']} lien(s), "
          f"{bilan['cycles_crees']} cycle(s) créés, {bilan['tickets_completes']} ticket(s) complétés. "
          f"({plane.appels} requêtes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
