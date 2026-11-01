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
- ✅ Plane v1.4.2 en ligne en HTTPS, compte admin créé
- ✅ Bases de Plane (PostgreSQL, Redis, RabbitMQ, MinIO) fermées depuis Internet
- ✅ Sauvegarde Plane chiffrée vers le poste, restauration testée
- ✅ n8n v2.44.5 en ligne en HTTPS, compte propriétaire créé
- ✅ Sauvegarde n8n chiffrée vers le poste, restauration testée (clé vérifiée)

## Ce qui reste

1. Workflow Plane → GitHub : mettre à jour le nœud « Contrôle projet GitHub » dans n8n → [06-plane-github.md](06-plane-github.md)
2. Copier les sauvegardes hors du poste, puis les automatiser → [sauvegardes.md](sauvegardes.md)
3. Passer à un vrai domaine avant d'inviter l'équipe → [03-https.md](03-https.md)

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
| 2026-10-31 | Plane déployé : 11 composants prêts, certificat valide jusqu'au 2027-01-28 (renouvelé automatiquement). Compte admin créé. Le serveur utilise ~3,2 Gio de RAM. |
| 2026-10-31 | n8n déployé, certificat valide, compte propriétaire créé. Sauvegarde n8n et test de restauration préparés. |
| 2026-10-31 | Fichier Vault n8n recréé depuis le Secret du cluster (mot de passe différent à la création). Test de restauration n8n réussi. |
| 2026-10-31 | Sens choisi : Plane → GitHub, routage par label vers les dépôts de Flowly-PBS. Workflow écrit d'après le code de Plane v1.4.2, testé dans n8n 2.44.5 local (7 cas, 0 échec). Pas encore installé. |
| 2026-10-31 | Workflow installé. Test réel : issue `Frontend#47` créée avec le lien Plane, mais **pas ajoutée** au projet GitHub « Frontend Team » (cause à lire dans l'exécution n8n). |
| 2026-10-31 | Traduction FR → EN par DeepL API Free ajoutée au workflow (original FR replié). Testée en local (8 cas, 0 échec). Pas encore installée. |
| 2026-11-01 | Workflow avec traduction installé. Test réel réussi : `Frontend#48` et `Backend#34` en anglais, original FR, lien Plane, dans leurs projets. Fausse erreur « already exists in this project » (auto-add GitHub) corrigée dans le workflow. |
| 2026-10-31 | 1ʳᵉ sauvegarde Plane rapatriée (chiffrée). Test de restauration réussi : données identiques (2 utilisateurs, 1 projet, 7 tickets). Aucun fichier joint à ce moment-là. |

## Bugs corrigés en route

Utile si tu écris de nouveaux playbooks :

- `(... | from_json).items` désigne la méthode Python, pas la clé JSON. Écrire `['items']`.
- En YAML, `- -` est une liste imbriquée. Pour passer l'argument `-`, écrire `- '-'`.
- Un NodePort ou un `hostPort` **contourne UFW**. Ne pas en créer.
- Le CLI de n8n écrit ses journaux sur la sortie standard : ne jamais compter ses lignes. Lire la base en lecture seule (`node:sqlite`).
- Plusieurs fichiers Vault doivent partager le même mot de passe, sinon un playbook qui les charge ensemble échoue. Le script de génération le vérifie maintenant.
