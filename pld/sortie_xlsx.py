"""Classeur de suivi des tâches, construit sur le modèle officiel PLD_Suivi_Taches.xlsx.

On garde les styles, listes de choix, formats et formules du modèle ; on remplace les lignes d'exemple.
"""
import copy
import datetime as dt
import warnings

from analyse import EQUIPE, TERMINE

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    import openpyxl
    from openpyxl.formatting.formatting import ConditionalFormattingList

FEUILLE_TACHES, FEUILLE_REVISIONS, FEUILLE_BORD = "Avancement des tâches", "Révisions", "Tableau de bord"
COLONNES = 10  # A → J


class ErreurXlsx(Exception):
    pass


def jours(charge):
    return f"{charge:g}j".replace(".", ",") if charge is not None else ""


def _styles(ws, ligne):
    return [copy.copy(ws.cell(ligne, col)._style) for col in range(1, COLONNES + 1)], ws.row_dimensions[ligne].height


def _appliquer(ws, ligne, styles):
    cellules, hauteur = styles
    for col, style in enumerate(cellules, 1):
        ws.cell(ligne, col)._style = copy.copy(style)
    ws.row_dimensions[ligne].height = hauteur


def _vider(ws, depuis):
    for plage in [p for p in ws.merged_cells.ranges if p.min_row >= depuis]:
        ws.unmerge_cells(str(plage))
    if ws.max_row >= depuis:
        ws.delete_rows(depuis, ws.max_row - depuis + 1)


def commentaire(c):
    morceaux = [c.cle] + [r for r in c.issues if r != c.cle]
    if c.preuves:
        morceaux.append("PR " + ", ".join(p["ref"] for p in c.preuves))
    if c.sprint:
        morceaux.append(c.sprint)
    if c.autres:
        morceaux.append("avec " + ", ".join(c.autres))
    return " · ".join(morceaux)


def _feuille_taches(ws, analyse, projet, titre_periode, version):
    ws["A1"] = f"{projet} – Suivi des tâches"
    ws["A2"] = f"Sprint : {titre_periode}    |    Période : {analyse.du:%d/%m/%Y} → {analyse.au:%d/%m/%Y}    |    Version : {version}"
    style_membre, style_tache, style_tache2 = _styles(ws, 4), _styles(ws, 5), _styles(ws, 6)
    regles = ws.conditional_formatting
    _vider(ws, 4)
    ligne = 4
    for m in analyse.membres:
        cartes = [c for c in analyse.cartes if c.responsable == m]
        _appliquer(ws, ligne, style_membre)
        ws.cell(ligne, 1, f"► {m}")
        ws.merge_cells(start_row=ligne, start_column=1, end_row=ligne, end_column=COLONNES)
        ligne += 1
        if not cartes:
            _appliquer(ws, ligne, style_tache)
            ws.cell(ligne, 3, "Aucune carte sur la période")  # colonne Membre vide : pas comptée par le tableau de bord
            ligne += 1
            continue
        for n, c in enumerate(cartes):
            _appliquer(ws, ligne, style_tache if n % 2 == 0 else style_tache2)
            fin = c.termine_le if c.etat == TERMINE else (c.fin or c.sprint_fin)
            valeurs = [c.id_pld, m, c.titre, jours(c.charge), c.etat, c.avancement,
                       c.debut or c.sprint_debut, fin, c.bloquants, commentaire(c)]
            for col, v in enumerate(valeurs, 1):
                cellule = ws.cell(ligne, col, v)
                if isinstance(v, dt.date):
                    cellule.number_format = "DD/MM/YYYY"
            if c.lien:
                ws.cell(ligne, 10).hyperlink = c.lien
            ligne += 1
    derniere = max(ligne - 1, 4)
    nouvelles = ConditionalFormattingList()
    for plage, liste in regles._cf_rules.items():
        colonne = str(plage.sqref).split(":")[0].rstrip("0123456789")
        for regle in liste:
            nouvelles.add(f"{colonne}4:{colonne}{derniere}", regle)
    ws.conditional_formatting = nouvelles
    return derniere


def _feuille_revisions(ws, revisions):
    style = [copy.copy(ws.cell(3, col)._style) for col in range(1, 6)]
    _vider(ws, 3)
    for i, r in enumerate(revisions):
        for col, cle in enumerate(("date", "version", "auteurs", "sections", "commentaires"), 1):
            ws.cell(3 + i, col, r.get(cle, ""))._style = copy.copy(style[col - 1])


def _feuille_bord(ws, analyse):
    t = f"'{FEUILLE_TACHES}'!"
    style_ligne = [copy.copy(ws.cell(3, col)._style) for col in range(1, 8)]
    style_total = [copy.copy(ws.cell(10, col)._style) for col in range(1, 8)]
    _vider(ws, 3)
    membres = analyse.membres
    for i, m in enumerate(membres):
        r = 3 + i
        valeurs = [m, f"=COUNTIF({t}$B$4:$B$500,A{r})"] + [
            f'=COUNTIFS({t}$B$4:$B$500,A{r},{t}$E$4:$E$500,"{etat}")' for etat in ("Terminé", "En cours", "À faire", "Bloqué")
        ] + [f"=IFERROR(AVERAGEIFS({t}$F$4:$F$500,{t}$B$4:$B$500,A{r}),0)"]
        for col, v in enumerate(valeurs, 1):
            ws.cell(r, col, v)._style = copy.copy(style_ligne[col - 1])
    total, fin = 3 + len(membres), 2 + len(membres)
    valeurs = ["TOTAL"] + [f"=SUM({c}3:{c}{fin})" for c in "BCDEF"] + [f"=IFERROR(AVERAGE(G3:G{fin}),0)"]
    for col, v in enumerate(valeurs, 1):
        ws.cell(total, col, v)._style = copy.copy(style_total[col - 1])


def ecrire(chemin, modele, analyse, projet, titre_periode, version, revisions):
    if not modele.is_file():
        raise ErreurXlsx(f"Modèle Excel introuvable : {modele}")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # extensions du modèle non gérées par openpyxl (barres de données)
        wb = openpyxl.load_workbook(modele)
    for nom in (FEUILLE_TACHES, FEUILLE_REVISIONS, FEUILLE_BORD):
        if nom not in wb.sheetnames:
            raise ErreurXlsx(f"Feuille « {nom} » absente du modèle Excel")
    lignes = _feuille_taches(wb[FEUILLE_TACHES], analyse, projet, titre_periode, version)
    _feuille_revisions(wb[FEUILLE_REVISIONS], revisions)
    _feuille_bord(wb[FEUILLE_BORD], analyse)
    wb.save(chemin)
    return lignes
