"""PLD Word, construit sur le modèle officiel PLD_Template.docx.

On garde la page de titre, les styles, le sommaire et la mise en page du modèle. On remplace le
contenu d'exemple section par section, en dupliquant les éléments modèles (ligne de membre, paire
de cartes, fiche story, ligne du rapport). Les liens internes pointent vers des signets créés ici :
card_K_I (fiche), membre_K (section du membre). Word met le sommaire à jour à l'ouverture.
"""
import copy
import re

import docx
from docx.oxml.ns import qn
from docx.shared import Cm
from docx.text.paragraph import Paragraph

from analyse import EQUIPE, TERMINE

A_COMPLETER = "[À compléter]"


class ErreurDocx(Exception):
    pass


# ---------------------------------------------------------------- outils XML

def _textes(el):
    return el.findall(".//" + qn("w:t"))


def _ecrire(el, texte):
    """Met le texte dans le 1er w:t de l'élément (sa mise en forme est gardée), vide les autres.
    Les retours à la ligne deviennent des sauts de ligne Word."""
    ts = _textes(el)
    if not ts:
        raise ErreurDocx("Élément du modèle sans texte : structure inattendue")
    for t in ts[1:]:
        t.text = ""
    premier = ts[0]
    lignes = str(texte).split("\n")
    premier.text = lignes[0]
    premier.set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
    run = premier.getparent()
    for ligne in lignes[1:]:
        br = run.makeelement(qn("w:br"), {})
        t = run.makeelement(qn("w:t"), {"{http://www.w3.org/XML/1998/namespace}space": "preserve"})
        t.text = ligne
        run.append(br)
        run.append(t)


def _style(p_el):
    s = p_el.find(qn("w:pPr") + "/" + qn("w:pStyle"))
    return s.get(qn("w:val")) if s is not None else ""


def _texte(el):
    return "".join(t.text or "" for t in _textes(el)).strip()


def _saut_de_page(el):
    return any(b.get(qn("w:type")) == "page" for b in el.iter(qn("w:br")))


class _Signets:
    def __init__(self, depart=900000):
        self.n = depart

    def poser(self, p_el, nom):
        """Signet autour du contenu d'un paragraphe."""
        self.n += 1
        debut = p_el.makeelement(qn("w:bookmarkStart"), {qn("w:id"): str(self.n), qn("w:name"): nom})
        fin = p_el.makeelement(qn("w:bookmarkEnd"), {qn("w:id"): str(self.n)})
        ppr = p_el.find(qn("w:pPr"))
        p_el.insert(list(p_el).index(ppr) + 1 if ppr is not None else 0, debut)
        p_el.append(fin)


def _retirer_signets(el):
    for b in list(el.iter(qn("w:bookmarkStart"))) + list(el.iter(qn("w:bookmarkEnd"))):
        b.getparent().remove(b)


def _ancre(el, nom):
    for h in el.iter(qn("w:hyperlink")):
        h.set(qn("w:anchor"), nom)
    for instr in el.iter(qn("w:instrText")):
        if "HYPERLINK" in (instr.text or ""):
            instr.text = f' HYPERLINK \\l "{nom}" '


def _sans_lien(el):
    """Retire les liens (w:hyperlink) en gardant leur texte."""
    for h in list(el.iter(qn("w:hyperlink"))):
        parent = h.getparent()
        for r in list(h):
            h.addprevious(r)
        parent.remove(h)


def _corps(doc):
    return list(doc.element.body.iterchildren())


def _titre(doc, texte, style=None):
    for el in _corps(doc):
        if el.tag == qn("w:p") and _texte(el) == texte and (style is None or _style(el).lower() == style):
            return el
    raise ErreurDocx(f"Titre « {texte} » absent du modèle Word")


def _suivant(el, tag):
    while el is not None:
        el = el.getnext()
        if el is not None and el.tag == qn(tag):
            return el
    raise ErreurDocx("Élément attendu absent du modèle Word")


def _lignes(tbl):
    return tbl.findall(qn("w:tr"))


def _cellules(tr):
    return tr.findall(qn("w:tc"))


# ---------------------------------------------------------------- sections

def _page_de_titre(doc, projet, titre_periode, date, membres):
    remplacements = {"[NOM DU PROJET]": projet, "[Titre du sprint]": titre_periode, "[JJ/MM/AAAA]": date,
                     "[Membre 1] – [Membre 2] – [Membre 3] – [Membre 4]": " – ".join(membres)}
    for el in _corps(doc)[:12]:
        if el.tag == qn("w:p") and _texte(el) in remplacements:
            _ecrire(el, remplacements.pop(_texte(el)))


def _descriptif(doc, valeurs):
    tbl = _suivant(_titre(doc, "Descriptif du document"), "w:tbl")
    for tr in _lignes(tbl):
        cells = _cellules(tr)
        if len(cells) == 2 and _texte(cells[0]) in valeurs:
            _ecrire(cells[1], valeurs[_texte(cells[0])])


def _revisions(doc, revisions):
    tbl = _suivant(_titre(doc, "Tableau des révisions"), "w:tbl")
    lignes = _lignes(tbl)
    modele = lignes[1]
    for tr in lignes[1:]:
        tbl.remove(tr)
    for r in revisions:
        tr = copy.deepcopy(modele)
        for tc, cle in zip(_cellules(tr), ("date", "version", "auteurs", "sections", "commentaires")):
            _ecrire(tc, r.get(cle, "") or " ")
        tbl.append(tr)


def _tableau_libre(doc, apres, entete, lignes):
    """Tableau simple (style « Table Grid » du modèle) inséré après un paragraphe."""
    t = doc.add_table(rows=1 + len(lignes), cols=len(entete))
    try:
        t.style = doc.styles["Table Grid"]
    except KeyError:
        pass
    for j, h in enumerate(entete):
        cell = t.cell(0, j)
        cell.text = str(h)
        for run in cell.paragraphs[0].runs:
            run.bold = True
    for i, ligne in enumerate(lignes, 1):
        for j, v in enumerate(ligne[:len(entete)]):
            t.cell(i, j).text = str(v)
    apres.addnext(t._tbl)
    return t._tbl


def _texte_libre(doc, paragraphe, contenu, defaut):
    """Contenu de pld.yml : texte, ou {texte, tableau: [[entête…], [ligne…]], image}."""
    if isinstance(contenu, str) or contenu is None:
        _ecrire(paragraphe, (contenu or "").strip() or defaut)
        return
    _ecrire(paragraphe, (contenu.get("texte") or "").strip() or " ")
    dernier = paragraphe
    if contenu.get("image"):
        p = Paragraph(paragraphe, doc).insert_paragraph_before("")  # image avant le texte
        p.add_run().add_picture(str(contenu["image"]), width=Cm(16))
    tableau = contenu.get("tableau") or []
    if len(tableau) >= 2:
        dernier = _tableau_libre(doc, dernier, tableau[0], tableau[1:])
    if contenu.get("note"):
        note = copy.deepcopy(paragraphe)
        _ecrire(note, contenu["note"].strip())
        dernier.addnext(note)


def _section_texte(doc, titre, contenu, defaut):
    p = _suivant(_titre(doc, titre), "w:p")
    while not _texte(p):
        p = _suivant(p, "w:p")
    _texte_libre(doc, p, contenu, defaut)


def _tableau_des_cartes(doc, analyse, numeros):
    tbl = _suivant(_titre(doc, "Tableau des cartes"), "w:tbl")
    lignes = _lignes(tbl)
    modele_membre, modele_paire = lignes[0], lignes[1]
    for tr in lignes:
        tbl.remove(tr)
    for m in analyse.membres:
        cartes = [c for c in analyse.cartes if c.responsable == m]
        if not cartes:
            continue
        tr = copy.deepcopy(modele_membre)
        _ecrire(tr, m)
        _ancre(tr, f"membre_{numeros[m]}")
        tbl.append(tr)
        for i in range(0, len(cartes), 2):
            tr = copy.deepcopy(modele_paire)
            for tc, c in zip(_cellules(tr), cartes[i:i + 2] + [None]):
                if c is None:
                    for t in _textes(tc):
                        t.text = ""
                    continue
                ts = _textes(tc)
                ts[0].text = f"{c.id_pld} – "
                ts[0].set("{http://www.w3.org/XML/1998/namespace}space", "preserve")
                lien = tc.find(".//" + qn("w:hyperlink"))
                _ecrire(lien, c.titre)
                _ancre(lien, "card_" + c.id_pld.replace(".", "_"))
            tbl.append(tr)


def _valeur(v):
    return v.strip() if v and v.strip() else A_COMPLETER


def _fiches(doc, analyse, numeros, signets):
    debut = _titre(doc, "Cartes de nos stories")
    fin = _titre(doc, "Plan Alpha / Beta")
    zone, el = [], debut.getnext()
    while el is not None and el is not fin:
        zone.append(el)
        el = el.getnext()
    while zone and (not _texte(zone[-1]) and zone[-1].tag == qn("w:p")):  # sauts de page avant « Plan »
        if _saut_de_page(zone[-1]):
            zone.pop()
            while zone and zone[-1].tag == qn("w:p") and not _texte(zone[-1]) and not _saut_de_page(zone[-1]):
                zone.pop()
            break
        zone.pop()
    m_titre = next(e for e in zone if e.tag == qn("w:p") and _style(e).lower().replace(" ", "") == "heading20")
    m_retour = next(e for e in zone if e.tag == qn("w:p") and "Retour" in _texte(e))
    m_fiche = next(e for e in zone if e.tag == qn("w:tbl"))
    m_vide = next(e for e in zone if e.tag == qn("w:p") and not _texte(e) and not _saut_de_page(e))
    for e in zone:
        e.getparent().remove(e)

    ancre = debut
    def ajouter(e):
        nonlocal ancre
        ancre.addnext(e)
        ancre = e

    for m in analyse.membres:
        cartes = [c for c in analyse.cartes if c.responsable == m]
        if not cartes:
            continue
        titre = copy.deepcopy(m_titre)
        _retirer_signets(titre)
        _ecrire(titre, m)
        signets.poser(titre, f"membre_{numeros[m]}")
        ajouter(titre)
        ajouter(copy.deepcopy(m_retour))
        for c in cartes:
            ajouter(copy.deepcopy(m_vide))
            fiche = copy.deepcopy(m_fiche)
            lignes = _lignes(fiche)
            entete = f"{c.id_pld} {c.titre}"
            _ecrire(lignes[0], entete)
            signets.poser(lignes[0].find(".//" + qn("w:p")), "card_" + c.id_pld.replace(".", "_"))
            f = c.fiche
            je_veux = _valeur(f.get("je_veux"))
            if f.get("afin_de"):
                je_veux += f"\nAfin de : {f['afin_de'].strip()}"
            description = f.get("description") or ""
            refs = " · ".join([c.cle] + [r for r in c.issues if r != c.cle])
            description = (description.strip() + "\n" if description.strip() else "") + f"Référence : {refs}"
            if c.sprint:
                description += f" · {c.sprint}"
            charge = f"{c.charge:g} jour(s)".replace(".", ",") if c.charge is not None else A_COMPLETER
            etat = f"{c.avancement} % — {c.etat}"
            if c.etat == TERMINE and c.termine_le:
                etat += f" le {c.termine_le:%d/%m/%Y}"
            responsable = c.responsable + (f" (avec {', '.join(c.autres)})" if c.autres else "")
            valeurs = [_valeur(f.get("en_tant_que")), je_veux, description, _valeur(f.get("dod")), charge, etat, responsable]
            for tr, v in zip(lignes[1:], valeurs):
                _ecrire(_cellules(tr)[-1], v)
            ajouter(fiche)
            ajouter(copy.deepcopy(m_retour))


def _rapport(doc, analyse, numeros, bloquants, commentaire):
    tbl = _suivant(_titre(doc, "Rapport d'avancement"), "w:tbl")
    lignes = _lignes(tbl)
    modele = lignes[2]
    bas = lignes[-2:]
    for tr in lignes[2:-2]:
        tbl.remove(tr)
    for m in analyse.membres:
        cartes = [c for c in analyse.cartes if c.responsable == m and c.dans_periode and c.etat in (TERMINE, "En cours", "Bloqué")]
        tr = copy.deepcopy(modele)
        gauche, droite = _cellules(tr)
        _ecrire(gauche, m)
        if m in numeros:
            _ancre(gauche, f"membre_{numeros[m]}")
        else:  # membre sans carte : pas de section où renvoyer
            _sans_lien(gauche)
        paragraphes = droite.findall(qn("w:p"))
        modele_p = paragraphes[0]
        for p in paragraphes:
            droite.remove(p)
        if not cartes:
            p = copy.deepcopy(modele_p)
            _sans_lien(p)
            _ecrire(p, "Aucune tâche terminée ou en cours sur la période")
            droite.append(p)
        for c in cartes:
            p = copy.deepcopy(modele_p)
            fin = f", le {c.termine_le:%d/%m/%Y}" if c.etat == TERMINE and c.termine_le else ""
            _ecrire(p, f"{c.id_pld} – {c.titre} ({c.etat}{fin})")
            _ancre(p, "card_" + c.id_pld.replace(".", "_"))
            droite.append(p)
        bas[0].addprevious(tr)
    for tr, texte in zip(bas, (bloquants, commentaire)):
        paragraphes = tr.findall(".//" + qn("w:p"))
        if len(paragraphes) >= 2:
            _ecrire(paragraphes[-1], texte)
        else:
            _ecrire(tr, texte)


def _sommaire(doc, signets):
    """Entrées du sommaire en cache : titres de niveau 1 (sections) et 2 (membres), sans numéro de page.
    Word les recalcule (avec les pages) à l'ouverture : w:updateFields."""
    sdt = next((e for e in _corps(doc) if e.tag == qn("w:sdt") and "TOC" in "".join(e.itertext())), None)
    if sdt is None:
        return
    contenu = sdt.find(qn("w:sdtContent"))
    ps = contenu.findall(qn("w:p"))
    entrees = [p for p in ps if p.find(qn("w:hyperlink")) is not None]
    if not entrees:
        return
    premier, niv1 = entrees[0], entrees[1] if len(entrees) > 1 else entrees[0]
    niv2 = next((p for p in entrees if _style(p).upper() == "TOC2"), niv1)
    titres = []
    for el in _corps(doc):
        if el.tag != qn("w:p") or not _texte(el):
            continue
        style = _style(el).lower().replace(" ", "")
        if style in ("heading10", "heading20"):
            nom = next((b.get(qn("w:name")) for b in el.iter(qn("w:bookmarkStart"))
                        if (b.get(qn("w:name")) or "").startswith("_Toc")), None)
            if not nom:
                nom = f"_Toc_pld_{len(titres) + 1}"
                signets.poser(el, nom)
            titres.append((1 if style == "heading10" else 2, _texte(el), nom))
    for p in entrees:
        contenu.remove(p)
    fin = ps[-1] if ps[-1] not in entrees else None
    for i, (niveau, texte, nom) in enumerate(titres):
        p = copy.deepcopy(premier if i == 0 else (niv1 if niveau == 1 else niv2))
        if i == 0 and niveau == 2:
            p.find(qn("w:pPr") + "/" + qn("w:pStyle")).set(qn("w:val"), "TOC2")
        h = p.find(qn("w:hyperlink"))
        h.set(qn("w:anchor"), nom)
        ts = _textes(h)
        ts[0].text = texte
        for t in ts[1:]:
            t.text = ""
        for instr in h.iter(qn("w:instrText")):
            if "PAGEREF" in (instr.text or ""):
                instr.text = f" PAGEREF {nom} \\h "
        if fin is not None:
            fin.addprevious(p)
        else:
            contenu.append(p)
    reglages = doc.settings.element
    if reglages.find(qn("w:updateFields")) is None:
        reglages.append(reglages.makeelement(qn("w:updateFields"), {qn("w:val"): "true"}))


def ecrire(chemin, modele, analyse, contexte):
    """contexte : projet, titre_periode, date, auteurs, responsable, email, promotion, version,
    revisions, resume, schema, plan_alpha_beta, bloquants, commentaire."""
    if not modele.is_file():
        raise ErreurDocx(f"Modèle Word introuvable : {modele}")
    doc = docx.Document(str(modele))
    signets = _Signets()
    avec_cartes = [m for m in analyse.membres if any(c.responsable == m for c in analyse.cartes)]
    numeros = {m: k for k, m in enumerate(avec_cartes, 1)}
    k = contexte
    _page_de_titre(doc, k["projet"], k["titre_periode"], k["date"], k["auteurs"])
    _descriptif(doc, {
        "Auteurs": ", ".join(k["auteurs"]), "Responsable": k.get("responsable") or A_COMPLETER,
        "E-mail": k.get("email") or A_COMPLETER, "Promotion": k.get("promotion") or A_COMPLETER,
        "Date de mise à jour": k.get("mise_a_jour") or k["date"], "Objet": f"Répartition des tâches et avancement du {analyse.du:%d/%m/%Y} "
        f"au {analyse.au:%d/%m/%Y}"})
    _revisions(doc, k["revisions"])
    _section_texte(doc, "Résumé", k.get("resume"), A_COMPLETER)
    _section_texte(doc, "Schéma fonctionnel", k.get("schema"), A_COMPLETER)
    _tableau_des_cartes(doc, analyse, numeros)
    _fiches(doc, analyse, numeros, signets)
    _section_texte(doc, "Plan Alpha / Beta", k.get("plan_alpha_beta"), A_COMPLETER)
    _rapport(doc, analyse, numeros, k["bloquants"], k["commentaire"])
    _sommaire(doc, signets)
    restes = sorted({m.group(0) for m in re.finditer(r"\[(?:NOM DU PROJET|Titre du sprint|JJ/MM/AAAA|Membre \d|Rôle|Objectif)\]",
                                                     "\n".join(t.text or "" for t in _textes(doc.element.body)))})
    doc.save(str(chemin))
    return restes
