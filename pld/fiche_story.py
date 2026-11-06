"""Rubriques de fiche story dans un texte (description Plane ou corps d'issue GitHub).

Formats reconnus :
  - modèle Plane :          « En tant que : utilisateur de Flowly » (valeur sur la même ligne) ;
  - modèle d'issue GitHub : « ### En tant que » puis la valeur sur les lignes suivantes ;
  - libellés anglais (issues traduites par n8n via DeepL) : « As a », « I want », « So that »…

Ce qui suit « <details><summary>Original (FR)</summary> » (copie ajoutée par n8n) est ignoré,
comme les commentaires HTML et « _No response_ » (champ vide d'un modèle d'issue).
"""
import re
import unicodedata

RUBRIQUES = {
    "en_tant_que": ["en tant que", "as a", "as an"],
    "je_veux": ["je veux", "i want", "i want to"],
    "afin_de": ["afin de", "afin que", "so that", "in order to"],
    "description": ["description"],
    "dod": ["definition of done", "dod", "definition de fini"],
    "bloquants": ["points bloquants", "point bloquant", "blockers", "blocking points"],
}
OBLIGATOIRES = ("en_tant_que", "je_veux", "afin_de", "dod")
FIN_ORIGINAL = re.compile(r"^\s*<details>\s*<summary>\s*Original \(FR\)", re.I)
VIDE = {"", "_no response_", "…", "...", "à compléter", "a completer"}
PUCE = re.compile(r"^\s*(?:[-*+]|\d+[.)])?\s*(?:\[[ xX]?\])?\s*")


def _sans_accents(texte):
    return "".join(c for c in unicodedata.normalize("NFD", texte) if unicodedata.category(c) != "Mn")


_LIBELLES = sorted(((lib, cle) for cle, libs in RUBRIQUES.items() for lib in libs), key=lambda x: -len(x[0]))
_TITRE = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*(?P<lib>[a-z' ]+?)\s*(?:\*\*|__)?\s*(?:(?P<sep>:)\s*(?P<reste>.*?))?\s*(?:\*\*|__)?\s*$"
)


def _titre(ligne):
    """Renvoie (clé, reste de la ligne) si la ligne ouvre une rubrique, sinon None."""
    brut = _sans_accents(ligne).lower()
    m = _TITRE.match(brut)
    if not m:
        return None
    lib = m.group("lib").strip()
    for libelle, cle in _LIBELLES:
        if lib == libelle:
            est_titre_md = ligne.lstrip().startswith("#") or ligne.strip().startswith(("**", "__"))
            if m.group("sep") or est_titre_md:
                # le reste garde la casse et les accents d'origine
                reste = ligne.split(":", 1)[1].strip().strip("*_ ").strip() if m.group("sep") else ""
                return cle, reste
    return None


def extraire(texte):
    """Dictionnaire rubrique → texte (chaîne vide si la rubrique existe mais n'est pas remplie)."""
    rubriques, courante = {}, None
    for ligne in (texte or "").splitlines():
        if FIN_ORIGINAL.match(ligne):
            break
        if ligne.strip().startswith("<!--"):
            continue
        titre = _titre(ligne)
        if titre:
            cle, reste = titre
            if rubriques.get(cle):  # rubrique déjà remplie : on garde la première
                courante = None
                continue
            courante = cle
            rubriques[cle] = [reste] if reste else []
        elif courante:
            rubriques[courante].append(ligne.rstrip())
    resultat = {}
    for cle, lignes in rubriques.items():
        valeur = "\n".join(lignes).strip()
        resultat[cle] = "" if _vide(valeur) else valeur
    return resultat


def _vide(valeur):
    """Vrai si la rubrique ne contient que des modèles non remplis (« … », « - [ ] », « _No response_ »)."""
    return all(PUCE.sub("", ligne).strip().lower() in VIDE for ligne in valeur.splitlines() or [""])


def manquantes(rubriques):
    """Rubriques obligatoires absentes ou vides, dans l'ordre de la fiche."""
    return [cle for cle in OBLIGATOIRES if not rubriques.get(cle)]
