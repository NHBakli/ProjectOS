"""Lecture seule de GitHub pour le PLD, par GraphQL via `gh api graphql` (compte déjà connecté).

Lit :
  - les issues des projets GitHub de l'organisation, avec leurs champs
    (Status, Estimate, Size, Start date, Target date, Iteration) ;
  - les issues citées par Plane mais absentes des projets ;
  - les PR fusionnées pendant la période, avec les issues qu'elles ferment.

Aucune mutation GraphQL : seules des requêtes `query` sont envoyées (garde-fou dans `graphql`).
"""
import json
import re
import subprocess

CHAMPS_ITEM = """
fieldValues(first:30) { nodes {
  ... on ProjectV2ItemFieldSingleSelectValue { name field { ... on ProjectV2FieldCommon { name } } }
  ... on ProjectV2ItemFieldNumberValue { number field { ... on ProjectV2FieldCommon { name } } }
  ... on ProjectV2ItemFieldDateValue { date field { ... on ProjectV2FieldCommon { name } } }
  ... on ProjectV2ItemFieldIterationValue { title startDate duration field { ... on ProjectV2FieldCommon { name } } }
} }"""
ISSUE = """
number title url state stateReason createdAt closedAt body repository { name }
assignees(first:10) { nodes { login } } labels(first:20) { nodes { name } }
closedByPullRequestsReferences(first:10, includeClosedPrs:false) {
  nodes { number url title mergedAt author { login } repository { name } } }"""
Q_PROJET = """query($org:String!, $num:Int!, $apres:String) {
  organization(login:$org) { projectV2(number:$num) { title number
    items(first:100, after:$apres) { pageInfo { hasNextPage endCursor }
      nodes { type %s content { ... on Issue { %s } } } } } } }""" % (CHAMPS_ITEM, ISSUE)
Q_PR = """query($q:String!, $apres:String) {
  search(query:$q, type:ISSUE, first:100, after:$apres) { pageInfo { hasNextPage endCursor }
    nodes { ... on PullRequest { number title url mergedAt author { login } repository { name }
      closingIssuesReferences(first:10) { nodes { number repository { name } } } } } } }"""
REF = re.compile(r"([A-Za-z0-9_.-]+)#([0-9]+)")


class ErreurGithub(Exception):
    pass


def gh(arguments, entree=None):
    """Lance `gh` et renvoie sa sortie. Remplacé dans les tests."""
    try:
        r = subprocess.run(["gh", *arguments], input=entree, capture_output=True, text=True, timeout=120)
    except FileNotFoundError:
        raise ErreurGithub("Commande gh absente : installer GitHub CLI puis `gh auth login`")
    except subprocess.TimeoutExpired:
        raise ErreurGithub("GitHub ne répond pas (délai dépassé)")
    if r.returncode != 0 and r.stdout.lstrip().startswith("{"):
        return r.stdout  # réponse GraphQL avec « errors » : analysée par graphql()
    if r.returncode != 0:
        message = (r.stderr or r.stdout).strip().splitlines()[-1:] or ["erreur inconnue"]
        raise ErreurGithub(f"gh a échoué : {message[0]}")
    return r.stdout


class GithubLecture:
    def __init__(self, org, executer=None):
        self.org, self.executer, self.appels = org, executer or gh, 0

    def graphql(self, requete, tolerer_absent=False, **variables):
        if not requete.lstrip().startswith("query"):
            raise RuntimeError("Lecture seule : seules les requêtes « query » sont permises")  # garde-fou
        args = ["api", "graphql", "-f", f"query={requete}"]
        for nom, valeur in variables.items():
            if valeur is None:
                continue
            args += ["-F" if isinstance(valeur, int) else "-f", f"{nom}={valeur}"]
        self.appels += 1
        try:
            rep = json.loads(self.executer(args))
        except ValueError:
            raise ErreurGithub("Réponse GitHub illisible")
        erreurs = [e for e in rep.get("errors") or [] if not (tolerer_absent and e.get("type") == "NOT_FOUND")]
        if erreurs or not rep.get("data"):
            erreurs = erreurs or rep.get("errors") or [{"message": "réponse vide"}]
            raise ErreurGithub("GitHub : " + "; ".join(e.get("message", "?") for e in erreurs))
        return rep["data"]


def _champs(item):
    """Valeurs des champs du projet : {'Status': 'Done', 'Estimate': 2.0, 'Iteration': {...}, …}."""
    valeurs = {}
    for f in (item.get("fieldValues") or {}).get("nodes") or []:
        nom = ((f or {}).get("field") or {}).get("name")
        if not nom:
            continue
        if "name" in f:
            valeurs[nom] = f["name"]
        elif "number" in f:
            valeurs[nom] = f["number"]
        elif "date" in f:
            valeurs[nom] = f["date"]
        elif "title" in f:
            valeurs[nom] = {"titre": f["title"], "debut": f.get("startDate"), "jours": f.get("duration")}
    return valeurs


def _issue(contenu, projet=None, champs=None):
    return {
        "ref": f"{contenu['repository']['name']}#{contenu['number']}",
        "depot": contenu["repository"]["name"],
        "numero": contenu["number"],
        "titre": contenu.get("title"),
        "url": contenu.get("url"),
        "etat": contenu.get("state"),
        "raison": contenu.get("stateReason"),
        "creee_le": (contenu.get("createdAt") or "")[:10] or None,
        "fermee_le": (contenu.get("closedAt") or "")[:10] or None,
        "corps": contenu.get("body") or "",
        "assignes": [a["login"] for a in (contenu.get("assignees") or {}).get("nodes") or [] if a],
        "etiquettes": [l["name"] for l in (contenu.get("labels") or {}).get("nodes") or [] if l],
        "pr": [{"ref": f"{p['repository']['name']}#{p['number']}", "url": p.get("url"), "titre": p.get("title"),
                "fusionnee_le": (p.get("mergedAt") or "")[:10] or None,
                "auteur": (p.get("author") or {}).get("login")}
               for p in (contenu.get("closedByPullRequestsReferences") or {}).get("nodes") or [] if p],
        "projets": [projet] if projet else [],
        "champs": champs or {},
    }


def lire_projets(gl, numeros):
    """Issues des projets, fusionnées si une issue est dans plusieurs projets."""
    issues, brouillons, titres = {}, 0, {}
    for num in numeros:
        apres = None
        while True:
            data = gl.graphql(Q_PROJET, org=gl.org, num=num, apres=apres)
            projet = (data.get("organization") or {}).get("projectV2")
            if not projet:
                raise ErreurGithub(f"Projet GitHub n°{num} introuvable dans {gl.org}")
            titres[num] = projet.get("title")
            for item in projet["items"]["nodes"]:
                if item.get("type") == "DRAFT_ISSUE":
                    brouillons += 1
                contenu = item.get("content") or {}
                if item.get("type") != "ISSUE" or not contenu.get("number"):
                    continue
                nouvelle = _issue(contenu, projet.get("title"), _champs(item))
                deja = issues.get(nouvelle["ref"])
                if deja:
                    deja["projets"] += nouvelle["projets"]
                    for k, v in nouvelle["champs"].items():
                        deja["champs"].setdefault(k, v)
                else:
                    issues[nouvelle["ref"]] = nouvelle
            page = projet["items"]["pageInfo"]
            if not page["hasNextPage"]:
                break
            apres = page["endCursor"]
    return issues, brouillons, titres


def lire_issues(gl, refs):
    """Issues hors projets (citées par Plane). Renvoie (issues, refs introuvables)."""
    trouvees, absentes = {}, []
    refs = sorted(set(refs))
    for i in range(0, len(refs), 20):
        lot = refs[i:i + 20]
        morceaux = []
        for j, ref in enumerate(lot):
            depot, num = REF.fullmatch(ref).groups()
            morceaux.append(f'i{j}: repository(owner:"{gl.org}", name:"{depot}") {{ issue(number:{int(num)}) {{ {ISSUE} }} }}')
        data = gl.graphql("query {\n" + "\n".join(morceaux) + "\n}", tolerer_absent=True)
        for j, ref in enumerate(lot):
            issue = (data.get(f"i{j}") or {}).get("issue")
            if issue:
                trouvees[ref] = _issue(issue)
            else:
                absentes.append(ref)
    return trouvees, absentes


def lire_pr_fusionnees(gl, du, au):
    prs, apres = [], None
    requete = f"org:{gl.org} is:pr is:merged merged:{du.isoformat()}..{au.isoformat()}"
    while True:
        s = gl.graphql(Q_PR, q=requete, apres=apres)["search"]
        for n in s["nodes"]:
            if not n or not n.get("number"):
                continue
            prs.append({"ref": f"{n['repository']['name']}#{n['number']}", "url": n.get("url"), "titre": n.get("title"),
                        "fusionnee_le": (n.get("mergedAt") or "")[:10], "auteur": (n.get("author") or {}).get("login"),
                        "ferme": [f"{i['repository']['name']}#{i['number']}"
                                  for i in (n.get("closingIssuesReferences") or {}).get("nodes") or [] if i]})
        if not s["pageInfo"]["hasNextPage"]:
            return prs
        apres = s["pageInfo"]["endCursor"]


def extraire(gl, numeros, refs_plane, du, au):
    issues, brouillons, titres = lire_projets(gl, numeros)
    hors_projets, absentes = lire_issues(gl, [r for r in refs_plane if r not in issues])
    for ref, issue in hors_projets.items():
        issues[ref] = issue
    return {
        "projets": titres,
        "issues": issues,
        "brouillons": brouillons,
        "absentes": absentes,
        "pr_fusionnees": lire_pr_fusionnees(gl, du, au),
        "requetes": gl.appels,
    }
