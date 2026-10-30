# Contrat des Secrets

Les fichiers Helm versionnés ne contiennent que des **noms** de Secrets. Les
valeurs réelles doivent être gardées dans un coffre chiffré, par exemple un
fichier Ansible Vault privé et exclu de Git. Ne pas passer les valeurs avec
`--set`, `-e` ou une commande qui les affiche dans l'historique du shell.

Avant de déployer un chart, créer ses Secrets dans le même namespace et vérifier
leurs **noms et clés seulement**, sans imprimer les valeurs. L'exécution devra
être faite sous `no_log` ou avec un mécanisme de secret chiffré équivalent. Les
Secrets Kubernetes sont protégés au repos par la configuration K3s prévue,
mais leurs détenteurs conservent l'accès aux données ; limiter les droits RBAC.

## n8n

Namespace `n8n`, Secret `n8n-secrets` :

| Clé | Valeur attendue |
|---|---|
| `N8N_ENCRYPTION_KEY` | Clé aléatoire, stable, sauvegardée séparément. |
| `N8N_HOST` | Domaine n8n choisi. |
| `N8N_PORT` | Port interne `5678`. |
| `N8N_PROTOCOL` | `http` derrière l'Ingress TLS. |

## Plane Community Edition

Namespace `plane`. Les noms suivent `helm/plane-ce-values.example.yaml` :

| Secret | Clés requises par les workloads |
|---|---|
| `plane-app-keys` | `SECRET_KEY`, `LIVE_SERVER_SECRET_KEY` ; ne pas faire tourner ces clés sans procédure de migration. |
| `plane-app-env` | `REDIS_URL`, `DATABASE_URL`, `AMQP_URL` avec les mêmes identifiants que les services. |
| `plane-live-env` | `REDIS_URL`. |
| `plane-postgres` | `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`. |
| `plane-rabbitmq` | `RABBITMQ_DEFAULT_USER`, `RABBITMQ_DEFAULT_PASS`. |
| `plane-doc-store` | `FILE_SIZE_LIMIT`, `AWS_S3_BUCKET_NAME`, `USE_MINIO`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_S3_ENDPOINT_URL`. |

La documentation du chart indique que `app_keys_existingSecret` injecte les
clés de signature dans les services concernés. Les URLs de `plane-app-env`
doivent contenir les mêmes mots de passe que `plane-postgres` et
`plane-rabbitmq` ; le chart ne les reconstruit pas à partir des autres Secrets.
Le Secret du stockage doit rester cohérent avec le nom du Service MinIO et le
bucket configuré. Toute valeur d'exemple publiée dans le chart est impropre au
déploiement.

## Plane Commercial Free

Les Secrets PostgreSQL, RabbitMQ et stockage ont les mêmes rôles. La variante
Commercial ajoute notamment `plane-silo-env` et peut demander des clés pour
ses services supplémentaires. Les noms candidats figurent dans
`helm/plane-commercial-values.example.yaml`. Le contrat exact sera finalisé
après le choix de l'édition et une revue des services réellement activés.

## Vérifications avant installation

1. Générer les clés localement, dans le coffre chiffré ; ne pas les afficher.
2. Confirmer que tous les Secrets attendus existent dans le bon namespace et
   que leurs noms de clés correspondent au chart retenu.
3. Vérifier que le rendu `helm template` ne crée aucun objet Secret avec des
   valeurs d'exemple. `scripts/validate-helm.sh` contrôle ce point.
4. Sauvegarder séparément les clés de déchiffrement et tester la restauration.

Les références des charts et leurs valeurs d'exemple sont dans
`helm/charts.lock.yaml` et dans la documentation des charts officiels
[Plane](https://developers.plane.so/self-hosting/methods/kubernetes) et
[n8n](https://github.com/n8n-io/n8n-hosting/blob/main/charts/n8n/README.md).
