# Playbooks K3s — préparation, installation, vérification

Ces playbooks sont préparés localement. Le VPS est passé de LXC à une **VM KVM**
le 2026-10-30 : le blocage du dernier précheck (`ip_forward=0`, `/proc/sys` en
lecture seule, relevés sur le LXC) doit être réévalué en relançant le précheck.
**L'installation reste bloquée** tant que le filtrage de TCP 6443 n'est pas
prouvé, qu'un éventuel cluster existant n'est pas identifié et qu'un plan de
retour arrière et un accès de secours ne sont pas confirmés.

## Fichiers et choix

- `prerequisites.yml` : lecture seule, sans sudo ni transfert de module.
- `install-k3s.yml` et `roles/k3s` : installation single-node idempotente après
  validations explicites. Aucune modification de SSH, de Fail2ban ou du pare-feu.
- `verify-k3s.yml` : lit l'état du service, du nœud, des Pods système et des
  StorageClasses ; ne crée pas de Pod ni de PVC.
- `smoke-k3s.yml` : essai pratique dans `projectos-smoke` avec deux Pods réseau,
  un Service, un PVC de 64 MiB et un Deployment ; il exige
  `k3s_smoke_tests_approved: true`.
- `cleanup-smoke-k3s.yml` : suppression du namespace de test et de son PVC,
  uniquement après `k3s_smoke_cleanup_approved: true` et vérification du label.

Le rôle utilise le binaire amd64 **v1.37.1+k3s1** avec le SHA-256 publié dans
la [release officielle](https://github.com/k3s-io/k3s/releases/tag/v1.37.1%2Bk3s1).
Il ne lance pas d'installateur distant. La version est un point de départ épinglé
à revoir avant déploiement, selon la date et la compatibilité confirmée.

La configuration est dans `/etc/rancher/k3s/config.yaml` (mode `0600`) et le
kubeconfig K3s est demandé en mode `0600`. Le chiffrement des Secrets au repos
est activé. Traefik et ServiceLB sont désactivés tant que l'exposition HTTPS
n'est pas conçue. Le backend Flannel et l'adresse d'écoute de l'API doivent être
choisis explicitement après la validation réseau. Le simple fait de choisir
`host-gw` ne garantit pas à lui seul le réseau des Pods.

Sur la VM KVM, le rôle prépare aussi l'hôte : modules `overlay` et
`br_netfilter`, sysctl `ip_forward`, et deux règles UFW pour les plages Pods et
Services. Voir [la procédure opérateur](install-k3s-vps.md).

## Verrous avant installation

Les variables suivantes valent `false` ou sont vides par défaut :

| Variable | Preuve attendue |
|---|---|
| `k3s_install_approved` | Autorisation d'appliquer les changements sur le VPS. |
| `k3s_host_compatibility_verified` | Précheck relancé sur la VM KVM et prérequis de l'hôte vérifiés avant l'essai K3s. |
| `k3s_api_protection_verified` | Règle de filtrage active et vérifiée avant le démarrage de K3s. |
| `k3s_api_protection_evidence` | Note non secrète sur la règle et sa vérification. |
| `k3s_flannel_backend` | Choix validé parmi `vxlan`, `host-gw`, `wireguard-native`. |
| `k3s_api_bind_address` | Adresse locale ou privée étudiée pour ce nœud ; pas d'adresse wildcard. |

Le rôle refuse aussi d'agir si le forwarding IPv4 est encore à `0`, si un K3s
non géré par Project OS existe, si TCP 6443 est déjà utilisé par un autre service
ou si l'hôte n'est pas Ubuntu 24.04 sur amd64. Un binaire différent de la version
épinglée demande `k3s_upgrade_approved: true` après sauvegarde et revue de la
mise à niveau. Ces variables sont des verrous opératoires : elles ne remplacent
pas les vérifications réseau et les tests pratiques.

## Commandes locales

Depuis la racine du dépôt :

```bash
./scripts/validate.sh
ANSIBLE_CONFIG=infrastructure/ansible.cfg ansible-playbook \
  --syntax-check infrastructure/ansible/playbooks/install-k3s.yml
```

Une fois tous les prérequis démontrés, utiliser un inventaire et des variables
privés hors Git pour l'installation contrôlée :

```bash
ANSIBLE_CONFIG=infrastructure/ansible.cfg ansible-playbook \
  -i /chemin/prive/hosts.yml \
  -e @/chemin/prive/k3s-approval.yml \
  infrastructure/ansible/playbooks/install-k3s.yml

ANSIBLE_CONFIG=infrastructure/ansible.cfg ansible-playbook \
  -i /chemin/prive/hosts.yml \
  infrastructure/ansible/playbooks/verify-k3s.yml
```

Après validation du nœud et avec autorisation distincte, exécuter les essais
pratiques. Le nettoyage efface le PVC **de ce test seulement** et reste séparé :

```bash
ANSIBLE_CONFIG=infrastructure/ansible.cfg ansible-playbook \
  -i /chemin/prive/hosts.yml \
  -e k3s_smoke_tests_approved=true \
  infrastructure/ansible/playbooks/smoke-k3s.yml

ANSIBLE_CONFIG=infrastructure/ansible.cfg ansible-playbook \
  -i /chemin/prive/hosts.yml \
  -e k3s_smoke_cleanup_approved=true \
  infrastructure/ansible/playbooks/cleanup-smoke-k3s.yml
```

La première exécution doit être surveillée. Une seconde exécution contrôlée
doit finir sans changement inattendu. Le rôle conserve des copies de l'ancien
binaire et des anciens fichiers de configuration lors de changements, mais cela
ne constitue pas une sauvegarde des données K3s.

## Vérifications et retour arrière

Après installation, vérifier l'API depuis la VM et depuis un réseau externe,
le nœud `Ready`, CoreDNS, le trafic inter-Pods, les PVC et un redémarrage.
Les essais de trafic et de PVC créent des ressources temporaires : ils seront
exécutés comme étape distincte et approuvée. Le smoke test vérifie la résolution
DNS, HTTP entre Pods via un Service et la lecture d'un fichier sur PVC après
redémarrage de son Pod. Il laisse ses ressources en place pour inspection.
Le nettoyage supprime le PVC de test : il doit faire l'objet d'une autorisation
distincte. Ce test ne remplace pas une restauration de volume ou de base ; les
deux seront exigées avant les applications réelles.

Les manifests ont été analysés localement comme YAML. Le `kubectl --dry-run=client`
local n'a pas pu fonctionner sans découverte de l'API Kubernetes ; le contrôle
des schémas et l'essai sur cluster restent à faire quand un environnement isolé
sera disponible. Aucun résultat de ce test n'est revendiqué pour le VPS actuel.

En cas d'échec, relever les journaux K3s et la configuration du réseau avant
toute action. Pour un premier déploiement, arrêter et désactiver le service K3s
peut empêcher de nouveaux changements, mais ne garantit pas que ses règles
réseau ont été retirées. Ne jamais réinitialiser iptables/nftables/UFW ni
supprimer `/var/lib/rancher/k3s` par réflexe. Un retour de version exige une
sauvegarde exploitable du datastore, du token serveur et, avec le chiffrement
activé, des clés nécessaires à la lecture des Secrets. Définir et valider la
procédure de restauration avant d'héberger des données importantes.
