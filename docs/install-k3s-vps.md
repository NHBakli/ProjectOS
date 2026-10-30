# Installer K3s sur la VM KVM — procédure opérateur

Procédure à exécuter **depuis le poste local**, à la racine du dépôt. Le rôle
`k3s` applique les prérequis de l'hôte puis installe K3s. Il ne touche ni à SSH,
ni aux comptes, ni à Fail2ban, et ne réinitialise jamais UFW/iptables.

Ce que le rôle modifie sur le VPS :

| Élément | Changement |
|---|---|
| `/etc/modules-load.d/projectos-k3s.conf` | Charge `overlay` et `br_netfilter` au démarrage (et immédiatement). |
| `/etc/sysctl.d/90-projectos-k3s.conf` | `net.ipv4.ip_forward=1`, `net.bridge.bridge-nf-call-iptables=1`. |
| UFW | Deux règles `allow from 10.42.0.0/16` et `10.43.0.0/16` (Pods/Services vers l'hôte), commentées `Project OS K3s`, et `allow 80,443/tcp` commentées `Project OS ingress`. **6443 reste fermé à Internet.** |
| `/usr/local/bin/k3s` | Binaire `v1.37.1+k3s1` vérifié par SHA-256. |
| `/etc/rancher/k3s/config.yaml` | Configuration `0600`, Secrets chiffrés au repos, Traefik et ServiceLB de K3s activés pour l'Ingress. |
| `/etc/systemd/system/k3s.service` | Unité systemd, activée et démarrée. |

K3s ajoute ensuite ses propres règles iptables (Flannel, kube-proxy,
network policies).

## 0. Préparer les fichiers privés (hors du dépôt)

```bash
mkdir -p ~/.config/projectos && chmod 700 ~/.config/projectos
cp infrastructure/ansible/inventories/production/hosts.example.yml ~/.config/projectos/hosts.yml
cp infrastructure/ansible/inventories/production/k3s-approval.example.yml ~/.config/projectos/k3s-approval.yml
```

Dans `~/.config/projectos/hosts.yml`, renseigner l'IP réelle, le compte
administrateur et `ansible_ssh_private_key_file`. Dans
`~/.config/projectos/k3s-approval.yml`, remplacer `192.0.2.10` par l'IP de
l'interface `ens18` de la VM.

## 1. Outils et validation locale

```bash
ansible-galaxy collection install -r infrastructure/ansible/requirements.yml \
  -p infrastructure/ansible/collections
./scripts/validate.sh
export ANSIBLE_CONFIG=infrastructure/ansible.cfg
```

## 2. Garder un accès de secours

Ouvrir une **seconde session SSH** sur le VPS et la laisser ouverte pendant
l'installation, et vérifier l'accès console du fournisseur. Le rôle ne touche pas
au port 22, mais K3s ajoute des règles réseau.

## 3. Précheck (lecture seule)

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml \
  infrastructure/ansible/playbooks/prerequisites.yml
```

`BLOCKED` est attendu à ce stade (`ip_forward=0`, `overlay` non chargé) : le rôle
corrige ces deux points à l'étape suivante.

## 4. Installation

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml \
  -e @$HOME/.config/projectos/k3s-approval.yml \
  infrastructure/ansible/playbooks/install-k3s.yml
```

Puis **relancer exactement la même commande** : la seconde exécution doit finir
avec `changed=0` (test d'idempotence).

## 5. Vérification

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml \
  infrastructure/ansible/playbooks/verify-k3s.yml
```

Attendu : nœud `Ready`, Pods `kube-system` en `Running` (coredns,
local-path-provisioner, metrics-server), StorageClass `local-path`.

Contrôle externe depuis le poste local (doit **expirer**) :

```bash
nc -vz -w5 <IP_VPS> 6443
```

## 6. Smoke test (crée des ressources temporaires)

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml \
  -e k3s_smoke_tests_approved=true \
  infrastructure/ansible/playbooks/smoke-k3s.yml
```

Vérifie le DNS, le HTTP entre Pods via un Service et la persistance d'un PVC
après redémarrage du Pod. Nettoyage (supprime le PVC de test seulement) :

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml \
  -e k3s_smoke_cleanup_approved=true \
  infrastructure/ansible/playbooks/cleanup-smoke-k3s.yml
```

## 7. Accès kubectl depuis le poste (tunnel SSH)

L'API n'est pas joignable depuis Internet : passer par un tunnel.

```bash
ssh -i <CLE> <ADMIN>@<IP_VPS> 'sudo cat /etc/rancher/k3s/k3s.yaml' > ~/.kube/projectos.yaml
chmod 600 ~/.kube/projectos.yaml
sed -i 's#server: https://.*:6443#server: https://127.0.0.1:6443#' ~/.kube/projectos.yaml

# Terminal dédié, laissé ouvert :
ssh -i <CLE> -N -L 6443:<IP_VPS>:6443 <ADMIN>@<IP_VPS>

KUBECONFIG=~/.kube/projectos.yaml kubectl get nodes
```

Le kubeconfig contient des identifiants administrateur : ne jamais l'afficher,
le committer ni le partager.

## Exposition HTTP/HTTPS

Traefik reçoit le trafic des ports 80/443 via ServiceLB (`svclb-traefik`).
Ces ports sont publiés par DNAT dans iptables : le trafic passe par la chaîne
FORWARD et **contourne les règles INPUT d'UFW**. Il en va de même pour tout
Service `NodePort` ou `hostPort`. Constat du 2026-10-31 : les NodePorts
automatiques du Service Traefik répondaient depuis Internet. Le rôle limite
donc les NodePorts à `127.0.0.1` (`kube-proxy-arg: nodeport-addresses`) ;
ServiceLB transmet à la ClusterIP de Traefik et n'en dépend pas. Règle du
projet : n'exposer que Traefik ; aucun Service `LoadBalancer` ou `hostPort`
supplémentaire sans revue. Contrôler régulièrement depuis l'extérieur que seuls 22, 80 et 443
répondent.

Pour appliquer le changement sur un K3s déjà installé, relancer la commande de
l'étape 4 : la configuration modifiée redémarre K3s (les Pods continuent de
tourner), puis K3s déploie Traefik dans `kube-system`.

## Retour arrière

Arrêter K3s sans supprimer ses données :

```bash
sudo systemctl disable --now k3s
```

Retirer les changements de l'hôte, uniquement si K3s est abandonné :

```bash
sudo ufw delete allow from 10.42.0.0/16
sudo ufw delete allow from 10.43.0.0/16
sudo ufw delete allow 80/tcp
sudo ufw delete allow 443/tcp
sudo rm /etc/sysctl.d/90-projectos-k3s.conf /etc/modules-load.d/projectos-k3s.conf
```

Les valeurs sysctl actives reviennent au défaut au prochain redémarrage. Arrêter
le service ne retire pas forcément les règles iptables posées par K3s : un
redémarrage de la VM les efface, car elles ne sont pas persistées. **Ne jamais**
lancer `ufw reset`, `iptables -F` ni supprimer `/var/lib/rancher/k3s` par réflexe.
