# Reprise du travail — 2026-10-26

## Mise à jour du 2026-10-28

L'administrateur indique que Kubernetes est maintenant accessible et que le
VPS a été sécurisé. C'est une information reçue, pas encore une validation
technique effectuée par Project OS. Le kubeconfig local présent sur le poste
ne contient que les contextes `kind-website` et `minikube` ; aucun accès au
cluster du VPS n'a pu être identifié dans le dépôt. La validation statique
Ansible locale passe. Le prochain contrôle est un audit **en lecture seule**
du cluster cible avec un accès explicite : type de distribution, nœud Ready,
Pods système, StorageClass, Ingress et filtrage de TCP 6443 depuis l'extérieur.
Les ressources temporaires de smoke test restent une étape distincte.

Avec un kubeconfig privé pointant explicitement vers le VPS, lancer d'abord :

```bash
KUBECONFIG=/chemin/prive/kubeconfig kubectl config current-context
KUBECONFIG=/chemin/prive/kubeconfig kubectl get nodes
KUBECONFIG=/chemin/prive/kubeconfig kubectl get pods -n kube-system
KUBECONFIG=/chemin/prive/kubeconfig kubectl get storageclass,ingressclass
```

Ces lectures ne démontrent ni le DNS des Pods, ni la persistance des PVC, ni
le filtrage externe de TCP 6443. Vérifier ce dernier depuis un réseau distinct
avant toute exposition applicative. Ne pas copier le kubeconfig dans le dépôt.

Les observations ci-dessous sont historiques et ne décrivent pas nécessairement
l'état actuel du VPS.

## Décisions et état réel

- La V1 vise **Plane Community Edition** (`plane-ce`). Plane ne publie pas de
  plafond de sièges pour cette édition ; elle donne accès aux fonctionnalités
  du niveau Free. Le plan Commercial Free annonce 12 sièges par workspace.
  Voir [le comparatif](plane-editions.md).
- Le travail reste **local**. Aucun K3s, Plane ou n8n n'a été déployé par
  Project OS sur le VPS. AegisOps et les protections de l'hôte n'ont pas été
  modifiés.
- Le dernier précheck LXC en lecture seule a rendu **`BLOCKED`** :
  `net.ipv4.ip_forward=0` et `/proc/sys` est en lecture seule. Le filtrage de
  l'API Kubernetes TCP 6443 depuis Internet n'est pas encore démontré.
  Voir [le relevé de phase 1](phase-1.md).
- Une réponse du fournisseur est attendue sur le forwarding IPv4, les
  capacités réseau du LXC et la protection de TCP 6443. Ne pas lancer
  `install-k3s.yml` avant d'avoir vérifié ces points, établi le retour arrière
  et confirmé un accès de secours.

## Préparation locale disponible

- Squelette Ansible, inventaire d'exemple sans cible réelle, précheck en
  lecture seule, rôle K3s et playbooks de vérification/smoke test :
  [guide K3s](k3s-playbooks.md).
- Versions et sommes SHA-256 des charts consignées dans
  [`helm/charts.lock.yaml`](../helm/charts.lock.yaml) ; exemples de valeurs pour
  Plane Community, Commercial Free et n8n. Commercial reste une référence de
  comparaison, sans être la cible de la V1.
- Contrats de Secrets et premières procédures de sauvegarde dans
  [secrets.md](secrets.md) et [recovery.md](recovery.md). Aucun secret réel n'est
  enregistré dans les valeurs d'exemple.
- Validation statique locale et CI préparées. Les rendus Helm des trois charts
  vérifiés ne créent aucun `Secret` Kubernetes à partir des valeurs d'exemple.

## Reprendre demain

1. Lire la réponse du fournisseur et mettre à jour le diagnostic LXC. Si elle
   ne couvre pas TCP 6443, demander explicitement comment le port est filtré
   depuis Internet. Un `ss` local ne suffit pas à le prouver.
2. Terminer **localement** le chemin d'exposition HTTPS, les paramètres DNS,
   la fourniture chiffrée des Secrets et la stratégie de sauvegarde hors hôte.
   Le domaine, les certificats et la destination/rétention des sauvegardes
   restent à définir avant déploiement.
3. Examiner les ressources du rendu Plane Community sur le nœud de 12 Gio,
   puis préparer la procédure de déploiement et de retour arrière.
4. Après levée des blocages, demander une approbation explicite avant toute
   installation K3s ou modification réseau sur le VPS ; valider ensuite Pods,
   DNS, trafic inter-Pods, PVC et restauration avant les applications.

## Vérifications locales

Depuis la racine du dépôt :

```bash
./scripts/validate.sh
./scripts/validate-helm.sh
git diff --check
```

Le 2026-10-26, `validate.sh`, `validate-helm.sh` avec les archives épinglées
déjà présentes dans `/tmp`, et `git diff --check` ont réussi. La CI GitHub et
le chemin de téléchargement des charts du script Helm n'ont pas encore été
exécutés de bout en bout. Les tests Kubernetes réels, l'idempotence sur VPS,
le stockage et la restauration restent **non effectués**.
