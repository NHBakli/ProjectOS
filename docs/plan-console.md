# Plan : console web du VPS (supervision + génération du PLD)

Statut : **plan, à valider**. Rédigé le 2026-11-06.

## Objectif

Une petite page web, dans K3s, qui affiche :

1. l'état du VPS : CPU, RAM, disque, charge, uptime, avec un historique sur une période choisie ;
2. l'état de la plateforme : pods, redémarrages, certificats TLS ;
3. la sécurité : jails Fail2ban, bans en cours et cumulés ;
4. un formulaire **PLD** : dates (`du`, `au`) ou sprints → Word + Excel + rapport à télécharger.

## Mémoire disponible (mesuré le 2026-11-06, lecture seule)

| | |
|---|---|
| Utilisée par les programmes | 3,6 Go / 12 Go |
| Disponible | 8,3 Go |
| Le « 92 % » du panneau de l'hébergeur | compte le cache disque (8,1 Go), libéré à la demande |
| Coût prévu de la console | ~100 Mo, pic ~250 Mo pendant une génération de PLD |

## Choix faits (2026-11-06)

| Sujet | Choix |
|---|---|
| Génération du PLD | **Sur le serveur**, depuis la page. Le script en local reste utilisable. |
| Métriques | **Page maison légère**, sans conteneur privilégié |
| Accès (qui, comment se connecter) | **À trancher plus tard.** En attendant : aucune exposition, accès par tunnel SSH |

## Architecture proposée

| Élément | Rôle |
|---|---|
| Namespace `console`, 1 Deployment | Petite application Python, réutilise `pld/` pour le PLD |
| Image | Python officielle épinglée par empreinte ; dépendances installées au démarrage avec `pip --require-hashes` ; code en ConfigMap. Pas de registre à gérer. |
| Métriques Kubernetes | API `metrics.k8s.io` (metrics-server, déjà présent), ServiceAccount en **lecture seule** (RBAC) |
| Fail2ban, disque, uptime | Timer systemd sur l'hôte (rôle Ansible) : chaque minute, il écrit ces chiffres dans une ConfigMap. Le pod n'a aucun accès à l'hôte. |
| Historique | SQLite sur un petit volume (PVC 1 Gio), 30 jours, un point par minute |
| Secrets PLD | Clé Plane, token GitHub **lecture seule** (Flowly-PBS), `pld.yml` (noms des membres), modèles Epitech : Secrets Kubernetes créés depuis Ansible Vault, **jamais dans Git** |
| Plane | Appelé par son service interne au cluster |
| Sécurité du pod | `runAsNonRoot`, `readOnlyRootFilesystem`, sans capacités, limites CPU/RAM, NetworkPolicy |
| Exposition | Service `ClusterIP` seulement, accès par `kubectl port-forward` dans un tunnel SSH, jusqu'au choix de l'accès |

## Étapes

1. Rôle Ansible du timer hôte → ConfigMap `console-hote`. Test : 2ᵉ exécution `changed=0`.
2. Application : métriques + historique, testée en local (cluster `kind`, `infrastructure/kind/`).
3. Page PLD : formulaire (dates ou sprints), génération en tâche de fond, téléchargement.
4. Secrets : `scripts/generate-secrets.sh console` (Vault), token GitHub fine-grained en lecture seule.
5. Playbook `deploy-console.yml`, sauvegarde du volume, retour arrière.
6. Accès : à trancher (connexion GitHub, mot de passe, ou tunnel SSH seulement).

## Points à trancher

| Question | Proposition |
|---|---|
| Accès | Plus tard. Options : connexion GitHub limitée à Flowly-PBS (oauth2-proxy), mot de passe unique, tunnel SSH seulement |
| Durée de l'historique | 30 jours |
| Sauvegardes affichées | Elles sont sur le poste : afficher la date de la dernière seulement si le playbook de sauvegarde la dépose sur le serveur |
