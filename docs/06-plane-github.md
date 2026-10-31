# 6. Workflow Plane → GitHub

Un ticket Plane avec un label d'équipe crée une issue dans le bon dépôt de l'organisation **Flowly-PBS**, et l'ajoute au bon projet GitHub.

| Label Plane | Dépôt GitHub | Projet GitHub |
|---|---|---|
| `frontend` | `Frontend` | 2 « Frontend Team » |
| `backend` | `Backend` | 1 « Flowly team back » |
| `mobile` | `Mobile` | 3 « Mobile Team » |
| `devops` | `DevOps` (à créer) | 5 « DevOps Team » |

Fichier à importer : [`n8n/workflows/plane-vers-github.json`](../n8n/workflows/plane-vers-github.json).

## Comment ça marche

1. Plane envoie un webhook à n8n quand un ticket est créé ou que ses labels changent.
2. n8n vérifie la signature (secret partagé avec Plane). Sinon, l'appel est rejeté.
3. Pour chaque label d'équipe, n8n regarde les liens du ticket Plane. Si un lien vers une issue de ce dépôt existe déjà, il ne fait rien : **pas de doublon**.
4. Sinon : création de l'issue, lien ajouté dans le ticket Plane, ajout au projet GitHub.

Le label Plane ne tient pas compte des majuscules. Un ticket avec deux labels (`frontend` + `backend`) crée une issue dans chaque dépôt, et chacune est ajoutée à son projet GitHub.

## Étapes

### Côté GitHub

**1. Créer le dépôt DevOps** (fait le 2026-10-31)

```bash
gh repo create Flowly-PBS/DevOps --private
```

Pas besoin de labels dans GitHub : c'est le label **Plane** qui choisit le dépôt.

**2. Créer le token GitHub**

GitHub → photo de profil → **Settings** → **Developer settings** → **Fine-grained tokens** → **Generate new token**.

| Champ | Valeur |
|---|---|
| Resource owner | `Flowly-PBS` |
| Expiration | 90 jours (note la date pour le renouveler) |
| Repository access | Only select : `Frontend`, `Backend`, `Mobile`, `DevOps` |
| Repository permissions | **Issues** : Read and write |
| Organization permissions | **Projects** : Read and write |

Copie le token. Ne le colle nulle part ailleurs que dans n8n (étape 6).

Si l'organisation demande une approbation : **Flowly-PBS** → **Settings** → **Personal access tokens** → **Pending requests** → approuver.

### Côté Plane

**3. Préparer le projet**

1. Utilise un projet Plane unique pour Flowly (crée-le s'il n'existe pas).
2. Dans ses réglages, crée les labels `frontend`, `backend`, `mobile`, `devops`.
3. Ouvre le projet. Note dans l'adresse :
   - le **slug** de l'espace de travail : juste après le domaine ;
   - l'**ID du projet** : après `/projects/`.

**4. Créer la clé API Plane**

Réglages de ton profil → **API tokens** → nouveau token. Copie-le.

### Côté n8n

**5. Importer le workflow**

n8n → **Create workflow** → menu `…` → **Import from File** → `n8n/workflows/plane-vers-github.json`.

**6. Créer les deux identifiants** (type **Header Auth**)

| Nom dans n8n | Name | Value |
|---|---|---|
| `Plane API` | `X-Api-Key` | la clé Plane (étape 4) |
| `GitHub token` | `Authorization` | `Bearer ` suivi du token GitHub (étape 2) |

Choisis-les dans les nœuds :

| Nœud | Identifiant |
|---|---|
| Liens du ticket Plane, Lien dans Plane | `Plane API` |
| Créer issue GitHub, Ajouter au projet GitHub | `GitHub token` |

**7. Adapter le nœud « Équipes à traiter »**

En haut du code, remplace :

- `https://plane.TON-DOMAINE` par l'adresse de Plane ;
- `ID-DU-PROJET-PLANE` par l'ID du projet (étape 3).

**8. Publier et copier l'URL**

1. Ouvre le nœud **Webhook Plane** → onglet **Production URL** → copie l'URL.
2. Enregistre, puis **Publish**.

### Relier Plane à n8n

**9. Créer le webhook dans Plane**

Réglages de l'espace de travail → **Webhooks** → **Add webhook** :

- URL : l'URL de production (étape 8) ;
- événements : **Individual events** → coche seulement **Work items** (issues).

Plane affiche un **secret** une seule fois : copie-le.

**10. Coller le secret dans n8n**

Nœud **Signature HMAC** → champ **Secret** → remplace `COLLER_ICI_LE_SECRET_DU_WEBHOOK_PLANE`. Enregistre, puis **Publish**.

## Tester

1. Dans le projet Plane, crée un ticket « Test n8n » avec le label `frontend`.
2. Attends 10 secondes.

**Attendu :**

- une issue « Test n8n » dans `Flowly-PBS/Frontend`, avec le lien du ticket Plane ;
- l'issue apparaît dans le projet GitHub « Frontend Team » ;
- le ticket Plane a un lien `GitHub Flowly-PBS/Frontend#…` ;
- n8n → **Executions** : succès.

3. Ajoute le label `backend` au même ticket. **Attendu :** une issue dans `Backend`, aucune nouvelle dans `Frontend`.
4. Supprime ensuite les issues de test dans GitHub et le ticket dans Plane.

Colle-moi le résultat (ou l'erreur de n8n), sans token ni secret.

## En cas de problème

| Symptôme | Action |
|---|---|
| Aucune exécution dans n8n | Plane n'arrive pas à joindre n8n. Sur le VPS : `sudo k3s kubectl -n plane logs deploy/plane-app-worker-wl --since=15m \| grep -i webhook` |
| Exécution arrêtée sur **Rejeter** | Secret différent entre Plane et le nœud **Signature HMAC** |
| Exécution réussie mais rien de créé | Label absent ou mal écrit, ou mauvais ID de projet dans « Équipes à traiter » |
| 401 ou 403 sur un nœud GitHub | Token expiré, mauvaises permissions, ou approbation de l'organisation en attente |
| 401 ou 404 sur un nœud Plane | Clé API Plane, slug ou ID de projet incorrect |
| Erreur sur **Contrôle projet GitHub** | Le token n'a pas la permission **Projects** de l'organisation |

Une création ratée n'est pas retentée. Corrige la cause, puis retire et remets le label dans Plane.

## Limites connues

- **Sens unique, création seulement.** Modifier ou fermer le ticket Plane ne change pas l'issue. Retirer un label ne supprime rien.
- Un label ajouté dans la même seconde que la création peut, rarement, créer un doublon.
- Le secret du webhook est stocké en clair dans le workflow (nœud **Signature HMAC**). Ne réexporte pas le workflow vers Git sans remettre `COLLER_ICI_LE_SECRET_DU_WEBHOOK_PLANE`.
- Le token GitHub expire : le renouveler et le remplacer dans l'identifiant `GitHub token`.
- Changement de domaine : modifier `PLANE_PUBLIC_URL` et l'URL du webhook dans Plane.

## Modifier le workflow

1. Modifie `n8n/workflows/plane-vers-github.json`.
2. Lance le test local (Docker, n8n 2.44.5, fausses API Plane et GitHub) :

```bash
./scripts/test-n8n-workflow.sh
```

**Attendu :** `Résultat : 0 échec(s)`.

3. Réimporte le fichier dans n8n, puis refais les étapes 6, 7 et 10.

## Sauvegarde

Le workflow et les identifiants sont dans la base n8n : `backup.yml` les sauvegarde ([sauvegardes.md](sauvegardes.md)).

## Retour arrière

1. n8n → le workflow → **Unpublish**.
2. Plane → **Webhooks** → supprimer le webhook.

Les issues déjà créées restent dans GitHub.
