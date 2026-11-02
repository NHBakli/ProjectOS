# Reprendre l'historique ClickUp dans Plane

Les anciennes sprints et tâches de ClickUp passent dans Plane, une seule fois.
Plane Community n'a pas de page « Importations » : on passe par l'API.

| Étape | État |
|---|---|
| 1. Extraire ClickUp (lecture seule) | ✅ Faite le 2026-11-02 |
| 2. Faire correspondre (cycles, statuts, issues GitHub) | ✅ Choix faits, table des issues à valider |
| 3. Importer dans Plane | À faire |

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
| Tâche parente | Un **cycle**, avec ses dates. Les 4 sont repris. |
| Sprint N°2 | Cycle **en cours** : nouvelle date de fin à fixer |
| Sous-tâche | Un ticket dans le cycle |
| `complete` / `to do` | État du groupe « terminé » / « à faire » |
| Assignés | **Non repris.** Les prochaines tâches naissent dans GitHub : le PLD lira qui a fait quoi dans GitHub. |
| Tâche déjà en issue GitHub | Lien vers l'issue ajouté au ticket. **Aucune issue recréée.** |

### Pas de doublon dans GitHub

1. Les tickets importés n'ont **pas d'étiquette d'équipe** : le workflow n8n ne se déclenche pas.
2. Ils portent le lien de leur issue GitHub, au même format que n8n. Si quelqu'un ajoute une étiquette plus tard, n8n voit le lien et ne crée rien.

La table tâche ClickUp → issue GitHub est dans `~/.config/projectos/pld.yml` (hors Git), validée à la main.

## 4. Importer dans Plane

À écrire : `pld/clickup_importer.py`.

| Sujet | Choix |
|---|---|
| Doublons dans Plane | ID ClickUp gardé dans le ticket (`external_source` = `clickup`) ; relancer l'import ne recrée rien |
| Date de fin réelle | Gardée dans la description (« Terminé le : »), car Plane remplace `completed_at` par la date de l'import |
| Cycles passés | Créés avec une fin future, tickets ajoutés, puis vraies dates (Plane refuse d'ajouter à un cycle terminé) |
| Sécurité | Sauvegarde Plane avant, essai à blanc, puis essai dans un projet jetable |
