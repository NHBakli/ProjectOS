# État du projet

Mis à jour le 2026-10-31.

## Le serveur

| | |
|---|---|
| Type | VM KVM (avant : conteneur LXC) |
| Système | Ubuntu 24.04.5, noyau 6.8 |
| Ressources | 9 vCPU, ~11 Gio RAM, ~123 Go libres |
| Pare-feu | UFW actif (géré par AegisOps) + Fail2ban |
| Ports ouverts sur Internet | 22, 80, 443 uniquement |

## Ce qui marche

- ✅ K3s `v1.37.1+k3s1` installé, nœud `Ready`
- ✅ Redémarre seul après un reboot de la VM
- ✅ Le rôle Ansible est idempotent : une 2ᵉ exécution ne change rien
- ✅ DNS interne, trafic entre Pods, volumes persistants, accès Internet des Pods
- ✅ API 6443, kubelet 10250 et NodePorts fermés depuis Internet
- ✅ Traefik + cert-manager : certificat Let's Encrypt obtenu

## Ce qui reste

1. Déployer Plane → [04-plane.md](04-plane.md)
2. Mettre en place et **tester** les sauvegardes → [sauvegardes.md](sauvegardes.md)
3. Déployer n8n → [05-n8n.md](05-n8n.md)
4. Passer à un vrai domaine avant d'inviter l'équipe → [03-https.md](03-https.md)

## Journal

| Date | Événement |
|---|---|
| 2026-10-26 | Test des prérequis sur l'ancien conteneur LXC : bloqué (`ip_forward`, `/proc/sys` en lecture seule). |
| 2026-10-30 | Le VPS passe en VM KVM. Test des prérequis : seuls `ip_forward` et le module `overlay` manquent. |
| 2026-10-31 | K3s installé. Tests réseau et stockage réussis. |
| 2026-10-31 | Reboot de la VM : tout revient seul. |
| 2026-10-31 | Traefik activé, ports 80/443 ouverts. |
| 2026-10-31 | Fuite trouvée : les NodePorts contournaient UFW. Corrigée (limités à `127.0.0.1`). |
| 2026-10-31 | cert-manager installé, test HTTPS réussi avec sslip.io. |
| 2026-10-31 | Déploiement Plane préparé, pas encore lancé. |

## Bugs corrigés en route

Utile si tu écris de nouveaux playbooks :

- `(... | from_json).items` désigne la méthode Python, pas la clé JSON. Écrire `['items']`.
- En YAML, `- -` est une liste imbriquée. Pour passer l'argument `-`, écrire `- '-'`.
- Un NodePort ou un `hostPort` **contourne UFW**. Ne pas en créer.
