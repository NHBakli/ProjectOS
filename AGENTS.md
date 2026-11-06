# AGENTS.md — Contexte et règles pour les agents IA

À lire en entier avant toute action. Source unique pour tous les agents (Codex, Claude Code…) : `CLAUDE.md` importe ce fichier.

## Le projet

**Project OS** : plateforme de gestion de projets auto-hébergée, décrite en Infrastructure as Code.
**K3s** (un nœud) + **Plane** (projets, tickets) + **n8n** (automatisations GitHub ↔ Plane), sur un VPS.
Tout s'installe depuis le poste local avec **Ansible**. On n'écrit pas d'application : on assemble et on exploite.

Utilisateur : francophone, travaille vite, garde la main sur les choix et lance lui-même les commandes qui modifient le VPS. Équipe prévue : 5–7 personnes. Pas de haute disponibilité.

## Le projet géré : Flowly (Epitech ESP)

Project OS sert à piloter **Flowly** : application de productivité gamifiée (desktop + mobile, sessions de focus, points, monde 3D), projet Epitech ESP d'une équipe de 7.
**Motivation principale de l'utilisateur : générer automatiquement le PLD** (Project Log Document) Epitech à partir de Plane et GitHub.

| Élément | Valeur |
|---|---|
| Organisation GitHub | `Flowly-PBS` : dépôts `Frontend`, `Backend`, `Mobile`, `DevOps` (créé le 2026-10-31), `Documentation` (public), `Contenu3D` |
| Projets GitHub | 1 « Flowly team back », 2 « Frontend Team », 3 « Mobile Team », 4 « Devops » (auto-add des issues `Backend`), 5 « DevOps Team ». IDs dans le workflow n8n. |
| Plane | Espace de travail `flowly`, projet Flowly `4574eea4-a44e-433f-b57e-435859d0d726`, étiquettes `Frontend`, `Backend`, `DevOps`, `Mobile` |
| n8n | Workflow « Plane vers GitHub (Flowly-PBS) », identifiants `Plane API`, `GitHub token` (fine-grained, Flowly-PBS), `DeepL` (API Free). Secret du webhook Plane dans le nœud **Signature HMAC1**. |
| Équipe (noms ↔ comptes GitHub) | `Flowly-PBS/Documentation` → `PLD/PLD_Releve_Sprint_1.md`. **Ne pas recopier dans ce dépôt public.** |
| PLD Sprint 1 | Fait à la main : `Flowly-PBS/Documentation` → `PLD/1st Keynote/1st Follow-up/` |

## Travailler avec l'utilisateur

- Il fait lui-même les étapes dans les interfaces web (Plane en **français**, n8n et GitHub en **anglais**) et envoie des captures. Le guider **clic par clic**, avec les libellés exacts.
- Libellés et chemins Plane : les vérifier dans le code source v1.4.2 (`packages/i18n/src/locales/fr/`, routes `apps/web/app/`) avant de les donner. Le code n'est pas gardé sur le poste : `git clone --depth 1 --branch v1.4.2 https://github.com/makeplane/plane.git` dans le dossier temporaire de la session. API publique : `apps/api/plane/api/` (urls, views, serializers).
- Ne jamais lui demander de coller un token, une clé ou un secret. S'il colle l'IP du serveur, ne pas la répéter.
- Pour un choix qui lui revient : questions à options, avec une recommandation.
- n8n 2.x : après une modification, **Save** puis **Publish**, sinon l'ancienne version reste active.

## État au 2026-11-06

| Brique | État |
|---|---|
| VPS | VM KVM, Ubuntu 24.04.5, 9 vCPU, ~11 Gio RAM. UFW (AegisOps) + Fail2ban. Ports publics : 22, 80, 443. |
| K3s `v1.37.1+k3s1` | ✅ Installé par le rôle Ansible, idempotent, survit au reboot. API 6443, kubelet et NodePorts fermés depuis Internet. |
| HTTPS | ✅ Traefik (fourni par K3s) + cert-manager `v1.21.3` + Let's Encrypt. Domaine **provisoire sslip.io**. |
| Plane CE `v1.4.2` (chart `plane-ce` 1.8.5) | ✅ En ligne, compte admin créé |
| n8n `2.44.5` (chart 1.17.0, SQLite) | ✅ En ligne, compte propriétaire créé |
| Sauvegardes | ✅ Plane et n8n chiffrées (gpg) vers le poste, restaurations testées. Lancement manuel. Dernières : 2026-11-02 (avant l'import ClickUp). |
| Workflow Plane → GitHub | ✅ En service avec traduction DeepL. Test réel 2026-11-01 : `Frontend#48`, `Backend#34` OK. |

Workflow Plane → GitHub (`docs/06-plane-github.md`) : label Plane `frontend`/`backend`/`mobile`/`devops` → dépôt + projet GitHub de Flowly-PBS, traduction DeepL, anti-doublon par lien dans le ticket. Les projets GitHub ont un auto-add (« already exists in this project » = succès). Dans le n8n de l'utilisateur, les nœuds ont un suffixe `1`.

Détails et journal : `docs/00-etat.md`. Choix techniques : `docs/decisions.md`.

## Reprise ClickUp (terminée le 2026-11-06)

Sujet : **reprendre l'historique ClickUp dans Plane** (étape 0 du PLD). Guide : `docs/07-import-clickup.md`.

| | |
|---|---|
| Fait | Extraction réelle (`~/projectos-pld/clickup/clickup-20261102T200905Z.json`). Sprints = **tâches parentes** (Phase 2, Phase 3, Sprint 1, Sprint 2), 38 sous-tâches. Ni points ni estimations. |
| Choix de l'utilisateur | 4 cycles Plane, **tous terminés** (Sprint 2 fini le 2026-10-23, tâches restées « à faire ») ; **pas d'assignés** ; tâches déjà en issue GitHub = lien ajouté, **jamais d'issue recréée** ; import sans étiquette d'équipe. |
| ⚠️ Changement de cap | L'utilisateur dit que **les prochaines tâches seront créées directement dans GitHub** (plus dans Plane). Le PLD croisera Plane (historique) et les backlogs GitHub (qui a fait quoi, ce qui est fini). À répercuter dans `docs/plan-pld.md` : sens du workflow n8n, source de vérité, estimations. |
| Table validée | `~/.config/projectos/pld.yml` (hors Git) : 38 tâches, 31 issues GitHub citées (toutes vérifiées existantes), sections `plane:` et `clickup_import:`. |
| Importeur | `pld/clickup_importer.py` : `--plan` (hors ligne), essai à blanc par défaut (GET seulement), `--appliquer` (confirmation `oui`), `--projet` pour un projet jetable. Tests face à un faux Plane. |
| Essai 2026-11-02 | Projet jetable `test` (`0e5fe1d2-…`) : import OK (38 tickets, 33 liens, 4 cycles, 121 requêtes). Retour de l'utilisateur : il veut les **tickets parents** (phases, sprints) comme ClickUp, et des **dates** sur les tâches. Ajouté : ticket parent + cycle, dates du sprint héritées, relance qui complète parent/dates vides sans rien remplacer. Relance sur `test` validée par l'utilisateur le 2026-11-03. Projet `test` supprimé. |
| Import réel 2026-11-06 | Projet Flowly : 42 tickets (4 parents + 38), 33 liens, 4 cycles. Résultat annoncé OK par l'utilisateur. |
| En attente de l'utilisateur | Supprimer la clé Plane « Import ClickUp » et son CSV dans `~/Downloads`, régénérer le token ClickUp, `git push`. |

Contraintes de Plane v1.4.2 trouvées dans le code (à respecter dans l'import) :

| Contrainte | Où | Parade |
|---|---|---|
| Pas d'importeur dans la CE (la page « Importations » n'existe pas) | `packages/constants/src/settings/workspace.ts` | Script par l'API |
| Ajout de tickets à un cycle terminé refusé (`CYCLE_COMPLETED`), et un cycle terminé ne se modifie plus | `api/views/cycle.py` (~l. 561 et 982) | Créer le cycle avec une fin future, ajouter les tickets, puis PATCH des vraies dates |
| `completed_at` en lecture seule, mis à `now()` au passage à l'état terminé | `db/models/issue.py` `_sync_completed_at` | Vraie date de fin dans la description (« Terminé le : »), lue par le générateur de PLD |
| Anti-doublon natif : `external_source` + `external_id` (409 si déjà présent, filtre en GET) | `api/views/issue.py` (~l. 331, 468) | `external_source=clickup`, `external_id` = ID de la tâche |
| Un ticket créé avec l'étiquette `Frontend`/`Backend`… déclenche le workflow n8n → issue GitHub | workflow n8n | Importer sans étiquette d'équipe, ou faire ignorer à n8n les tickets `external_source=clickup` (vérifier d'abord que le webhook contient ce champ) |

## La suite (dans l'ordre)

1. **Générer le PLD Epitech depuis Plane + GitHub** : plan validé dans `docs/plan-pld.md`, **à implémenter** (étapes 1 à 7). Choix de l'utilisateur : script sur le poste, modèle de description dans les tickets, chiffres + texte fixe, période = entre deux remises. Modèles officiels hors Git : `~/Downloads/PLD_Template.docx`, `PLD_Suivi_Taches.xlsx`, `Processus_PLD (1).pdf`. Brouillon du Sprint 1 : dépôt `Flowly-PBS/Documentation`, dossier `PLD/`. Commencer par les « Points à trancher » du plan.
   **Étape 0 finie (2026-11-06) : historique ClickUp importé dans Plane** → `docs/07-import-clickup.md`.
   Les projets GitHub de Flowly-PBS ont déjà les champs `Status`, `Estimate`, `Start date`, `Target date` (projet 1 : `Iteration` au lieu des dates). Aucun modèle d'issue (`.github/ISSUE_TEMPLATE`) dans les dépôts.
   **Ensuite** : revoir `docs/plan-pld.md` après le changement de cap (tâches créées dans GitHub), trancher ses « Points à trancher », puis l'étape 1 (squelette). Les tickets parents (phases, sprints) ne comptent pas comme des cartes.
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
| `pld/` | Générateur de PLD (en cours) : `clickup_extraire.py`, `clickup_importer.py`, tests dans `pld/tests/` (lancés par `validate.sh`) |
| `~/projectos-pld/` (hors Git) | Extractions ClickUp (contiennent noms et e-mails) |
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
