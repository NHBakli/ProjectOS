"""Rapport de cohérence (rapport-coherence.md) : ce qu'il faut corriger avant la remise. Non remis à Epitech."""
import datetime as dt

from analyse import ATTENTION, ERREUR, INFO

TITRES = {ERREUR: "✗ À corriger", ATTENTION: "⚠ À vérifier", INFO: "ℹ Pour information"}


def _cellule(texte):
    return str(texte or "").replace("|", "\\|").replace("\n", " ")


def ecrire(chemin, analyse, numero, projet, sources, genere_le=None):
    genere_le = genere_le or dt.datetime.now()
    s = analyse.stats
    lignes = [
        f"# Rapport de cohérence — PLD n°{numero} {projet}",
        "",
        "> Document de travail, **à ne pas remettre**. Corriger dans GitHub (ou Plane), puis relancer le générateur.",
        "",
        f"- Généré le {genere_le:%d/%m/%Y à %H:%M}",
        f"- Période : {analyse.du:%d/%m/%Y} → {analyse.au:%d/%m/%Y}",
        f"- Sources : {sources}",
        "",
        "## Chiffres",
        "",
        "| | |",
        "|---|---|",
        f"| Cartes affichées dans le PLD | {s['cartes']} |",
        f"| Cartes de la période | {s['periode']} (terminées {s['terminees']}, en cours {s['en_cours']}, "
        f"à faire {s['a_faire']}, bloquées {s['bloquees']}) |",
        f"| Charge prévue / réalisée | {s['charge_prevue']:g} j / {s['charge_realisee']:g} j |",
        f"| Cartes sans estimation | {s['sans_estimation']} |",
        f"| PR fusionnées sur la période | {s['pr']} |",
        f"| Charge attendue par membre | ~{analyse.charge_attendue:g} j (2 j par mois) |",
        "",
    ]
    nombre = {n: sum(c.niveau == n for c in analyse.controles) for n in TITRES}
    lignes += [f"Bilan : **{nombre[ERREUR]}** à corriger, **{nombre[ATTENTION]}** à vérifier, {nombre[INFO]} pour information.", ""]
    par_cle = {c.cle: c for c in analyse.cartes}
    for niveau, titre in TITRES.items():
        liste = [c for c in analyse.controles if c.niveau == niveau]
        if not liste:
            continue
        lignes += [f"## {titre} ({len(liste)})", "", "| Critère | Carte | Problème |", "|---|---|---|"]
        for c in liste:
            carte = par_cle.get(c.carte)
            nom = f"{carte.id_pld} {c.carte} — {carte.titre}" if carte else (c.carte or "—")
            lignes.append(f"| {_cellule(c.critere)} | {_cellule(nom)} | {_cellule(c.message)} |")
        lignes.append("")
    lignes += ["## Cartes par membre (période)", "", "| Membre | Cartes | Terminées | Charge |", "|---|---|---|---|"]
    for m in analyse.membres:
        cartes = [c for c in analyse.cartes if c.responsable == m and c.dans_periode]
        lignes.append(f"| {_cellule(m)} | {len(cartes)} | {sum(c.etat == 'Terminé' for c in cartes)} | "
                      f"{sum(c.charge or 0 for c in cartes):g} j |")
    lignes.append("")
    chemin.write_text("\n".join(lignes), encoding="utf-8")
    return nombre
