# Choix de l'édition Plane

État au 2026-10-26 : **Community Edition retenue pour la V1** afin de garder
le code ouvert et de ne pas dépendre d'une licence commerciale. Les deux
éditions possèdent un chart publié dans le dépôt Helm de Plane. Les valeurs
d'exemple ne doivent pas être appliquées avant la préparation des Secrets et
la validation du stockage et du réseau.

| Critère | Community Edition | Commercial Edition, plan Free |
|---|---|---|
| Code et licence | Code ouvert, AGPL-3.0 ; pas de clé de licence. | Code fermé ; plan Free sans clé payante, avec système de licence Plane. |
| Sièges | Plane ne publie pas de plafond de sièges pour cette édition ; fonctionnalités du niveau Free. | 12 sièges Free par workspace annoncés par Plane ; couvre l'équipe prévue de 5–7. |
| Évolution des fonctionnalités | Pour les fonctions payantes, migration vers Commercial. | Passage aux plans payants sans changer d'édition. |
| Chart vérifié localement | `plane-ce` 1.8.5, application 1.4.2. | `plane-enterprise` 3.10.12, application 3.3.3. |
| Ressources au rendu par défaut | 7 Deployments, 4 StatefulSets, 2 Jobs. | 9 Deployments, 5 StatefulSets, 2 Jobs ; dimensionnement à contrôler sur 12 Gio. |

Les versions ci-dessus viennent de l'index `https://helm.plane.so/`. Les
archives téléchargées dans `/tmp` correspondent aux sommes SHA-256 consignées
dans `helm/charts.lock.yaml`. La documentation officielle présente la
[Community Edition](https://developers.plane.so/self-hosting/editions-and-versions)
et la [procédure Kubernetes des deux éditions](https://developers.plane.so/self-hosting/methods/kubernetes).

Le fait d'auto-héberger ne supprime pas les conditions de licence de l'édition
choisie. Community est gratuite sous AGPL-3.0, sans clé de licence et sans
plafond de sièges publié ; elle donne accès aux fonctions du niveau Free.
Commercial Free est aussi auto-hébergée, mais son offre gratuite annonce 12
sièges par workspace. Si des fonctions payantes deviennent nécessaires, il
faudra étudier une migration vers Commercial. Les deux éditions demandent la
même rigueur pour PostgreSQL, cache, broker, stockage objet, Secrets et
sauvegardes.

Les comptes de ressources viennent de `helm template` avec les valeurs par
défaut : ils décrivent le rendu, pas une consommation mesurée ni une preuve de
fonctionnement. Ces valeurs produisent des Secrets avec des exemples publics ;
elles ne doivent pas servir au déploiement.

**À définir avant déploiement :** domaine Plane et politique de sauvegarde.
Aucun mot de passe ou token ne doit être placé dans les valeurs Helm suivies par
Git. Les charts disposent
de références à des Secrets préexistants ; leurs valeurs d'exemple contiennent
aussi des identifiants publics et ne sont pas sûres pour un déploiement direct.
