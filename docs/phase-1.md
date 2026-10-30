# Phase 1 — suivi et préchecks

## État du travail

- [x] Inspecter le dépôt et préserver les changements déjà présents.
- [x] Ajouter un inventaire d'exemple sans adresse ni compte réel.
- [x] Exclure les secrets et les fichiers locaux courants de Git.
- [x] Écrire un précheck K3s en lecture seule et documenter son verdict.
- [x] Ajouter une validation statique locale.
- [x] Exécuter le précheck sur le LXC cible et archiver un résumé expurgé.
- [ ] Établir comment TCP 6443 est filtré depuis Internet, côté VM, hôte et fournisseur.
- [x] ~~Valider avec l'administrateur Proxmox les ajustements LXC nécessaires.~~
  Remplacé : le VPS est une VM KVM depuis le 2026-10-30.
- [x] Relancer le précheck sur la VM KVM (2026-10-30).

## Exécution

Depuis la racine du dépôt :

```bash
./scripts/validate.sh
ANSIBLE_CONFIG=infrastructure/ansible.cfg ansible-playbook \
  -i /chemin/prive/hosts.yml infrastructure/ansible/playbooks/prerequisites.yml
```

La validation locale requiert les outils épinglés dans
`requirements-validation.txt` (`python -m pip install -r requirements-validation.txt`)
ou leurs équivalents déjà installés. La CI exécute la même commande.

Copier `infrastructure/ansible/inventories/production/hosts.example.yml` vers
`hosts.yml` dans un emplacement privé, puis remplacer l'adresse réservée et le
compte d'exemple. Aucun secret n'est requis dans l'inventaire. La seconde commande
ouvre une connexion SSH mais n'installe rien. Les tâches `raw` ne transfèrent pas
de module Ansible ni de fichier temporaire sur le LXC. Elles n'utilisent pas sudo.
Un refus SSH ou une tâche inaccessible ne vaut pas diagnostic de compatibilité.

## Interprétation

- `BLOCKED` : un prérequis local indispensable manque, notamment systemd comme
  PID 1, les contrôleurs CPU/mémoire de cgroups v2, OverlayFS, le namespace réseau
  ou le forwarding IPv4. Identifier la cause avant toute installation.
- `NEEDS_VALIDATION` : aucun blocage de cette liste n'a été observé. Les capacités
  du processus, les règles réseau, les ports et le stockage restent à interpréter.
- `READY` : réservé à une validation pratique ultérieure de containerd, des Pods,
  du CNI, du DNS, des PVC et de la protection de TCP 6443. Le playbook ne le retourne
  jamais à lui seul.

Le diagnostic de TUN est informatif : son absence n'est pas à elle seule un blocage.
La présence d'OverlayFS dans `/proc/filesystems` ne prouve pas qu'un conteneur
pourra monter overlay. Le résultat de `ss` n'établit pas l'accessibilité depuis
Internet. Une valeur `ip_forward=0` bloque la préparation tant qu'une solution
contrôlée n'est pas décidée ; le playbook ne modifie aucun sysctl.

## Résultat sur la VM KVM — 2026-10-30

Le playbook a terminé avec 12 tâches `ok`, 0 modifiée, 0 erreur.
Verdict : **`BLOCKED`**, pour deux causes attendues sur une Ubuntu neuve :

| Observation | Résultat |
|---|---|
| Virtualisation | `kvm` |
| systemd est PID 1 | Oui |
| Contrôleurs cgroups v2 CPU et mémoire | Présents |
| OverlayFS dans `/proc/filesystems` | **Non** : module `overlay` disponible mais non chargé |
| Namespace réseau / TUN | Présents |
| Forwarding IPv4 | **Désactivé** (`0`, défaut Ubuntu) |
| `/proc/sys` | En écriture |
| TCP 6443 en écoute | Non |

Audit complémentaire en lecture seule : Ubuntu 24.04.5, noyau `6.8.0-147-generic`,
modules `br_netfilter` et `vxlan` disponibles non chargés, aucun composant
Kubernetes ni runtime de conteneurs. UFW est actif (`INPUT DROP`, seul TCP 22
autorisé, règles AegisOps) et Fail2ban est actif. Depuis un réseau externe,
TCP 6443 expire (paquets ignorés) et TCP 22 répond. Cela prouve le filtrage
**côté hôte** aujourd'hui, sans service en écoute ; le filtrage fournisseur
reste inconnu.

Les deux blocages se lèvent par une configuration versionnée et approuvée :
chargement persistant de `overlay` et `br_netfilter`, puis sysctl
`net.ipv4.ip_forward=1`. La politique UFW `INPUT DROP` peut aussi bloquer le
trafic des Pods vers l'hôte (API, DNS) ; l'éventuelle autorisation des plages
Pods/Services doit être décidée avec la politique AegisOps.

## Incertitudes LXC à lever (historique)

*Le VPS est une VM KVM depuis le 2026-10-30 : les limites propres au conteneur
ne s'appliquent plus. Le fonctionnement de containerd, du CNI, du DNS et des PVC
reste à prouver.*

Le comportement réel de containerd, des montages overlay, de Flannel, du DNS
interne et des PVC n'est pas prouvé. La visibilité des modules `vxlan` et
`br_netfilter` dans LXC n'indique pas à elle seule leur disponibilité côté hôte.
Si une adaptation Proxmox ou fournisseur est nécessaire, documenter le changement
minimal, son impact réseau et son retour arrière avant intervention. Ne pas
convertir le conteneur en mode privilégié ni désactiver son confinement par défaut.

## Résultat sur le LXC cible — 2026-10-26 (historique)

*Relevé de l'ancien conteneur LXC : il ne vaut plus pour la VM KVM et doit être
refait.*

Le playbook a terminé avec 11 tâches `ok`, 0 tâche modifiée et 0 erreur.
Verdict : **`BLOCKED`** pour l'installation de K3s dans l'état observé.

| Observation | Résultat |
|---|---|
| systemd est PID 1 | Oui |
| Contrôleurs cgroups v2 CPU et mémoire | Présents |
| OverlayFS listé par le noyau | Oui, montage réel non testé |
| Namespace réseau | Présent, création et trafic Pod non testés |
| Forwarding IPv4 | Désactivé (`0`) |
| `/proc/sys` | Monté en lecture seule |
| TUN | Absent, non classé comme blocage isolé |
| TCP 6443 en écoute dans le LXC | Non lors du précheck ; filtrage externe inconnu |

Les capacités lues sont celles du processus de diagnostic non-root : elles ne
permettent pas de conclure sur les capacités accordées à containerd ou à K3s.
Le précheck ne démontre ni le fonctionnement de containerd/CNI/PVC, ni le filtrage
de TCP 6443 depuis Internet. Avant la phase 2, il faut déterminer avec accès
administratif Proxmox ou fournisseur comment activer le forwarding nécessaire
sans élargir les privilèges LXC de façon arbitraire, puis vérifier la protection
réseau externe de l'API et prévoir un retour arrière.
