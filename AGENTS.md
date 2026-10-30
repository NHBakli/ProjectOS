# AGENTS.md — Instructions permanentes pour Codex

## Mission

Tu travailles sur **Project OS**, une plateforme DevOps auto-hébergée, versionnée dans Git, qui doit déployer **K3s + Plane + n8n** sur un VPS Linux. Le projet est principalement **Infrastructure as Code**, pas un développement from scratch de l'application Plane.

**Résultat attendu :** une V1 reproductible, documentée, observable, sauvegardable, avec accès web HTTPS et workflows d'automatisation GitHub ↔ Plane. L'utilisateur souhaite travailler rapidement avec Codex comme partenaire d'implémentation, tout en conservant la maîtrise des choix techniques et de l'application des changements sur le VPS.

Lis `README.md` et inspecte le dépôt avant de commencer. Le README décrit l'intention et la roadmap ; **le système de fichiers et les tests priment pour l'état réellement implémenté**.

## Contexte confirmé

- **AegisOps est un projet distinct, déjà utilisé pour préparer et durcir le VPS.** Ne pas recréer le hardening de l'hôte, changer les comptes ou réécrire la configuration SSH.
- Hôte cible : Ubuntu 22.04 dans **LXC / Proxmox**, noyau visible `7.0.2-6-pve`.
- Ressources observées : 9 vCPU, 12 Gio de RAM, ~129 Go disponibles lors des derniers diagnostics.
- VPS avec **IPv4 publique** ; compte non-root administrateur `aegisadmin` avec sudo. Ne jamais codifier l'IP publique, l'alias SSH ou des identifiants réels dans des fichiers suivis par Git.
- cgroups v2 accessibles, ext4 et OverlayFS détectés, systemd fonctionne ; `unshare --net` a réussi ; `iptables -L` a fonctionné.
- `/dev/net/tun` absent ; `modinfo` ne voit pas `vxlan` / `br_netfilter` depuis LXC ; `/proc/sys` monté en lecture seule ; `net.ipv4.ip_forward` observé à `0`.
- Chaîne iptables `f2b-sshd` observée : **Fail2ban est probablement actif**. UFW a été observé inactif, mais ne conclus pas que le réseau est sans protection : les règles hôte/fournisseur peuvent intervenir.
- **K3s n'est pas confirmé installé** et la compatibilité réelle containerd/CNI/stockage n'a pas encore été prouvée. Ne considère pas les diagnostics passés comme un feu vert définitif.
- Utilisation prévue : projet personnel, équipe éventuelle de **5–7 utilisateurs** ; cluster **single-node** initial, sans promesse de haute disponibilité.

## Architecture voulue

1. **Ansible** prépare uniquement les prérequis spécifiques à K3s et installe/configure le cluster sans réappliquer AegisOps.
2. **K3s**, avec configuration versionnée, cluster single-node, kubeconfig protégé, API Kubernetes non publique.
3. **Helm** déploie Plane et ses dépendances, puis n8n, depuis des versions/chart/values épinglés.
4. **Ingress / HTTPS** fournit les accès web ; pas d'exposition directe des bases, brokers ou interfaces d'admin.
5. **Stockage persistant + sauvegardes testées** protègent PostgreSQL, fichiers, paramètres et credentials n8n.
6. **CI**, puis éventuellement **GitOps** (Flux ou Argo CD) quand le cluster et les restaurations sont fiables. Ne pas introduire GitOps par réflexe dès le premier commit.

Plane possède déjà frontend, API/backend et workers. Ne pas écrire un « backend Project OS » parallèle sans besoin explicite. n8n orchestre les automatisations et interactions GitHub/Plane (ex. router les tickets `frontend` et `backend`). Vérifier les API et webhooks réellement disponibles avant de concevoir les workflows.

**Édition de Plane :** ne pas supposer qu'un Helm chart officiel déploie la Community Edition. Vérifier sur la documentation officielle la disponibilité actuelle des éditions, charts et obligations de licence ; choisir la voie compatible avec les exigences et coûts du projet avant de rédiger les valeurs Helm.

## Priorités d'implémentation

### Phase 1 — Repo et compatibilité (commencer ici)
- Inspecter les fichiers et Git ; ne pas détruire ni réorganiser inutilement un dépôt existant.
- Préparer structure IaC, `.gitignore`, inventaire d'exemple, documentation et validation statique.
- Implémenter des **préchecks non destructifs** pour la compatibilité LXC : cgroups, mounts, capacités, réseau, overlay, systemd, prérequis K3s.
- Produire un résultat clair : `READY`, `BLOCKED` ou `NEEDS_VALIDATION`, sans masquer les limites.
- Documenter les changements éventuellement requis côté hôte Proxmox ou fournisseur ; **ne pas** forcer LXC privilégié ni désactiver ses protections.

### Phase 2 — K3s
- Rôle Ansible idempotent, configuration via template (`/etc/rancher/k3s/config.yaml`), version fixée, handlers, tests de syntaxe.
- Décider Flannel (VXLAN / host-gw / autre) **après** validation pratique ; ne pas préjuger que l'absence de TUN est bloquante ni que host-gw résout toutes les limitations LXC.
- Vérifier l'API 6443 et les ports d'exposition avant l'installation. L'API doit être **inaccessible depuis Internet** ; ne pas se reposer uniquement sur l'authentification Kubernetes.
- Valider réellement : `kubectl get nodes`, Pods système, DNS, communication inter-Pods, PVC, redémarrage.

### Phase 3 — Exposition et stockage
- Choisir et documenter la gestion des adresses, DNS, TLS, Secrets, Ingress, StorageClass, PVC et sauvegardes.
- Tester la restauration d'un volume et d'une base avant d'héberger des données importantes.

### Phase 4 — Plane
- Vérifier l'édition et les licences ; épingler un chart et ses versions.
- Déployer et tester frontend, API, workers, jobs/migrations, base/cache/queue/stockage selon les dépendances du chart retenu.
- Configurer HTTPS, comptes, volumes et ressources proportionnées au serveur.

### Phase 5 — n8n + GitHub
- Installer n8n avec persistance et `N8N_ENCRYPTION_KEY` fournie de manière sécurisée.
- Ajouter des webhooks/API GitHub et Plane ; construire d'abord un flux vérifiable et idempotent (éviter les doublons), puis le routage par labels `frontend`/`backend`.
- Ne jamais écrire de tokens en dur ou dans des logs.

### Phase 6 — Opérations
- Documentation de démarrage, de montée de version, des sauvegardes et de la restauration.
- Logs, métriques et alertes adaptés aux ressources ; CI pour lint / templates ; GitOps optionnel après validation.

## Règles de développement

- **Local-first :** écrire dans l'IDE et Git. Pas de modification manuelle permanente des fichiers applicatifs sur le VPS.
- **Infra déclarative :** réutiliser les modules Ansible et charts existants. Éviter `shell`/`command` pour des opérations déjà couvertes par des modules idempotents, sauf justification.
- **Simplicité :** une architecture minimaliste sur un nœud ; pas de composants supplémentaires sans bénéfice concret.
- **Versionning :** épingler versions d'images, charts, collections et K3s ; éviter `latest`.
- **Style :** fichiers YAML propres, noms de tâches explicites, variables documentées, validation/lint, commentaires utiles mais concis.
- **Préservation :** ne pas effacer fichiers/règles/volumes existants ni remplacer des outils déjà installés sans raison et accord.
- **Distinguer constat et hypothèse :** ne pas inventer des ressources existantes, des versions, un fonctionnement de chart ou des tests réussis.
- **Changements ciblés :** livrer des incréments cohérents, explicables, testables, sans gros refactoring prématuré.
- **Documentation :** mettre à jour `README.md` / `docs/` lorsque les commandes, architecture ou procédures changent.

## Sécurité — règles strictes

1. **Aucune modification de SSH, des utilisateurs, de Fail2ban ou des règles de sécurité AegisOps sans demande explicite.**
2. **Ne pas installer/démarrer K3s sur l'hôte public avant d'avoir établi et vérifié la protection de l'API TCP 6443.** Ne pas ouvrir 6443 au monde. Préférer un accès administratif par SSH tunnel ou réseau privé.
3. **Ne pas réinitialiser iptables, nftables ou UFW.** Les composants Kubernetes peuvent ajouter des règles ; évaluer les interactions avec l'existant et documenter le rollback.
4. **Ne pas augmenter arbitrairement les privilèges LXC.** Pas de conversion en conteneur privilégié, pas de retrait de confinement, pas d'accès host indiscriminé.
5. **Jamais de secrets dans Git ou dans la sortie du terminal.** Exclure kubeconfig, token K3s, clés SSH, fichiers `.env` réels, credentials n8n, mots de passe et manifests Secrets en clair. Employer un stockage de secrets chiffré.
6. **Aucune action sur le VPS risquant d'interrompre le réseau, SSH, les données ou de provoquer un redémarrage sans approbation explicite**, plan de retour arrière et accès de secours confirmé.
7. **Pas de `curl | sh` opaque exécuté sans validation.** Si un installateur est utilisé, vérifier la source, figer la version et documenter le comportement.
8. **Préserver les données :** PVC, sauvegardes, migration, restauration ; pas de suppression forcée des ressources persistantes.
9. **Les exécutions de précheck doivent rester en lecture seule.** Les opérations qui créent des interfaces, chargent des modules ou modifient des sysctls doivent être des étapes séparées et approuvées.
10. Les services web accessibles publiquement ne doivent exposer que les ports nécessaires, sous TLS et authentification adaptées.

## Validation et définition du terminé

Avant de qualifier une modification de terminée :

- Syntaxe YAML / Ansible vérifiée ; `ansible-lint` quand disponible.
- Manifests Kubernetes validés (`kubectl --dry-run=client` là où applicable, lint Helm, schémas) sans dépendre d'un cluster pour les tests statiques.
- `helm template` et `helm lint` passés sur les charts/values retenus lorsque Helm est utilisé.
- Aucune fuite de secrets dans les diffs ou le dépôt.
- Idempotence testée pour les rôles modifiant l'hôte (deux exécutions contrôlées, seconde sans modification inattendue).
- Tests réels sur LXC/K3s signalés comme **non effectués** tant qu'ils n'ont pas été exécutés.
- Déploiement et retour arrière documentés ; persistance et restauration vérifiées avant usage en production.

## Format des réponses Codex

Pour chaque tâche, fournis :
1. **Ce qui a été changé**, avec chemins de fichiers.
2. **Pourquoi** (principaux compromis techniques).
3. **Tests lancés et résultats** ; sépare clairement ceux non exécutés.
4. **Risques / prérequis** et éventuelle action à approuver sur le VPS.
5. **Prochaine étape minimale**.

Ne redemande pas des informations déjà présentes dans le dépôt ou ce fichier. Si un paramètre essentiel n'est pas connu (domaine, certificats, édition Plane, politique de sauvegarde), utilise un exemple non secret et signale explicitement la configuration à fournir avant déploiement.

## Première mission à exécuter

**Inspecte le dépôt Project OS avant toute implémentation.** Confirme sa structure et l'état réel des fichiers. Propose puis réalise la **Phase 1** : squelette IaC minimal, inventaire d'exemple sûr, validations statiques et playbook de prérequis K3s **en lecture seule**. Ne déploie rien sur le VPS et ne touche pas à AegisOps. Fournis les commandes de test local et un compte-rendu des éléments encore incertains concernant LXC.