# Sauvegarde et restauration — plan V1

**Plan préparatoire, non exécuté.** Le support de sauvegarde hors VPS, la
rétention et les procédures concrètes seront choisis avant d'héberger des
données. Un PVC `local-path` sur un seul nœud ne résiste pas à la perte de l'hôte.

| Donnée | Sauvegarde requise | Vérification de restauration |
|---|---|---|
| K3s | Datastore SQLite sous `/var/lib/rancher/k3s/server/db/` et token serveur `/var/lib/rancher/k3s/server/token`, conservés de manière cohérente et chiffrée. | Restaurer dans un environnement isolé et vérifier l'API et les objets. |
| Plane | Export cohérent de PostgreSQL et copie des objets MinIO ; sauvegarder aussi valeurs Helm et Secrets chiffrés. | Retrouver un projet, un ticket et une pièce jointe. |
| n8n | PVC contenant SQLite et fichiers n8n, plus `N8N_ENCRYPTION_KEY` conservée séparément. | Retrouver un workflow et vérifier qu'un credential se déchiffre. |
| TLS | Certificats et clés ou capacité de les réémettre, selon la solution choisie. | Servir les deux domaines en HTTPS sans alerte de certificat. |

K3s précise que le **même token serveur** est nécessaire à la restauration du
datastore ; sans lui, les données confidentielles qu'il protège ne seront pas
lisibles. Voir la [documentation officielle K3s](https://docs.k3s.io/datastore/backup-restore).
Plane demande de sauvegarder PostgreSQL et le stockage objet, puis la
configuration ; voir sa [documentation officielle](https://developers.plane.so/self-hosting/manage/backup-restore).

## Décisions à prendre avant la mise en service

- Destination chiffrée **hors du VPS** : stockage objet, autre serveur ou
  service de sauvegarde, avec accès limité et budget connu.
- Fréquence et rétention : exemple initial quotidien 7 jours, hebdomadaire
  4 semaines, à confirmer selon la valeur des données.
- Méthode de cohérence PostgreSQL et SQLite, vérifiée sur les versions retenues.
- Espace disponible, surveillance des échecs, et personne avertie en cas de
  sauvegarde manquée.
- Exercice de restauration dans un environnement isolé avant données réelles,
  puis à intervalle régulier.

Ne pas supprimer un ancien PVC, token, Secret ou volume au cours d'un retour
arrière tant que les sauvegardes et leur restauration ne sont pas validées.
