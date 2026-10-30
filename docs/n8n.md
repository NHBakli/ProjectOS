# n8n — préparation de la V1

Le chart officiel n8n `1.17.0` (application `2.44.5`) est épinglé dans
`helm/charts.lock.yaml`. La [documentation du chart](https://github.com/n8n-io/n8n-hosting/blob/main/charts/n8n/README.md)
décrit un mode standalone adapté aux petites installations. Il utilise SQLite
sur un PVC et n'ajoute pas Redis ni PostgreSQL. Ce choix convient au départ pour
un usage personnel ou une petite équipe, sous réserve d'essais et de sauvegardes.
Passer ensuite au mode queue demanderait PostgreSQL et Redis.

`helm/n8n-values.example.yaml` fixe ce mode, un PVC de 5 Gio, un Ingress HTTPS
et des ressources modestes. Les noms `n8n.example.invalid`, `n8n-tls` et la
StorageClass `local-path` sont des exemples à confirmer. L'Ingress suppose un
contrôleur Traefik opérationnel et un certificat TLS déjà présent. Aucun
service de base ou d'administration n'est exposé directement.

## Secrets à fournir avant le déploiement

Le Secret Kubernetes `n8n-secrets` doit exister dans le namespace `n8n` avec
ces clés, sans les inscrire dans Git ni dans les logs :

| Clé | Usage |
|---|---|
| `N8N_ENCRYPTION_KEY` | Clé aléatoire stable ; indispensable pour relire les credentials après restauration. |
| `N8N_HOST` | Domaine public n8n validé. |
| `N8N_PORT` | `5678` pour l'écoute interne. |
| `N8N_PROTOCOL` | `http` derrière la terminaison TLS de l'Ingress. |

La clé doit être conservée dans un fichier chiffré hors Git, par exemple
Ansible Vault, puis injectée avec une procédure qui ne l'affiche pas. Le chart
est configuré pour ne pas générer son Secret principal. Il génère aussi un
token de task runner même lorsque cette fonction est désactivée, sauf si un
Secret existant est indiqué ; le fichier de valeurs indique donc un nom de
Secret de runner mais ne crée pas ce Secret tant que les runners restent
désactivés. Vérifier ce comportement à chaque mise à niveau du chart.

## Tests et données

`helm lint` et `helm template` passent localement avec l'exemple ; le rendu
contient un PVC, un Deployment et un Ingress, sans objet Secret. Cela ne prouve
pas que le Pod démarre, que le PVC fonctionne ou que le TLS est valide.

Avant de créer des workflows, tester la restauration du PVC **avec la même
clé de chiffrement**. La sauvegarde doit couvrir le fichier SQLite, les données
binaires stockées sur le volume et la clé conservée séparément. Une sauvegarde
du seul PVC sans la clé ne suffit pas à restaurer les credentials.

Les webhooks GitHub et Plane seront configurés après validation des API, du
domaine HTTPS et de la persistance. Le premier flux devra être idempotent et
vérifiable avant le routage par labels.
