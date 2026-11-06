# Générer le PLD

Le script lit Plane (historique) et GitHub (cartes, preuves), puis produit le PLD Epitech.
Il ne modifie rien dans Plane ni dans GitHub. Plan complet : [plan-pld.md](plan-pld.md).

| Étape | État |
|---|---|
| 1. Squelette : config, choix de la période, modèle d'issue | ✅ 2026-11-06 |
| 2. Lecture de Plane (`--extraire`) | ✅ Écrite, testée face à un faux Plane. Essai sur le vrai Plane : à faire |
| 3. Lecture de GitHub + croisement | À faire |
| 4. Rapport de cohérence | À faire |
| 5. Classeur Excel | À faire |
| 6. PLD Word | À faire |

## 1. Préparer la configuration

Fichier : `~/.config/projectos/pld.yml` (hors Git). Modèle : [`pld/pld.example.yml`](../pld/pld.example.yml).

| Clé | Rôle |
|---|---|
| `pld.remise_suivante` | Fin de période par défaut (prochaine remise) |
| `pld.debut_par_defaut` | Début de période par défaut |
| `pld.membres` | Pseudo GitHub → nom affiché dans le PLD |
| `pld.ignores` | Membres de l'organisation hors équipe |
| `pld.modeles` | Chemins des modèles Epitech (défaut : `~/Downloads/`) |

Les noms des membres ne vont **jamais** dans ce dépôt.

## 2. Lancer

```bash
cd ~/Desktop/Dev/ProjectOS
./scripts/generer-pld.sh 2
```

Choisir la période :

```bash
./scripts/generer-pld.sh 2 --du 2026-10-02 --au 2026-12-02
./scripts/generer-pld.sh 2 --sprints "Sprint N°2" "Sprint N°3"
```

La 1ʳᵉ fois, le script crée un environnement Python dans `~/.cache/projectos/pld-venv` (quelques secondes). Les versions et empreintes sont figées dans `pld/requirements.txt`.

**Attendu (étape 1) :** la période, le nombre de membres, `✓` devant les deux modèles, les fichiers prévus dans `~/projectos-pld/PLD/Sprint_2/`, puis `Rien n'a été lu ni écrit.`

### En cas de problème

| Message | Cause | Solution |
|---|---|---|
| `Configuration introuvable` | Pas de `pld.yml` | Copier `pld/pld.example.yml` dans `~/.config/projectos/pld.yml` |
| `Période à l'envers` | `--du` après `--au` | Corriger les dates |
| `Choisir soit --sprints, soit --du/--au` | Les deux donnés | En garder un seul |
| `✗ introuvable` devant un modèle | Modèle Epitech absent | Indiquer son chemin dans `pld.modeles` |
| Erreur `pip` (`hash`) | Paquet modifié ou réseau | Relancer ; si ça persiste, ne pas forcer : me prévenir |

### Retour arrière

Le script n'écrit que dans `~/.cache/projectos/pld-venv` et, avec `--extraire`, dans `~/projectos-pld/plane/`. Pour l'effacer :

```bash
rm -rf ~/.cache/projectos/pld-venv
```

## 3. Lire Plane (`--extraire`)

Lecture seule : le script ne fait que des requêtes GET. Il enregistre un JSON sans clé ni e-mail.

1. Crée une clé API dans Plane : avatar → **Paramètres** → **Jetons d'accès personnel** → **Ajouter un jeton d'accès** → nom `PLD lecture`, expiration courte → **Générer un jeton** → copie-la. Plane n'a pas de clé « lecture seule » : c'est le script qui se limite aux GET.
2. Lance :

```bash
cd ~/Desktop/Dev/ProjectOS
read -rsp 'Clé API Plane : ' PLANE_API_KEY && export PLANE_API_KEY && echo
./scripts/generer-pld.sh 2 --extraire
```

**Attendu :** `Projet Plane : « Flowly » (FLOWL)`, la liste des 4 cycles avec leurs dates, `Tickets : 42 (4 parent(s), 38 carte(s))`, `Liens GitHub : 33 (…)`, puis `Extraction : ~/projectos-pld/plane/plane-….json (… requêtes, lecture seule)`.

Avec des sprints : `./scripts/generer-pld.sh 2 --extraire --sprints "Sprint N°2"` affiche aussi `Période des sprints : …`.

3. Quand tu as fini : `unset PLANE_API_KEY`.

Compte une minute environ : une requête par ticket pour ses liens, et Plane limite à 60 requêtes par minute (le script attend tout seul).

| Message | Cause | Solution |
|---|---|---|
| `Accès refusé par Plane (401)` | Clé fausse ou expirée | Recréer la clé |
| `Introuvable (404)` | Espace ou ID de projet faux | Vérifier `plane:` dans `pld.yml` |
| `Sprint inconnu dans Plane` | Nom différent du cycle | Copier le nom affiché dans la liste des cycles |
| `Adresse de Plane inconnue` | Ni `plane.url` ni `platform.yml` | Ajouter `plane.url` dans `pld.yml` |

**Retour arrière :** rien à défaire dans Plane. Effacer les extractions : `rm ~/projectos-pld/plane/plane-*.json`.

## 4. Installer le modèle d'issue GitHub

Le modèle [`pld/modeles/carte-pld.yml`](../pld/modeles/carte-pld.yml) ajoute un formulaire « Carte PLD » aux nouvelles issues : En tant que, Je veux, Afin de, Description, Definition of Done, Points bloquants. Le générateur lit ces rubriques (en français, ou en anglais pour les issues traduites par n8n).

À faire dans chaque dépôt où l'équipe crée des tâches (`Frontend`, `Backend`, `Mobile`, `DevOps`) :

1. Dans le dépôt, crée une branche, par exemple `modele-carte-pld`.
2. Copie le fichier :

```bash
mkdir -p .github/ISSUE_TEMPLATE
cp ~/Desktop/Dev/ProjectOS/pld/modeles/carte-pld.yml .github/ISSUE_TEMPLATE/carte-pld.yml
```

3. Commit, push, Pull Request vers la branche par défaut, merge.

**Attendu :** sur GitHub, **Issues** → **New issue** propose **Carte PLD**.

Après la création de l'issue, dans le projet GitHub de l'équipe : remplir **Estimate** (jours, 0.5 à 4), **Start date**, **Target date**. Le 1ᵉʳ assigné est le responsable.

**Retour arrière :** supprimer `.github/ISSUE_TEMPLATE/carte-pld.yml` dans le dépôt. Les issues déjà créées ne changent pas.
