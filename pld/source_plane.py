"""Lecture seule du projet Plane pour le PLD : projet, états, étiquettes, membres, estimations,
cycles (avec leurs tickets), tickets (avec liens, fiche story, date de fin réelle).

Uniquement des requêtes GET (garde-fou dans PlaneLecture.get). Routes de l'API publique
de Plane v1.4.2 : apps/api/plane/api/urls/ (work-items, cycles, cycle-issues, links,
states, labels, members, estimates).

Le résultat est un dictionnaire JSON sans secret ni e-mail.
"""
import datetime as dt
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from zoneinfo import ZoneInfo

import fiche_story

PLATFORM = Path.home() / ".config" / "projectos" / "platform.yml"
LIEN_GITHUB = re.compile(r"https://github\.com/(?P<org>[A-Za-z0-9_.-]+)/(?P<depot>[A-Za-z0-9_.-]+)/issues/(?P<num>[0-9]+)")
TERMINE_LE = re.compile(r"Terminé le\s*:\s*(\d{4}-\d{2}-\d{2})")
attendre = time.sleep  # remplacé dans les tests


class ErreurPlane(Exception):
    pass


class PlaneLecture:
    def __init__(self, url, cle, espace, projet_id):
        self.base = f"{url.rstrip('/')}/api/v1/workspaces/{espace}/projects/{projet_id}"
        self.cle, self.appels = cle, 0

    def get(self, chemin, absent_ok=False):
        url = self.base + chemin
        for essai in range(6):
            req = urllib.request.Request(url, method="GET", headers={"X-Api-Key": self.cle, "Accept": "application/json"})
            assert req.get_method() == "GET"  # garde-fou : lecture seule
            self.appels += 1
            try:
                with urllib.request.urlopen(req, timeout=60) as rep:
                    texte = rep.read()
                    return json.loads(texte) if texte else None
            except urllib.error.HTTPError as e:
                if e.code == 429 and essai < 5:
                    pause = e.headers.get("Retry-After")
                    pause = min(int(pause) if pause and pause.isdigit() else 60, 90)
                    print(f"  Limite de Plane (60 requêtes/min), pause de {pause} s…", file=sys.stderr)
                    attendre(pause)
                    continue
                if e.code == 404 and absent_ok:
                    return None
                if e.code in (401, 403):
                    raise ErreurPlane(f"Accès refusé par Plane ({e.code}) : clé API fausse, expirée ou sans droit")
                if e.code == 404:
                    raise ErreurPlane(f"Introuvable (404) : {chemin} — espace ou ID de projet faux ?")
                raise ErreurPlane(f"Plane répond {e.code} sur {chemin}")
            except urllib.error.URLError as e:
                raise ErreurPlane(f"Plane injoignable : {e.reason}")
        raise ErreurPlane(f"Trop de refus (429) sur {chemin}")

    def liste(self, chemin):
        resultats, curseur = [], None
        while True:
            params = {"per_page": 1000}
            if curseur:
                params["cursor"] = curseur
            rep = self.get(f"{chemin}?{urllib.parse.urlencode(params)}")
            if isinstance(rep, list):
                return rep
            resultats.extend((rep or {}).get("results") or [])
            if not (rep or {}).get("next_page_results"):
                return resultats
            curseur = rep.get("next_cursor")


def url_plane(cfg, platform=PLATFORM):
    if cfg.plane_url:
        return cfg.plane_url
    if platform.exists():
        import yaml
        domaine = (yaml.safe_load(platform.read_text(encoding="utf-8")) or {}).get("projectos_base_domain")
        if domaine:
            return f"https://plane.{domaine}"
    raise ErreurPlane("Adresse de Plane inconnue : ajoute plane.url dans pld.yml")


# ---------------------------------------------------------------- conversions

class _Texte(HTMLParser):
    """HTML de Plane (éditeur Tiptap) → texte : un paragraphe par ligne, listes en « - »."""
    BLOCS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "pre", "tr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.morceaux, self.case, self.dans_li = [], None, 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "br":
            self.morceaux.append("\n")
        elif tag == "li":
            self.morceaux.append("\n- ")
            self.dans_li += 1
            if a.get("data-type") == "taskItem":
                self.case = "[x] " if a.get("data-checked") == "true" else "[ ] "
        elif tag in self.BLOCS and not self.dans_li:  # <li><p>…</p></li> : même ligne que la puce
            self.morceaux.append("\n")

    def handle_endtag(self, tag):
        if tag == "li":
            self.dans_li = max(0, self.dans_li - 1)
        elif (tag in self.BLOCS and not self.dans_li) or tag in ("ul", "ol"):
            self.morceaux.append("\n")

    def handle_data(self, data):
        if self.dans_li and not data.strip():
            return  # blancs entre les balises d'une puce
        if self.case:
            self.morceaux.append(self.case)
            self.case = None
        self.morceaux.append(data)


def html_vers_texte(contenu):
    if not contenu:
        return ""
    p = _Texte()
    p.feed(contenu)
    p.close()
    lignes = [re.sub(r"[ \t\u00a0]+", " ", l).strip() for l in "".join(p.morceaux).splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lignes)).strip()


def date_plane(valeur, fuseau):
    """Date, dans le fuseau du projet, d'une date ou d'un datetime ISO renvoyé par Plane."""
    if not valeur:
        return None
    if len(valeur) == 10:
        return dt.date.fromisoformat(valeur)
    return dt.datetime.fromisoformat(valeur.replace("Z", "+00:00")).astimezone(fuseau).date()


def refs_github(liens, org):
    """« Frontend#12 » pour chaque lien vers une issue de l'organisation, sans doublon, dans l'ordre."""
    refs = []
    for lien in liens:
        m = LIEN_GITHUB.fullmatch((lien.get("url") or "").strip().rstrip("/"))
        if m and m.group("org").lower() == org.lower():
            ref = f"{m.group('depot')}#{m.group('num')}"
            if ref not in refs:
                refs.append(ref)
    return refs


def _iso(d):
    return d.isoformat() if d else None


# ---------------------------------------------------------------- extraction

def extraire(plane, org, maintenant=None, journal=print):
    maintenant = maintenant or dt.datetime.now(dt.timezone.utc)
    projet = plane.get("/") or {}
    fuseau = ZoneInfo(projet.get("timezone") or "UTC")
    prefixe = projet.get("identifier") or "?"
    journal(f"Projet Plane : « {projet.get('name', '?')} » ({prefixe})")

    etats = {e["id"]: {"nom": e.get("name"), "groupe": e.get("group")} for e in plane.liste("/states/")}
    etiquettes = {l["id"]: l.get("name") for l in plane.liste("/labels/")}
    membres = {}
    for m in plane.liste("/members/"):
        nom = m.get("display_name") or " ".join(x for x in (m.get("first_name"), m.get("last_name")) if x)
        membres[m["id"]] = nom or m["id"][:8]  # ni e-mail ni avatar

    points = {}
    estimation = plane.get("/estimates/", absent_ok=True)
    if isinstance(estimation, dict) and estimation.get("id"):
        for p in plane.liste(f"/estimates/{estimation['id']}/estimate-points/"):
            points[p["id"]] = p.get("value")

    cycles, cycle_de = [], {}
    for c in sorted(plane.liste("/cycles/"), key=lambda c: c.get("start_date") or ""):
        ids = [i["id"] for i in plane.liste(f"/cycles/{c['id']}/cycle-issues/")]
        cycles.append({"id": c["id"], "nom": c.get("name"), "debut": _iso(date_plane(c.get("start_date"), fuseau)),
                       "fin": _iso(date_plane(c.get("end_date"), fuseau)), "tickets": ids})
        for i in ids:
            cycle_de[i] = c["id"]

    brut = plane.liste("/work-items/")
    parents = {t.get("parent") for t in brut if t.get("parent")}
    tickets = []
    for t in sorted(brut, key=lambda t: t.get("sequence_id") or 0):
        texte = html_vers_texte(t.get("description_html"))
        liens = [{"url": l.get("url"), "titre": l.get("title")} for l in plane.liste(f"/work-items/{t['id']}/links/")]
        etat = etats.get(t.get("state")) or {}
        termine = TERMINE_LE.search(texte)
        fiche = fiche_story.extraire(texte)
        tickets.append({
            "id": t["id"],
            "ref": f"{prefixe}-{t.get('sequence_id')}",
            "titre": t.get("name"),
            "etat": etat.get("nom"),
            "groupe": etat.get("groupe"),
            "parent": t.get("parent"),
            "est_parent": t["id"] in parents,
            "cycle": cycle_de.get(t["id"]),
            "debut": t.get("start_date"),
            "fin": t.get("target_date"),
            "termine_le": termine.group(1) if termine else _iso(date_plane(t.get("completed_at"), fuseau)),
            "estimation": points.get(t.get("estimate_point")),
            "etiquettes": sorted(etiquettes.get(l, "?") for l in t.get("labels") or []),
            "assignes": [membres.get(a, a[:8]) for a in t.get("assignees") or []],
            "source": f"{t['external_source']}:{t.get('external_id')}" if t.get("external_source") else None,
            "liens": liens,
            "github": refs_github(liens, org),
            "fiche": fiche,
            "fiche_manquante": fiche_story.manquantes(fiche),
            "texte": texte,
        })
    return {
        "extrait_le": maintenant.isoformat(timespec="seconds"),
        "projet": {"nom": projet.get("name"), "identifiant": prefixe, "fuseau": str(fuseau)},
        "estimations": bool(points),
        "cycles": cycles,
        "tickets": tickets,
        "requetes": plane.appels,
    }


def sprints_vers_periode(extraction, noms):
    """Dates couvertes par les cycles nommés (du premier début à la dernière fin)."""
    par_nom = {c["nom"]: c for c in extraction["cycles"]}
    inconnus = [n for n in noms if n not in par_nom]
    if inconnus:
        connus = ", ".join(f"« {n} »" for n in par_nom) or "aucun"
        raise ErreurPlane(f"Sprint inconnu dans Plane : {', '.join(inconnus)} (cycles : {connus})")
    choisis = [par_nom[n] for n in noms]
    sans_dates = [c["nom"] for c in choisis if not (c["debut"] and c["fin"])]
    if sans_dates:
        raise ErreurPlane(f"Cycle sans dates dans Plane : {', '.join(sans_dates)}")
    return (dt.date.fromisoformat(min(c["debut"] for c in choisis)),
            dt.date.fromisoformat(max(c["fin"] for c in choisis)))


def resume(extraction, du=None, au=None):
    """Lignes de résumé affichées après l'extraction."""
    tickets = extraction["tickets"]
    cartes = [t for t in tickets if not t["est_parent"]]
    par_cycle = {c["id"]: c for c in extraction["cycles"]}
    lignes = [f"Cycles : {len(extraction['cycles'])}"]
    for c in extraction["cycles"]:
        lignes.append(f"  {c['nom']} : {c['debut']} → {c['fin']}, {len(c['tickets'])} ticket(s)")
    lignes += [
        f"Tickets : {len(tickets)} ({len(tickets) - len(cartes)} parent(s), {len(cartes)} carte(s))",
        f"  terminées : {sum(t['groupe'] == 'completed' for t in cartes)}, "
        f"sans cycle : {sum(not t['cycle'] for t in cartes)}",
        f"Liens GitHub : {sum(len(t['github']) for t in tickets)} "
        f"({len({r for t in tickets for r in t['github']})} issues différentes)",
        f"Fiches stories complètes : {sum(not t['fiche_manquante'] for t in cartes)} / {len(cartes)}",
        f"Estimations dans Plane : {'oui' if extraction['estimations'] else 'non (système d’estimation absent)'}",
    ]
    if du and au:
        dans = [t for t in cartes if _dans_periode(t, par_cycle, du, au)]
        lignes.append(f"Cartes touchant la période {du} → {au} : {len(dans)}")
    return lignes


def _dans_periode(ticket, par_cycle, du, au):
    """Carte rattachée à la période : par son cycle, sinon par ses dates."""
    c = par_cycle.get(ticket["cycle"])
    debut, fin = (c["debut"], c["fin"]) if c else (ticket["debut"], ticket["termine_le"] or ticket["fin"])
    if not debut and not fin:
        return False
    debut = dt.date.fromisoformat(debut or fin)
    fin = dt.date.fromisoformat(fin or debut)
    return debut <= au and fin >= du
