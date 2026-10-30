# Reprise du travail — 2026-10-26

## 2026-10-31 — NodePorts fermés, DNS et TLS

NodePorts limités à `127.0.0.1` et appliqués : depuis l'extérieur, 31750 et
31566 expirent, 80/443 répondent toujours. Seconde exécution du rôle :
`changed=0` (idempotence vérifiée). DNS provisoire : sslip.io. cert-manager
`v1.21.3` et les ClusterIssuers Let's Encrypt sont préparés ; voir
[tls.md](tls.md). **Non encore appliqués.**

## 2026-10-31 — Redémarrage et Ingress

Après redémarrage de la VM, K3s, les modules et le sysctl sont revenus seuls ;
`verify-k3s.yml` réussit. Le rôle a ensuite activé Traefik 3.7.13 et ServiceLB
de K3s et ouvert 80/443 dans UFW (`changed=3`). Depuis l'extérieur : 22, 80
et 443 répondent (HTTP 404 sans route, attendu) ; 6443 et 10250 expirent.
Les NodePorts automatiques de Traefik répondaient aussi depuis Internet
(contournement d'UFW par DNAT) : le rôle les limite désormais à `127.0.0.1`,
**à appliquer et revérifier**. Domaine et TLS restent à choisir.

## 2026-10-31 — K3s installé sur la VM KVM

`install-k3s.yml` a terminé sans erreur (`changed=9`) : modules `overlay` et
`br_netfilter`, sysctl `ip_forward`, deux règles UFW (10.42/16, 10.43/16),
binaire `v1.37.1+k3s1`, configuration et unité systemd. `verify-k3s.yml` : nœud
`Ready`, coredns, local-path-provisioner et metrics-server `Running`,
StorageClass `local-path`. Depuis un réseau externe, TCP 6443 et 10250
expirent alors que K3s y écoute : le filtrage côté hôte est démontré.

Corrections apportées à `verify-k3s.yml` : attente de l'état `Ready` (le nœud
met une à deux minutes à s'enregistrer) et lecture de la clé JSON `['items']`
au lieu de `.items`, que Jinja résout comme la méthode `dict.items`.

`smoke-k3s.yml` a réussi (`ok=15`, `failed=0`) : DNS interne, HTTP entre Pods
via un Service, marqueur sur PVC `local-path` relu après redémarrage du Pod.
Depuis un Pod, la résolution DNS externe et le HTTP sortant fonctionnent : la
politique UFW `FORWARD DROP` ne bloque pas le trafic des Pods (règles Flannel).
Le namespace `projectos-smoke` est laissé en place pour inspection. Correction :
dans une liste YAML, `- -` est une liste imbriquée contenant `null` ; l'argument
stdin de kubectl doit être écrit `'-'`.

**Non effectués :** seconde exécution du rôle (idempotence), redémarrage de la
VM, sauvegarde du token et du datastore, restauration.

## Relevé du 2026-10-30 — VM KVM vérifiée

Précheck et audit exécutés en lecture seule : VM `kvm`, Ubuntu 24.04.5, aucun
Kubernetes installé, UFW `INPUT DROP` avec TCP 22 seul, TCP 6443 filtré depuis
l'extérieur. Verdict `BLOCKED` dû à `ip_forward=0` et au module `overlay` non
chargé. Détails dans [le relevé de phase 1](phase-1.md). Le rôle K3s cible
désormais Ubuntu 24.04.

## Mise à jour du 2026-10-30 — passage en VM KVM

Le VPS a été migré d'un conteneur LXC vers une **VM KVM** (information de
l'administrateur, pas encore vérifiée depuis ce dépôt). Dans une VM, le noyau
appartient à l'invité : `net.ipv4.ip_forward`, les modules `overlay`,
`br_netfilter` et `vxlan`, ainsi que `/dev/net/tun`, relèvent de la
configuration de la VM et non plus des limites du conteneur. Le verdict
`BLOCKED` du 2026-10-26 (`ip_forward=0`, `/proc/sys` en lecture seule) est donc
**probablement levé, mais non démontré**.

Conséquences :

- Relancer `prerequisites.yml` sur la VM et remplacer le relevé de phase 1.
  Le précheck affiche désormais le type de virtualisation détecté.
- Re-mesurer noyau, CPU, RAM et disque : les ressources ont pu changer.
- Établir si le cluster annoncé le 2026-10-28 existe encore sur la nouvelle VM,
  et sous quelle forme, avant d'utiliser `install-k3s.yml`.
- Prouver à nouveau le filtrage externe de TCP 6443 : la migration a pu changer
  l'adresse, les règles du fournisseur ou celles d'AegisOps.
- `ip_forward=0` est la valeur par défaut d'Ubuntu. Le rôle K3s exige `1` avant
  l'installation ; activer ce sysctl sera une étape distincte, versionnée et
  approuvée.

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
