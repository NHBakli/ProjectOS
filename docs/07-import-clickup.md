# Reprendre l'historique ClickUp dans Plane

Les anciennes sprints et tâches de ClickUp passent dans Plane, une seule fois.
Plane Community n'a pas de page « Importations » : on passe par l'API.

| Étape | État |
|---|---|
| 1. Extraire ClickUp (lecture seule) | ✅ Script prêt : `pld/clickup_extraire.py` |
| 2. Faire correspondre statuts, membres, tags | À faire, d'après le résumé de l'étape 1 |
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

## 2 et 3. Correspondances et import

Prévu, pas encore écrit. Principes retenus :

| Sujet | Choix |
|---|---|
| Sprints ClickUp | Un **cycle Plane** par sprint, avec ses vraies dates |
| Doublons | ID ClickUp gardé dans le ticket (`external_source` = `clickup`) ; relancer l'import ne recrée rien |
| Date de fin réelle | Gardée dans la description (« Terminé le : »), car Plane remplace `completed_at` par la date de l'import |
| Issues GitHub | L'import ne doit pas déclencher le workflow n8n Plane → GitHub |
| Sécurité | Sauvegarde Plane avant, essai à blanc, puis essai dans un projet jetable |
