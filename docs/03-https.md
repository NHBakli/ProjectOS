# 3. Activer HTTPS

## Le domaine

On n'a pas encore acheté de domaine. On utilise **sslip.io**, gratuit et sans configuration :
`plane.1-2-3-4.sslip.io` pointe automatiquement vers l'IP `1.2.3.4`.

| | |
|---|---|
| ✅ | Marche immédiatement, certificat Let's Encrypt valide |
| ❌ | L'IP apparaît dans l'adresse |
| ❌ | Limites Let's Encrypt partagées avec d'autres utilisateurs |

**Avant d'inviter l'équipe :** passer à un vrai domaine (~10 €/an) ou à DuckDNS (gratuit).

Le domaine contient l'IP : il reste dans `~/.config/projectos/platform.yml`, jamais dans Git.

## Comment ça marche

1. **Traefik** reçoit le trafic sur les ports 80 et 443.
2. **cert-manager** demande les certificats à Let's Encrypt et les renouvelle tout seul.
3. Chaque application déclare son nom d'hôte et reçoit son certificat.

Deux émetteurs existent :

| Nom | Usage |
|---|---|
| `letsencrypt-staging` | Tests (certificat non reconnu par les navigateurs) |
| `letsencrypt-prod` | Vrais services |

## Étapes

**1. Installer cert-manager**

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml -e cert_manager_deploy_approved=true \
  infrastructure/ansible/playbooks/deploy-cert-manager.yml
```

**Attendu :** `failed=0`.

**2. Tester** (`smoke-k3s.yml` doit avoir été lancé avant : il crée la page de test)

```bash
ansible-playbook -i ~/.config/projectos/hosts.yml -e k3s_smoke_tests_approved=true \
  -e @$HOME/.config/projectos/platform.yml \
  infrastructure/ansible/playbooks/smoke-tls.yml
```

**Attendu :** `Défi HTTP-01 réussi et page servie en HTTPS`.

## En cas de problème

| Symptôme | Action |
|---|---|
| Certificat bloqué | `sudo k3s kubectl describe certificate -A` sur le VPS |
| Erreur de limite Let's Encrypt | Attendre, ou passer à un vrai domaine |

## Retour arrière

```bash
sudo k3s kubectl -n kube-system delete helmchart cert-manager
```

Les certificats déjà émis restent en place.
