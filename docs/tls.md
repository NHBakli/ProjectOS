# DNS et TLS — V1

## Choix provisoire : sslip.io

Aucun domaine n'est encore acheté. La V1 utilise [sslip.io](https://sslip.io),
qui résout `<nom>.<a-b-c-d>.sslip.io` vers l'adresse `a.b.c.d` sans
configuration. Noms prévus : `plane.<base>` et `n8n.<base>`, où `<base>` est
`<ip-avec-tirets>.sslip.io`. Ce domaine contient l'IP publique : il reste dans
le fichier privé `~/.config/projectos/platform.yml`
(modèle : `inventories/production/platform.example.yml`) et n'est pas versionné.

Limites : l'IP apparaît dans les URL ; les limites de débit Let's Encrypt
peuvent être partagées avec d'autres utilisateurs de sslip.io ; changer plus
tard de domaine imposera de mettre à jour les URL de Plane, n8n et des webhooks
GitHub. Passer à un domaine acheté ou à DuckDNS avant l'arrivée de l'équipe.

## Certificats

cert-manager `v1.21.3` est déployé par le contrôleur Helm intégré à K3s
(`kubernetes/cert-manager/helmchart.yaml`) ; ses CRD sont conservées en cas de
désinstallation. Deux ClusterIssuers HTTP-01 via Traefik :
`letsencrypt-staging` pour les essais, `letsencrypt-prod` pour les services.
Aucun e-mail n'est enregistré. Les clés de compte ACME et les certificats sont
des Secrets du cluster ; ils peuvent être réémis et ne sont pas critiques pour
la restauration.

Une application obtient son certificat avec l'annotation
`cert-manager.io/cluster-issuer: letsencrypt-prod` sur son Ingress et une
section `tls` nommant le Secret à créer.

## Commandes

```bash
export ANSIBLE_CONFIG=infrastructure/ansible.cfg
cp infrastructure/ansible/inventories/production/platform.example.yml ~/.config/projectos/platform.yml
# Remplacer 192-0-2-10 par l'IP du VPS avec des tirets.

ansible-playbook -i ~/.config/projectos/hosts.yml -e cert_manager_deploy_approved=true \
  infrastructure/ansible/playbooks/deploy-cert-manager.yml

ansible-playbook -i ~/.config/projectos/hosts.yml -e k3s_smoke_tests_approved=true \
  -e @$HOME/.config/projectos/platform.yml \
  infrastructure/ansible/playbooks/smoke-tls.yml
```

Le test TLS publie la page du smoke test sur `smoke.<base>` avec un certificat
**staging**, vérifie le défi HTTP-01 et la réponse HTTPS. Il est supprimé avec
le namespace par `cleanup-smoke-k3s.yml`.

## Retour arrière

Supprimer le HelmChart (`k3s kubectl -n kube-system delete helmchart
cert-manager`) désinstalle cert-manager ; les CRD et les certificats déjà émis
restent. Ne pas supprimer les CRD tant que des Certificates existent.
