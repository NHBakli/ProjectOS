"""Configuration du générateur de PLD : lecture de pld.yml (hors Git) et choix de la période.

Clés lues (voir pld/pld.example.yml) :
  plane.espace, plane.projet_id, plane.url (facultatif)
  github.org, github.projets
  pld.projet, pld.remise_suivante, pld.debut_par_defaut, pld.membres, pld.ignores,
  pld.sortie, pld.modeles.docx, pld.modeles.xlsx,
  pld.responsable, pld.email, pld.promotion, pld.revisions,
  pld.textes.resume, pld.textes.schema, pld.textes.plan_alpha_beta, pld.textes.bloquants, pld.textes.commentaire
"""
import datetime as dt
import re
from dataclasses import dataclass, field
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    raise SystemExit("Module PyYAML absent : lancer ./scripts/generer-pld.sh")

CONFIG = Path.home() / ".config" / "projectos" / "pld.yml"
SORTIE = Path.home() / "projectos-pld" / "PLD"
MODELE_DOCX = Path.home() / "Downloads" / "PLD_Template.docx"
MODELE_XLSX = Path.home() / "Downloads" / "PLD_Suivi_Taches.xlsx"
PROJETS_GITHUB = [1, 2, 3, 4, 5]
PSEUDO = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")


class ErreurConfig(Exception):
    pass


@dataclass
class Config:
    espace: str
    projet_id: str
    plane_url: str | None
    org: str
    projets_github: list
    projet: str
    membres: dict
    ignores: list
    debut_par_defaut: dt.date | None
    remise_suivante: dt.date | None
    sortie: Path
    modele_docx: Path
    modele_xlsx: Path
    responsable: str | None = None
    email: str | None = None
    promotion: str | None = None
    revisions: list = field(default_factory=list)
    textes: dict = field(default_factory=dict)


@dataclass
class Periode:
    du: dt.date | None = None
    au: dt.date | None = None
    sprints: list = field(default_factory=list)
    origine: str = ""

    def __str__(self):
        if self.sprints:
            return "sprints " + ", ".join(f"« {s} »" for s in self.sprints)
        return f"{self.du.isoformat()} → {self.au.isoformat()}"


def date_iso(valeur, cle):
    """Accepte une date YAML ou une chaîne AAAA-MM-JJ."""
    if valeur is None or valeur == "":
        return None
    if isinstance(valeur, dt.date):
        return valeur
    try:
        return dt.date.fromisoformat(str(valeur))
    except ValueError:
        raise ErreurConfig(f"{cle} : date invalide « {valeur} » (attendu : AAAA-MM-JJ)")


def _section(donnees, nom):
    sec = donnees.get(nom) or {}
    if not isinstance(sec, dict):
        raise ErreurConfig(f"La section « {nom}: » doit être un dictionnaire")
    return sec


def _chemin(valeur, defaut):
    return Path(valeur).expanduser() if valeur else defaut


def lire_config(donnees):
    """Construit et contrôle la Config depuis le contenu YAML déjà chargé."""
    if not isinstance(donnees, dict):
        raise ErreurConfig("pld.yml est vide ou mal formé")
    plane, github, pld = (_section(donnees, n) for n in ("plane", "github", "pld"))

    espace, projet_id = plane.get("espace"), str(plane.get("projet_id") or "")
    if not espace:
        raise ErreurConfig("plane.espace manque (slug de l'espace de travail, ex. « flowly »)")
    if not UUID.fullmatch(projet_id):
        raise ErreurConfig("plane.projet_id manque ou n'est pas un ID de projet Plane")

    projets = github.get("projets", PROJETS_GITHUB)
    if not isinstance(projets, list) or not all(isinstance(p, int) and p > 0 for p in projets):
        raise ErreurConfig("github.projets : liste de numéros de projets GitHub (ex. [1, 2, 3])")

    membres = pld.get("membres") or {}
    if not isinstance(membres, dict):
        raise ErreurConfig("pld.membres : dictionnaire pseudo GitHub → nom affiché")
    for pseudo, nom in membres.items():
        if not PSEUDO.fullmatch(str(pseudo)):
            raise ErreurConfig(f"pld.membres : pseudo GitHub invalide « {pseudo} »")
        if not isinstance(nom, str) or not nom.strip():
            raise ErreurConfig(f"pld.membres : nom vide pour « {pseudo} »")
    ignores = pld.get("ignores") or []
    if not isinstance(ignores, list):
        raise ErreurConfig("pld.ignores : liste de pseudos GitHub")
    doublons = sorted(set(membres) & set(ignores))
    if doublons:
        raise ErreurConfig(f"Pseudo à la fois membre et ignoré : {', '.join(doublons)}")

    modeles = pld.get("modeles") or {}
    if not isinstance(modeles, dict):
        raise ErreurConfig("pld.modeles : dictionnaire avec docx et xlsx")
    textes = pld.get("textes") or {}
    if not isinstance(textes, dict):
        raise ErreurConfig("pld.textes : dictionnaire (resume, schema, plan_alpha_beta, bloquants, commentaire)")
    for cle, valeur in textes.items():
        if isinstance(valeur, dict):
            tableau = valeur.get("tableau") or []
            if not isinstance(tableau, list) or not all(isinstance(l, list) for l in tableau):
                raise ErreurConfig(f"pld.textes.{cle}.tableau : liste de lignes, la première est l'en-tête")
            if valeur.get("image") and not Path(str(valeur["image"])).expanduser().is_file():
                raise ErreurConfig(f"pld.textes.{cle}.image : fichier introuvable")
            if valeur.get("image"):
                valeur["image"] = str(Path(str(valeur["image"])).expanduser())
        elif not isinstance(valeur, str):
            raise ErreurConfig(f"pld.textes.{cle} : texte, ou {{texte, tableau, image, note}}")
    revisions = pld.get("revisions") or []
    if not isinstance(revisions, list) or not all(isinstance(r, dict) for r in revisions):
        raise ErreurConfig("pld.revisions : liste de {date, version, auteurs, sections, commentaires}")
    return Config(
        espace=str(espace),
        projet_id=projet_id,
        plane_url=plane.get("url"),
        org=str(github.get("org") or "Flowly-PBS"),
        projets_github=projets,
        projet=str(pld.get("projet") or "Flowly"),
        membres={str(k): v.strip() for k, v in membres.items()},
        ignores=[str(i) for i in ignores],
        debut_par_defaut=date_iso(pld.get("debut_par_defaut"), "pld.debut_par_defaut"),
        remise_suivante=date_iso(pld.get("remise_suivante"), "pld.remise_suivante"),
        sortie=_chemin(pld.get("sortie"), SORTIE),
        modele_docx=_chemin(modeles.get("docx"), MODELE_DOCX),
        modele_xlsx=_chemin(modeles.get("xlsx"), MODELE_XLSX),
        responsable=pld.get("responsable"),
        email=pld.get("email"),
        promotion=str(pld["promotion"]) if pld.get("promotion") else None,
        revisions=[{k: str(v) for k, v in r.items()} for r in revisions],
        textes=textes,
    )


def charger(chemin=CONFIG):
    chemin = Path(chemin).expanduser()
    if not chemin.is_file():
        raise ErreurConfig(f"Configuration introuvable : {chemin} (modèle : pld/pld.example.yml)")
    try:
        donnees = yaml.safe_load(chemin.read_text(encoding="utf-8"))
    except yaml.YAMLError as e:
        raise ErreurConfig(f"{chemin} : YAML invalide ({e})")
    return lire_config(donnees)


def choisir_periode(cfg, du=None, au=None, sprints=None):
    """Dates données > dates de pld.yml. Les sprints excluent les dates."""
    if sprints:
        if du or au:
            raise ErreurConfig("Choisir soit --sprints, soit --du/--au, pas les deux")
        noms = [s.strip() for s in sprints if s.strip()]
        if len(set(noms)) != len(noms):
            raise ErreurConfig("--sprints : un sprint est cité deux fois")
        return Periode(sprints=noms, origine="--sprints")
    debut = date_iso(du, "--du") or cfg.debut_par_defaut
    fin = date_iso(au, "--au") or cfg.remise_suivante
    if debut is None:
        raise ErreurConfig("Début de période inconnu : --du AAAA-MM-JJ, ou pld.debut_par_defaut")
    if fin is None:
        raise ErreurConfig("Fin de période inconnue : --au AAAA-MM-JJ, ou pld.remise_suivante")
    if debut > fin:
        raise ErreurConfig(f"Période à l'envers : {debut} après {fin}")
    origine = "ligne de commande" if (du and au) else ("pld.yml" if not (du or au) else "ligne de commande + pld.yml")
    return Periode(du=debut, au=fin, origine=origine)
