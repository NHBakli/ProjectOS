# Choix techniques

| Sujet | Choix | Pourquoi |
|---|---|---|
| Kubernetes | K3s, un seul nœud | Léger, adapté à un seul VPS. Pas de haute disponibilité. |
| Installation | Ansible depuis le poste local | Reproductible, versionné, rien à la main sur le serveur |
| Réseau des Pods | Flannel `vxlan` | Mode par défaut, testé sur la VM |
| Entrée web | Traefik et ServiceLB fournis par K3s | Rien à installer en plus, version liée à K3s |
| Certificats | cert-manager + Let's Encrypt | Gratuit, renouvellement automatique |
| Domaine | sslip.io (provisoire) | Gratuit, immédiat. À remplacer avant l'arrivée de l'équipe. |
| Déploiement des charts | `HelmChart` intégré à K3s | Pas besoin de Helm sur le poste ni de tunnel |
| Chart n8n | Archive gardée dans `helm/charts/`, empreinte vérifiée | K3s ne lit pas les charts OCI ; protège aussi contre une modification du registre |
| Stockage | `local-path` (disque du VPS) | Simple. Les données ne survivent pas à la perte du VPS : d'où les sauvegardes. |
| Secrets | Ansible Vault | Déjà dans Ansible, chiffré, rien en clair |
| n8n | Mode simple (SQLite) | Suffit pour 5 à 7 personnes |
| Synchronisation | Plane → GitHub, création seulement | Plane est la source de vérité. Le label d'équipe choisit le dépôt et le projet GitHub. Un seul sens : pas de boucle. |
| Plane | Un seul projet, labels d'équipe | Simple pour 5 à 7 personnes |
| Doublons | Lien GitHub enregistré dans le ticket Plane | Vérifié avant chaque création ; rien à stocker dans n8n |
| Webhook Plane | Signature HMAC vérifiée dans n8n | L'URL du webhook est publique |
| GitOps (Flux, Argo CD) | Pas maintenant | Seulement quand les sauvegardes et restaurations seront fiables |

## Plane : Community ou Commercial ?

**Community Edition retenue.**

| | Community | Commercial (gratuit) |
|---|---|---|
| Licence | Open source (AGPL-3.0) | Code fermé, système de licence Plane |
| Utilisateurs | Pas de limite publiée | 12 par espace de travail |
| Fonctions payantes | Non. Il faudrait migrer. | Oui, sur abonnement |
| Chart | `plane-ce` 1.8.5 | `plane-enterprise` 3.10.12 |

Les valeurs Commercial (`helm/plane-commercial-values.example.yaml`) sont gardées pour comparaison seulement.

## Versions épinglées

Toutes les versions sont dans [`helm/charts.lock.yaml`](../helm/charts.lock.yaml) et dans les `defaults` du rôle K3s. On ne met jamais `latest`.
