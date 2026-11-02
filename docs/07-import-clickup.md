# Reprendre l'historique ClickUp dans Plane

Les anciennes sprints et tâches de ClickUp passent dans Plane, une seule fois.
Plane Community n'a pas de page « Importations » : on passe par l'API.

| Étape | État |
|---|---|
| 1. Extraire ClickUp (lecture seule) | ✅ Faite le 2026-11-02 |
| 2. Faire correspondre (cycles, statuts, issues GitHub) | ✅ Choix faits, table validée |
| 3. Importer dans Plane | Essai dans un projet jetable validé (2026-11-03), import réel à faire |

## 1. Extraire ClickUp

Le script ne fait que lire. Il n'envoie rien à ClickUp ni ailleurs.

### Créer un token ClickUp

Accès direct, une fois connecté : `https://app.clickup.com/settings/apps`.

Ou bien :

1. Dans ClickUp, clique sur ton avatar (en haut à droite) → **Settings**.
2. Menu de gauche : **Apps**.
3. Bloc **API Token** : **Generate** (ou **Regenerate** s'il existe déjà), puis **Copy**.

Le token commence par `pk_`. Il n'expire pas : pense à le régénérer après l'import (voir plus bas).
Source : documentation ClickUp, `developer.clickup.com/docs/authentication`.

Ne colle ce token nulle part ailleurs que dans la commande ci-dessous.

### Lancer l'extraction

```bash
cd ~/Desktop/Dev/ProjectOS
read -rsp 'Token ClickUp : ' CLICKUP_TOKEN && export CLICKUP_TOKEN && echo
python3 pld/clickup_extraire.py
unset CLICKUP_TOKEN
```

Attendu :

```text
Lecture de « … »…
Espace de travail : …

Listes (espace / dossier / liste : début → fin, tâches, fermées) :
  … / Sprints / Sprint 1 : 2026-… → 2026-…, 23 tâches, 20 fermées
…
Fichier : /home/…/projectos-pld/clickup/clickup-2026….json  (… requêtes, lecture seule)
```

Le fichier JSON reste sur ton poste (droits `600`, hors Git). Il contient les noms et e-mails de l'équipe : ne le pousse pas.
Le résumé affiché ne contient pas d'e-mail : tu peux le coller pour préparer l'étape 2.

### En cas de problème

| Message | Cause | Solution |
|---|---|---|
| `Choisis l'espace de travail avec --equipe` | Tu as plusieurs espaces ClickUp | Relancer avec l'option affichée, par ex. `--equipe 9012345` |
| `Accès refusé (401)` | Token mal copié ou régénéré | Recopier le token, relancer |
| `Limite ClickUp atteinte, pause…` | 100 requêtes/minute en offre gratuite | Rien : le script attend et reprend |
| `ClickUp injoignable` | Pas de réseau | Vérifier la connexion |

### Après l'import

Le token donne un accès complet à ton compte. Une fois l'import fini : **Settings** → **Apps** → **Regenerate**, pour invalider l'ancien.

## 2. Ce que contient ClickUp (extraction du 2026-11-02)

Une seule liste. Les sprints sont des **tâches parentes**, les vraies tâches sont leurs sous-tâches.

| Tâche parente ClickUp | Dates | Sous-tâches |
|---|---|---|
| Phase N°2 | 2026-02-02 → 2026-03-30 | 10, terminées |
| Phase N°3 | 2026-03-30 → 2026-04-20 | 4, terminées |
| Sprint N°1 | 2026-09-15 → 2026-10-02 | 11, terminées |
| Sprint N°2 | 2026-10-02 → 2026-10-23 | 13, dont 12 à faire |

Ni points, ni estimation de temps, ni champ personnalisé. Statuts : `to do`, `complete`.

## 3. Correspondances (choix du 2026-11-02)

| ClickUp | Plane |
|---|---|
| Tâche parente (phase, sprint) | Un **ticket parent** avec ses sous-tickets, comme dans ClickUp, **et** un **cycle** aux mêmes dates (pour le PLD). Le ticket parent n'est pas dans le cycle. |
| Sprint N°2 | Cycle **terminé** le 2026-10-23 (resté ouvert dans ClickUp, fin confirmée). Ses tâches restent « à faire », comme leurs issues GitHub. |
| Sous-tâche | Un sous-ticket du ticket parent, dans le cycle. Sans date dans ClickUp : il prend les dates du sprint. |
| `complete` / `to do` | État du groupe « terminé » / « à faire » |
| Assignés | **Non repris.** Les prochaines tâches naissent dans GitHub : le PLD lira qui a fait quoi dans GitHub. |
| Tâche déjà en issue GitHub | Lien vers l'issue ajouté au ticket. **Aucune issue recréée.** |

### Pas de doublon dans GitHub

1. Les tickets importés n'ont **pas d'étiquette d'équipe** : le workflow n8n ne se déclenche pas.
2. Ils portent le lien de leur issue GitHub, au même format que n8n. Si quelqu'un ajoute une étiquette plus tard, n8n voit le lien et ne crée rien.

La table tâche ClickUp → issue GitHub est dans `~/.config/projectos/pld.yml` (hors Git), validée à la main.

## 4. Importer dans Plane

Script : `pld/clickup_importer.py`. Il crée 4 tickets parents, 38 sous-tickets, 4 cycles et les liens vers les issues GitHub existantes.
Il ne crée **aucune** issue GitHub, n'assigne personne, ne modifie ni ne supprime rien dans Plane.

| Mode | Commande | Effet |
|---|---|---|
| Plan | `--plan` | Hors ligne. Affiche ce qui sera importé. |
| Essai à blanc | (aucune option) | Lit Plane (GET seulement) et dit ce qui serait créé |
| Import | `--appliquer` | Refait l'essai, demande `oui`, puis crée |

### 1. Préparer

1. Dans `~/.config/projectos/pld.yml`, `fin_cycle_en_cours` confirme la fin du Sprint N°2, resté ouvert dans ClickUp (fait : `"2026-10-23"`).
2. Sauvegarde Plane ([sauvegardes.md](sauvegardes.md)) : obligatoire.
3. Vérifie le plan :

```bash
cd ~/Desktop/Dev/ProjectOS
python3 pld/clickup_importer.py --plan
```

**Attendu :** `Total : 4 cycles, 4 tickets parents, 38 sous-tickets, 33 liens GitHub.` et aucune ligne `✗`.

### 2. Créer une clé API Plane

1. Ouvre `https://plane.TON-DOMAINE/settings/profile/api-tokens/` (**Jetons d'accès personnel**).
2. **Ajouter un jeton d'accès** → nom `Import ClickUp`, expiration courte → **Générer un jeton** → copie-le.

Ne la colle que dans la commande ci-dessous. Supprime-la après l'import.

### 3. Essai à blanc

```bash
read -rsp 'Clé API Plane : ' PLANE_API_KEY && export PLANE_API_KEY && echo
python3 pld/clickup_importer.py
```

**Attendu :** `Projet Plane : « … » (…)`, la liste `Ticket parent à créer`, `Ticket à créer`, `Lien à créer`, `Cycle à créer`, puis `… action(s) à faire … (… requêtes, lecture seule)`.

### 4. Essai dans un projet jetable

1. Plane → **Créer un projet** → nom `Essai import`.
2. Note son ID dans l'adresse (après `/projects/`).
3. Active les cycles : `https://plane.TON-DOMAINE/flowly/settings/projects/ID-DU-PROJET/features` → **Cycles**.
4. Lance l'import dans ce projet (remplace `ID-DU-PROJET`) :

```bash
python3 pld/clickup_importer.py --appliquer --projet ID-DU-PROJET
```

5. Tape `oui`. Compte 2 à 3 minutes (Plane limite à 60 requêtes par minute ; le script attend tout seul).
6. Relance la même commande. **Attendu :** `Rien à faire : tout est déjà dans Plane.`
7. Regarde le projet dans Plane : tickets parents et sous-tickets, cycles, liens GitHub. Pour voir le temps : **Disposition en calendrier** ou **Disposition en chronologie** (le **Tableau** kanban n'affiche pas de dates).
8. Supprime le projet : réglages du projet → **Supprimer le projet**.

### 5. Import réel

```bash
python3 pld/clickup_importer.py --appliquer
unset PLANE_API_KEY
```

**Attendu :** `Terminé : 42 ticket(s), 33 lien(s), 4 cycle(s) créés, 0 ticket(s) complétés.` Aucune nouvelle issue dans GitHub.

### En cas de problème

| Message | Cause | Solution |
|---|---|---|
| `encore ouvert dans ClickUp : confirme sa date de fin` | Sprint resté ouvert dans ClickUp | Mettre sa vraie fin dans `fin_cycle_en_cours` (`pld.yml`) |
| `Accès refusé par Plane (401)` | Clé mal copiée ou supprimée | Recréer la clé, relancer |
| `Introuvable (404)` | Espace ou ID de projet faux | Vérifier `plane:` dans `pld.yml` ou `--projet` |
| `Les cycles sont désactivés` | Fonction Cycles coupée dans le projet | L'activer (étape 4.3) |
| `Cycle « … » déjà terminé dans Plane` | Un import précédent s'est arrêté après les vraies dates | Supprimer ce cycle dans Plane, relancer |
| Arrêt au milieu | Réseau, Plane | Relancer : rien n'est recréé |
| `Ticket à compléter (parent, début, fin)` | Projet importé par une version précédente du script | Normal : la relance ajoute le parent et les dates **vides**, sans rien remplacer |

### Retour arrière

Tous les tickets importés portent `Repris de ClickUp` dans leur description. Les supprimer à la main avec leurs cycles, ou restaurer la sauvegarde de l'étape 1.

### Choix techniques

| Sujet | Choix |
|---|---|
| Doublons dans Plane | ID ClickUp gardé dans le ticket (`external_source` = `clickup`) ; relancer l'import ne recrée rien |
| Date de fin réelle | Gardée dans la description (« Terminé le : »), car Plane remplace `completed_at` par la date de l'import |
| Cycles passés | Créés avec une fin future, tickets ajoutés, puis vraies dates (Plane refuse d'ajouter à un cycle terminé) |
| État Plane | Premier état du groupe « terminé » ou « à faire » du projet |
| Relance | Crée ce qui manque ; sur un ticket déjà importé, remplit seulement le parent et les dates vides |

Tests (faux Plane local, sans réseau) : `python3 -m unittest discover -s pld/tests`, lancés aussi par `validate.sh`.
