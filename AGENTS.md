# AGENTS.md — Contexte et règles pour les agents IA

À lire en entier avant toute action. Source unique pour tous les agents (Codex, Claude Code…) : `CLAUDE.md` importe ce fichier.

## Le projet

**Project OS** : plateforme de gestion de projets auto-hébergée, décrite en Infrastructure as Code.
**K3s** (un nœud) + **Plane** (projets, tickets) + **n8n** (automatisations GitHub ↔ Plane), sur un VPS.
Tout s'installe depuis le poste local avec **Ansible**. On n'écrit pas d'application : on assemble et on exploite.

Utilisateur : francophone, travaille vite, garde la main sur les choix et lance lui-même les commandes qui modifient le VPS. Équipe prévue : 5–7 personnes. Pas de haute disponibilité.

## État au 2026-10-31

| Brique | État |
|---|---|
| VPS | VM KVM, Ubuntu 24.04.5, 9 vCPU, ~11 Gio RAM. UFW (AegisOps) + Fail2ban. Ports publics : 22, 80, 443. |
| K3s `v1.37.1+k3s1` | ✅ Installé par le rôle Ansible, idempotent, survit au reboot. API 6443, kubelet et NodePorts fermés depuis Internet. |
| HTTPS | ✅ Traefik (fourni par K3s) + cert-manager `v1.21.3` + Let's Encrypt. Domaine **provisoire sslip.io**. |
| Plane CE `v1.4.2` (chart `plane-ce` 1.8.5) | ✅ En ligne, compte admin créé |
| n8n `2.44.5` (chart 1.17.0, SQLite) | ✅ En ligne, compte propriétaire créé |
| Sauvegardes | ✅ Plane et n8n chiffrées (gpg) vers le poste, restaurations testées. Lancement manuel. |
| Workflow Plane → GitHub | 🟡 Installé. Test réel : issue + lien Plane OK ; ajout au projet GitHub **échoue** (cause non lue). Traduction DeepL écrite et testée en local, pas installée. |

Détails et journal : `docs/00-etat.md`. Choix techniques : `docs/decisions.md`.

## La suite (dans l'ordre)

1. **Installer le workflow Plane → GitHub** (`docs/06-plane-github.md`). Choix de l'utilisateur : sens **Plane → GitHub**, création seulement ; **un seul projet Plane** avec labels d'équipe ; organisation GitHub **Flowly-PBS**.
   - Routage : `frontend` → dépôt `Frontend` + projet 2, `backend` → `Backend` + projet 1, `mobile` → `Mobile` + projet 3, `devops` → `DevOps` (créé le 2026-10-31) + projet 5. Seuls les labels **Plane** comptent ; aucun label n'est posé côté GitHub.
   - Anti-doublon : lien GitHub enregistré dans le ticket Plane, vérifié avant création. Signature HMAC du webhook Plane vérifiée.
   - Vérifié dans le code de Plane v1.4.2 (`webhook_task.py`, API `work-items/…/links/`, en-tête `X-Api-Key`). Testé dans n8n 2.44.5 local avec de fausses API.
   - Test réel (2026-10-31) : Plane → n8n via l'URL publique OK, issue `Flowly-PBS/Frontend#47` + lien Plane OK. **Ajout au projet GitHub absent** : lire l'erreur de l'exécution n8n (permission Projects du token ?).
   - Traduction : DeepL API Free (identifiant n8n `DeepL`, en-tête `Authorization: DeepL-Auth-Key …`), FR → EN-US, original FR dans `<details>`. Si DeepL échoue, issue en français avec avertissement.
2. **Sauvegardes** : copie hors du poste (disque externe ou cloud), puis automatisation. Le datastore K3s n'est pas encore sauvegardé.
3. **Vrai domaine** (ou DuckDNS) avant d'inviter l'équipe. Il faudra changer les URL de Plane, n8n et des webhooks.
4. Plus tard : observabilité légère, CI de déploiement, GitOps seulement quand les restaurations sont fiables. n8n signale que le mode « task runner interne » sera retiré : passer en runners externes lors d'une mise à jour.

## Comment on travaille

1. Écrire et valider **en local** : `./scripts/validate.sh` (yamllint, ansible-lint, syntax-check). Pour Helm : `./scripts/validate-helm.sh` (Helm 3.22.1). Pour les workflows n8n : `./scripts/test-n8n-workflow.sh`.
2. Tester les rendus Jinja/Helm en local avec de fausses valeurs avant de livrer.
3. Committer : message en français, un commit par incrément cohérent.
4. Donner à l'utilisateur **les commandes exactes** à lancer et le **résultat attendu**. Il colle la sortie, on analyse.
5. L'agent peut faire des vérifications **en lecture seule** sur le VPS : inventaire privé `~/.config/projectos/hosts.yml` (IP, compte et clé SSH, `sudo -n` disponible), `k3s kubectl get/describe/logs`, tests `nc`/`curl` depuis le poste. Toute modification passe par un playbook lancé avec l'accord de l'utilisateur.
6. L'agent **ne connaît pas le mot de passe Vault** : les playbooks qui chargent un fichier `*.vault.yml` sont lancés par l'utilisateur (`--ask-vault-pass`).
7. Mettre à jour `README.md` et `docs/` à chaque changement. **Style imposé** : court, phrases simples, étapes numérotées, commandes copiables, « Attendu », « En cas de problème », « Retour arrière ». Pas de `<...>` dans les commandes : bash le lit comme une redirection.

## Fichiers clés

| Chemin | Rôle |
|---|---|
| `infrastructure/ansible/roles/k3s/` | Installation de K3s et préparation de l'hôte (modules, sysctl, UFW) |
| `infrastructure/ansible/playbooks/` | `deploy-*`, `backup*.yml`, `restore-test-*`, `verify-k3s`, `smoke-*` |
| `helm/*-values.yaml`, `helm/charts.lock.yaml`, `helm/charts/` | Valeurs, versions épinglées, archive n8n vendorisée |
| `kubernetes/` | Manifests cert-manager et smoke tests |
| `scripts/generate-secrets.sh plane\|backup\|n8n` | Crée les secrets directement chiffrés (Vault), un seul mot de passe |
| `n8n/workflows/` | Workflows n8n à importer (sans secret ni domaine) |
| `scripts/test-n8n-workflow.sh` | Teste un workflow dans un n8n local (Docker) face à de fausses API Plane/GitHub |
| `~/.config/projectos/` (hors Git) | `hosts.yml`, `k3s-approval.yml`, `platform.yml`, `*.vault.yml` |
| `~/projectos-backups/` (hors Git) | Sauvegardes chiffrées |

Les déploiements passent par le **CRD `HelmChart` de K3s** (pas de Helm sur le poste). K3s ne lit pas les charts OCI : l'archive n8n est dans `helm/charts/`, son SHA-256 est vérifié.

## Pièges déjà rencontrés

- `(... | from_json).items` désigne la méthode Python : écrire `['items']`.
- En YAML, `- -` est une liste imbriquée : écrire `- '-'`.
- Dans une chaîne Jinja, `'\1'` devient le caractère `\x01`.
- Les NodePorts et `hostPort` **contournent UFW** (DNAT) : NodePorts limités à `127.0.0.1`, n'exposer que Traefik.
- `kubectl apply --server-side` répond toujours `serverside-applied` : utiliser `kubectl diff` pour l'idempotence.
- Le CLI n8n écrit ses journaux sur stdout : compter dans la base (`node:sqlite`, lecture seule), pas dans sa sortie.
- Plusieurs fichiers Vault chargés ensemble doivent avoir le **même** mot de passe. Récupération possible depuis les Secrets du cluster (`docs/secrets.md`).
- Webhook Plane : la signature `X-Plane-Signature` est un HMAC-SHA256 du corps brut. Le vérifier sur le corps brut (option *Raw Body* du nœud Webhook), jamais sur un JSON resérialisé.
- La page `/god-mode/` de Plane et la première page de n8n donnent les droits admin au premier visiteur : créer les comptes tout de suite.

## Règles de développement

- **Local-first :** tout dans Git. Pas de modification manuelle permanente sur le VPS.
- **Déclaratif :** modules Ansible et charts existants. `shell`/`command` seulement si justifié, avec `changed_when`.
- **Simplicité :** pas de composant sans bénéfice concret.
- **Versions épinglées** partout (images, charts, collections, K3s). Jamais `latest`.
- **Préservation :** ne pas effacer fichiers, règles ou volumes existants sans accord.
- **Constat ≠ hypothèse :** ne pas inventer versions, comportements de chart ou tests réussis. Dire clairement ce qui n'a pas été exécuté.
- **Changements ciblés**, testables, sans gros refactoring prématuré.

## Sécurité — règles strictes

1. **Ne pas toucher** à SSH, aux comptes, à Fail2ban ni aux règles AegisOps sans demande explicite.
2. **L'API Kubernetes (6443) reste fermée** sur Internet. Accès admin par tunnel SSH.
3. **Ne jamais réinitialiser** iptables, nftables ou UFW.
4. **Pas d'augmentation arbitraire de privilèges** (conteneurs privilégiés, `hostPath`, `hostNetwork`…).
5. **Aucun secret dans Git ni dans la sortie du terminal** : IP publique, kubeconfig, tokens, clés, mots de passe, Secrets en clair. Secrets dans Ansible Vault, tâches sensibles sous `no_log`.
6. **Aucune action risquant le réseau, SSH, les données ou un redémarrage** sans accord explicite, retour arrière et accès de secours.
7. **Pas de `curl | sh`.** Sources vérifiées, versions figées, empreintes contrôlées.
8. **Préserver les données :** sauvegarder avant toute mise à jour. Ne jamais supprimer un PVC ou un namespace applicatif sans restauration testée.
9. Les vérifications restent **en lecture seule**. Les tests qui créent des ressources sont des étapes séparées, approuvées, nettoyées ensuite.
10. N'exposer publiquement que le nécessaire, sous TLS et authentification.

## Définition du terminé

- `validate.sh` passe (et `validate-helm.sh` si Helm est concerné).
- Aucune fuite de secret dans le diff (`git diff | grep` sur l'IP).
- Idempotence vérifiée pour ce qui modifie l'hôte (2ᵉ exécution : `changed=0`).
- Tests réels sur le VPS signalés **non effectués** tant qu'ils ne l'ont pas été.
- Déploiement, retour arrière et sauvegarde documentés.

## Format des réponses

Court et en français :
1. Ce qui a changé (fichiers).
2. Pourquoi (en une ou deux phrases).
3. Tests lancés et résultats ; ce qui n'a pas été testé.
4. Commandes à lancer par l'utilisateur, avec le résultat attendu.
5. Prochaine étape.
