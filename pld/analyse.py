"""Croisement Plane ↔ GitHub, cartes du PLD, charges et contrôles de cohérence.

Règles (docs/plan-pld.md, « Règles de croisement ») :
  1. ticket Plane avec issue(s) GitHub → une carte ; GitHub donne l'état réel, le responsable, les preuves ;
  2. issue d'un projet GitHub citée par aucun ticket Plane → carte à part ;
  3. ticket Plane sans lien GitHub → carte Plane seule ;
  4. une issue citée par deux tickets → comptée une fois dans les preuves, signalée ;
  5. tickets parents (phases, sprints) → pas des cartes.
"""
import datetime as dt
from dataclasses import dataclass, field

import fiche_story

A_FAIRE, EN_COURS, TERMINE, BLOQUE, ANNULE = "À faire", "En cours", "Terminé", "Bloqué", "Annulé"
ETAT_PLANE = {"backlog": A_FAIRE, "unstarted": A_FAIRE, "started": EN_COURS, "completed": TERMINE, "cancelled": ANNULE}
STATUS_GITHUB = {"backlog": A_FAIRE, "ready": A_FAIRE, "todo": A_FAIRE, "to do": A_FAIRE,
                 "in progress": EN_COURS, "in review": EN_COURS, "done": TERMINE}
AVANCEMENT = {A_FAIRE: 0, EN_COURS: 50, TERMINE: 100, ANNULE: 0}
AVANCEMENT_REVUE = 80  # Status « In review »
TAILLE_JOURS = {"XS": 0.5, "S": 1, "M": 2, "L": 3, "XL": 4}
ETIQUETTES_BLOQUE = {"bloqué", "bloque", "blocked", "blocker"}
CHARGE_MIN, CHARGE_MAX = 0.5, 4
JOURS_PAR_MOIS = 2
EQUIPE = "Équipe (non attribué)"
ERREUR, ATTENTION, INFO = "erreur", "attention", "info"


@dataclass
class Carte:
    cle: str                      # FLOWL-12 ou Frontend#40
    origine: str                  # plane | github
    titre: str
    pseudo: str | None = None     # compte GitHub du responsable
    responsable: str = EQUIPE     # nom affiché
    autres: list = field(default_factory=list)
    charge: float | None = None
    charge_source: str | None = None
    etat: str = A_FAIRE
    etat_plane: str | None = None
    avancement: int = 0
    debut: dt.date | None = None
    fin: dt.date | None = None
    termine_le: dt.date | None = None
    sprint: str | None = None
    sprint_debut: dt.date | None = None
    sprint_fin: dt.date | None = None
    fiche: dict = field(default_factory=dict)
    bloquants: str = ""
    issues: list = field(default_factory=list)   # refs GitHub
    urls: list = field(default_factory=list)
    preuves: list = field(default_factory=list)  # PR fusionnées
    domaine: str | None = None
    dans_periode: bool = False
    id_pld: str = ""

    @property
    def lien(self):
        return self.urls[0] if self.urls else None


@dataclass
class Controle:
    niveau: str
    critere: str
    message: str
    carte: str | None = None


@dataclass
class Analyse:
    cartes: list
    membres: list           # noms dans l'ordre du PLD (membres de pld.yml, puis l'équipe si besoin)
    controles: list
    du: dt.date
    au: dt.date
    pr_periode: list
    charge_attendue: float
    stats: dict


def _date(valeur):
    if not valeur:
        return None
    return valeur if isinstance(valeur, dt.date) else dt.date.fromisoformat(str(valeur)[:10])


def _nombre(valeur):
    try:
        return float(str(valeur).replace(",", "."))
    except (TypeError, ValueError):
        return None


def _bloque(etiquettes, bloquants):
    if any(e.strip().lower() in ETIQUETTES_BLOQUE for e in etiquettes):
        return True
    texte = (bloquants or "").strip().lower().rstrip(".")
    return bool(texte) and texte not in {"aucun", "aucune", "none", "rien", "non", "-", "n/a"}


def etat_issue(issue):
    """(état, avancement) d'une issue GitHub : fermeture d'abord, puis le champ Status du projet."""
    if issue.get("etat") == "CLOSED":
        return (ANNULE, 0) if issue.get("raison") in ("NOT_PLANNED", "DUPLICATE") else (TERMINE, 100)
    status = str(issue.get("champs", {}).get("Status") or "").strip().lower()
    etat = STATUS_GITHUB.get(status, A_FAIRE)
    return etat, (AVANCEMENT_REVUE if status == "in review" else AVANCEMENT[etat])


def _combiner(etats):
    """État d'une carte qui regroupe plusieurs issues."""
    utiles = [(e, a) for e, a in etats if e != ANNULE]
    if not utiles:
        return ANNULE, 0
    moyenne = round(sum(a for _, a in utiles) / len(utiles))
    if all(e == TERMINE for e, _ in utiles):
        return TERMINE, 100
    if any(e in (EN_COURS, TERMINE) for e, _ in utiles):
        return EN_COURS, moyenne
    return A_FAIRE, moyenne


def _charge_github(issues):
    estimations = [_nombre(i["champs"].get("Estimate")) for i in issues]
    estimations = [e for e in estimations if e is not None]
    if estimations:
        return sum(estimations), "Estimate (GitHub)"
    tailles = [TAILLE_JOURS.get(str(i["champs"].get("Size") or "").upper()) for i in issues]
    tailles = [t for t in tailles if t is not None]
    if tailles:
        return sum(tailles), "Size (GitHub)"
    return None, None


def _fiche_github(issues):
    for i in issues:
        f = fiche_story.extraire(i.get("corps"))
        if f:
            return f
    return {}


class _Noms:
    def __init__(self, cfg):
        self.cfg, self.inconnus = cfg, set()

    def nom(self, pseudo):
        if pseudo in self.cfg.membres:
            return self.cfg.membres[pseudo]
        self.inconnus.add(pseudo)
        return pseudo

    def utiles(self, pseudos):
        return [p for p in pseudos if p and p not in self.cfg.ignores]


def construire_cartes(cfg, plane, github, du, au, aujourd_hui):
    issues = github["issues"]
    noms = _Noms(cfg)
    controles = []
    cycles = {c["id"]: c for c in plane["cycles"]}
    citee_par = {}
    for t in plane["tickets"]:
        if not t["est_parent"]:
            for ref in t["github"]:
                citee_par.setdefault(ref, []).append(t["ref"])
    prs_par_issue = {}
    for pr in github["pr_fusionnees"]:
        for ref in pr["ferme"]:
            prs_par_issue.setdefault(ref, []).append(pr)

    cartes = []
    for t in plane["tickets"]:
        if t["est_parent"]:
            continue
        liees = [issues[r] for r in t["github"] if r in issues]
        c = Carte(cle=t["ref"], origine="plane", titre=t["titre"], issues=list(t["github"]),
                  etat_plane=ETAT_PLANE.get(t["groupe"], A_FAIRE), fiche=t["fiche"] or {},
                  domaine=next((e for e in t["etiquettes"] if e in ("Frontend", "Backend", "Mobile", "DevOps")), None))
        cycle = cycles.get(t["cycle"])
        if cycle:
            c.sprint, c.sprint_debut, c.sprint_fin = cycle["nom"], _date(cycle["debut"]), _date(cycle["fin"])
        c.debut, c.fin = _date(t["debut"]), _date(t["fin"])
        c.charge = _nombre(t["estimation"])
        c.charge_source = "Estimation (Plane)" if c.charge is not None else None
        if liees:
            c.etat, c.avancement = _combiner([etat_issue(i) for i in liees])
            if c.charge is None:
                c.charge, c.charge_source = _charge_github(liees)
            if fiche_story.manquantes(c.fiche):  # fiche Plane incomplète : celle de l'issue, si plus complète
                fg = _fiche_github(liees)
                if fg and len(fiche_story.manquantes(fg)) < len(fiche_story.manquantes(c.fiche)):
                    c.fiche = fg
            pseudos = noms.utiles([a for i in liees for a in i["assignes"]])
            debuts = [_date(i["champs"].get("Start date")) for i in liees if i["champs"].get("Start date")]
            fins = [_date(i["champs"].get("Target date")) for i in liees if i["champs"].get("Target date")]
            c.debut = c.debut or (min(debuts) if debuts else None)
            c.fin = c.fin or (max(fins) if fins else None)
            iteration = next((i["champs"]["Iteration"] for i in liees if i["champs"].get("Iteration")), None)
            if not c.sprint and iteration:
                c.sprint = iteration["titre"]
            if c.etat == TERMINE:
                fermees = [_date(i["fermee_le"]) for i in liees if i["fermee_le"]]  # GitHub d'abord
                c.termine_le = max(fermees) if fermees else (_date(t["termine_le"]) if c.etat_plane == TERMINE else None)
            c.urls = [i["url"] for i in liees]
            preuves = {p["ref"]: p for i in liees for p in i["pr"] if p.get("fusionnee_le")}
            preuves.update({p["ref"]: p for r in t["github"] for p in prs_par_issue.get(r, [])})
            c.preuves = sorted(preuves.values(), key=lambda p: p.get("fusionnee_le") or "")
            if not pseudos:
                pseudos = noms.utiles([p.get("auteur") for p in c.preuves])
            etiquettes = [e for i in liees for e in i["etiquettes"]] + t["etiquettes"]
            if not c.domaine:
                c.domaine = liees[0]["depot"]
            if c.etat != c.etat_plane and c.etat_plane is not None:
                controles.append(Controle(INFO, "Réel vs planifié",
                                          f"État Plane « {c.etat_plane} », GitHub « {c.etat} » : GitHub retenu", c.cle))
        else:
            c.etat = c.etat_plane
            c.avancement = AVANCEMENT.get(c.etat, 0)
            c.termine_le = _date(t["termine_le"]) if c.etat == TERMINE else None
            pseudos, etiquettes = [], t["etiquettes"]
            if t["assignes"]:  # comptes Plane (pas de pseudo GitHub) : nom affiché tel quel
                c.responsable, c.autres = t["assignes"][0], t["assignes"][1:]
        for ref in t["github"]:
            if ref not in issues:
                controles.append(Controle(ERREUR, "Complétude", f"Issue {ref} citée par Plane mais introuvable dans GitHub", c.cle))
        bloquants = c.fiche.get("bloquants", "")
        if pseudos:
            c.pseudo = pseudos[0]
            c.responsable = noms.nom(pseudos[0])
            c.autres = [noms.nom(p) for p in dict.fromkeys(pseudos[1:]) if p != pseudos[0]]
        c.bloquants = bloquants if _bloque([], bloquants) else ""
        if c.etat in (A_FAIRE, EN_COURS) and _bloque(etiquettes, bloquants):
            c.etat = BLOQUE
        cartes.append(c)

    # Issues des projets GitHub citées par aucun ticket Plane
    for ref, i in sorted(issues.items()):
        if ref in citee_par or not i["projets"]:
            continue
        c = Carte(cle=ref, origine="github", titre=i["titre"], issues=[ref], urls=[i["url"]], domaine=i["depot"])
        c.etat, c.avancement = etat_issue(i)
        c.charge, c.charge_source = _charge_github([i])
        c.fiche = fiche_story.extraire(i["corps"])
        c.debut = _date(i["champs"].get("Start date")) or _date(i["creee_le"])
        c.fin = _date(i["champs"].get("Target date"))
        c.termine_le = _date(i["fermee_le"]) if c.etat == TERMINE else None
        if i["champs"].get("Iteration"):
            it = i["champs"]["Iteration"]
            c.sprint, c.sprint_debut = it["titre"], _date(it.get("debut"))
            if c.sprint_debut and it.get("jours"):
                c.sprint_fin = c.sprint_debut + dt.timedelta(days=int(it["jours"]) - 1)
        preuves = {p["ref"]: p for p in i["pr"] if p.get("fusionnee_le")}
        preuves.update({p["ref"]: p for p in prs_par_issue.get(ref, [])})
        c.preuves = sorted(preuves.values(), key=lambda p: p.get("fusionnee_le") or "")
        pseudos = noms.utiles(i["assignes"]) or noms.utiles([p.get("auteur") for p in c.preuves])
        if pseudos:
            c.pseudo, c.responsable = pseudos[0], noms.nom(pseudos[0])
            c.autres = [noms.nom(p) for p in dict.fromkeys(pseudos[1:]) if p != pseudos[0]]
        c.bloquants = c.fiche.get("bloquants", "") if _bloque([], c.fiche.get("bloquants")) else ""
        if c.etat in (A_FAIRE, EN_COURS) and _bloque(i["etiquettes"], c.fiche.get("bloquants")):
            c.etat = BLOQUE
        cartes.append(c)

    for c in cartes:
        c.dans_periode = dans_periode(c, du, au)
    for ref, tickets in citee_par.items():
        if len(tickets) > 1:
            controles.append(Controle(INFO, "Cohérence", f"Issue {ref} citée par {len(tickets)} tickets ({', '.join(tickets)}) : "
                                      "comptée une fois dans les preuves"))
    for pseudo in sorted(noms.inconnus):
        controles.append(Controle(ATTENTION, "Complétude", f"Compte GitHub « {pseudo} » absent de pld.membres et de pld.ignores : "
                                  "affiché tel quel"))
    return cartes, controles


def intervalle(c):
    """Période couverte par une carte. Début : sprint, sinon dates. Fin : None tant que la carte
    n'est pas finie (travail toujours en cours), sinon la fin réelle, sinon la fin prévue."""
    debut = c.sprint_debut or c.debut or c.termine_le or c.fin
    if c.etat in (A_FAIRE, EN_COURS, BLOQUE):
        return debut, None
    return debut, c.termine_le or c.sprint_fin or c.fin


def dans_periode(c, du, au):
    """Une carte finie le jour où la période commence appartient à la période précédente."""
    debut, fin = intervalle(c)
    if debut is None:
        return c.etat in (EN_COURS, BLOQUE)  # travail en cours sans date
    return debut <= au and (fin is None or fin > du or debut >= du)


def _cle_tri(c):
    return (intervalle(c)[0] or dt.date.max, c.cle)


def numeroter(cartes, cfg, au):
    """Cartes visibles (commencées avant la fin de période), groupées par membre, numérotées k.i."""
    visibles = [c for c in cartes if c.dans_periode or (c.etat != ANNULE and (intervalle(c)[0] or au) <= au)]
    membres = list(dict.fromkeys(list(cfg.membres.values()) + sorted({c.responsable for c in visibles} - {EQUIPE})))
    if any(c.responsable == EQUIPE for c in visibles):
        membres.append(EQUIPE)
    avec_cartes = [m for m in membres if any(c.responsable == m for c in visibles)]
    rang = {m: k for k, m in enumerate(avec_cartes, 1)}
    for m in avec_cartes:
        for i, c in enumerate(sorted((c for c in visibles if c.responsable == m), key=_cle_tri), 1):
            c.id_pld = f"{rang[m]}.{i}"
    visibles.sort(key=lambda c: tuple(int(x) for x in c.id_pld.split(".")))
    return visibles, membres


def controler(cartes, membres, du, au, pr_periode, aujourd_hui, charge_attendue):
    controles = []
    periode = [c for c in cartes if c.dans_periode and c.etat != ANNULE]
    for c in periode:
        if c.charge is None:
            controles.append(Controle(ERREUR, "Charge", "Carte sans estimation (Estimate dans GitHub, ou estimation Plane)", c.cle))
        elif not CHARGE_MIN <= c.charge <= CHARGE_MAX:
            controles.append(Controle(ERREUR, "Charge", f"Charge de {c.charge:g} j hors de 0,5–4 j : découper la carte", c.cle))
        if c.responsable == EQUIPE:
            controles.append(Controle(ERREUR, "Qualité des cartes", "Carte sans responsable (assigné GitHub)", c.cle))
        if not (c.debut or c.sprint_debut) or not (c.fin or c.sprint_fin or c.termine_le):
            controles.append(Controle(ATTENTION, "Qualité des cartes", "Dates de début ou de fin prévues manquantes", c.cle))
        manque = fiche_story.manquantes(c.fiche)
        if manque:
            libelles = {"en_tant_que": "En tant que", "je_veux": "Je veux", "afin_de": "Afin de", "dod": "Definition of Done"}
            controles.append(Controle(ATTENTION, "Qualité des cartes",
                                      "Fiche story incomplète : " + ", ".join(libelles[m] for m in manque), c.cle))
        if c.etat == TERMINE and c.issues and not c.preuves:
            controles.append(Controle(ATTENTION, "Réel vs planifié", "Terminé sans PR fusionnée liée (preuve de livraison)", c.cle))
        fin_prevue = c.fin or c.sprint_fin
        if c.etat in (A_FAIRE, EN_COURS, BLOQUE) and fin_prevue and fin_prevue < aujourd_hui:
            controles.append(Controle(ERREUR, "Réel vs planifié", f"Fin prévue le {fin_prevue:%d/%m/%Y} dépassée, carte « {c.etat} »", c.cle))
        auteurs = {p.get("auteur") for p in c.preuves if p.get("auteur")}
        if c.pseudo and auteurs and c.pseudo not in auteurs:
            controles.append(Controle(INFO, "Information", f"Responsable {c.pseudo}, PR par {', '.join(sorted(auteurs))}", c.cle))
    couvertes = {r for c in cartes for r in c.issues}
    for pr in pr_periode:
        if not set(pr["ferme"]) & couvertes:
            controles.append(Controle(ATTENTION, "Complétude",
                                      f"PR {pr['ref']} fusionnée le {pr['fusionnee_le']} ({pr['auteur']}) sans carte liée : "
                                      f"« {pr['titre']} »"))
    for m in membres:
        if m == EQUIPE:
            continue
        charge = sum(c.charge or 0 for c in periode if c.responsable == m)
        if charge < 0.5 * charge_attendue or charge > 1.5 * charge_attendue:
            controles.append(Controle(ATTENTION, "Charge", f"{m} : {charge:g} j sur la période pour ~{charge_attendue:g} j attendus "
                                      f"({JOURS_PAR_MOIS} j par mois)"))
    return controles


def analyser(cfg, plane, github, du, au, aujourd_hui=None):
    aujourd_hui = aujourd_hui or dt.date.today()
    cartes, controles = construire_cartes(cfg, plane, github, du, au, aujourd_hui)
    visibles, membres = numeroter(cartes, cfg, au)
    mois = ((au - du).days + 1) / 30.44
    charge_attendue = round(JOURS_PAR_MOIS * mois * 2) / 2
    controles += controler(visibles, membres, du, au, github["pr_fusionnees"], aujourd_hui, charge_attendue)
    for ref in github.get("absentes", []):
        if not any(ref in c.message for c in controles):
            controles.append(Controle(ERREUR, "Complétude", f"Issue {ref} introuvable dans GitHub"))
    periode = [c for c in visibles if c.dans_periode and c.etat != ANNULE]
    stats = {
        "cartes": len(visibles),
        "periode": len(periode),
        "terminees": sum(c.etat == TERMINE for c in periode),
        "en_cours": sum(c.etat == EN_COURS for c in periode),
        "a_faire": sum(c.etat == A_FAIRE for c in periode),
        "bloquees": sum(c.etat == BLOQUE for c in periode),
        "charge_prevue": sum(c.charge or 0 for c in periode),
        "charge_realisee": sum(c.charge or 0 for c in periode if c.etat == TERMINE),
        "sans_estimation": sum(c.charge is None for c in periode),
        "pr": len(github["pr_fusionnees"]),
    }
    ordre = {ERREUR: 0, ATTENTION: 1, INFO: 2}
    controles.sort(key=lambda c: (ordre[c.niveau], c.critere, c.carte or ""))
    return Analyse(visibles, membres, controles, du, au, github["pr_fusionnees"], charge_attendue, stats)
