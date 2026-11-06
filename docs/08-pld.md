# Générer le PLD

Une commande lit Plane (historique) et GitHub (cartes, preuves), puis produit le PLD Epitech.
Elle ne modifie rien dans Plane ni dans GitHub. Plan et règles : [plan-pld.md](plan-pld.md).

| Fichier produit (`~/projectos-pld/PLD/Sprint_N/`) | Rôle |
|---|---|
| `PLD_Flowly_SprintN.docx` | Le PLD, sur le modèle Word officiel |
| `Suivi_Taches_SprintN.xlsx` | Le classeur, sur le modèle Excel officiel |
| `rapport-coherence.md` | **Non remis.** Ce qu'il faut corriger avant la remise |
| `cartes.json` | **Non remis.** Les données calculées, pour vérifier |

| Étape | État |
|---|---|
| 1. Config, période, modèle d'issue | ✅ |
| 2. Lecture de Plane | ✅ testée face à un faux Plane |
| 3. Lecture de GitHub + croisement | ✅ testée sur le vrai GitHub (lecture seule) |
| 4. Rapport de cohérence | ✅ |
| 5. Classeur Excel | ✅ |
| 6. PLD Word | ✅ relu en PDF (LibreOffice) |
| 7. Premier vrai PLD | **À lancer par toi** (clé Plane) |

## 1. Préparer (une seule fois)

1. Config : `~/.config/projectos/pld.yml` (hors Git). Modèle commenté : [`pld/pld.example.yml`](../pld/pld.example.yml).

| Clé | Rôle |
|---|---|
| `pld.remise_suivante`, `pld.debut_par_defaut` | Période par défaut |
| `pld.membres` | Pseudo GitHub → nom affiché. **Jamais dans ce dépôt** |
| `pld.ignores` | Membres de l'organisation hors équipe |
| `pld.responsable`, `pld.email`, `pld.promotion` | Descriptif du document (vide = `[À compléter]`) |
| `pld.textes.resume` | Résumé (le script ajoute les chiffres de la période) |
| `pld.textes.schema`, `pld.textes.plan_alpha_beta` | Texte, ou `{texte, tableau, image, note}` |
| `pld.textes.bloquants`, `pld.textes.commentaire` | Ajoutés sous les points bloquants et le commentaire calculés |
| `pld.revisions` | Révisions précédentes (`date`, `version`, `auteurs`, `sections`, `commentaires`) |

2. Modèles Epitech dans `~/Downloads/` : `PLD_Template.docx`, `PLD_Suivi_Taches.xlsx` (autre chemin : `pld.modeles`).
3. GitHub : `gh auth status` doit montrer les droits `project` et `repo` (déjà le cas).
4. Vérifier :

```bash
cd ~/Desktop/Dev/ProjectOS
./scripts/generer-pld.sh 2 --verifier
```

**Attendu :** la période, `Membres : 8`, `✓` devant les deux modèles, `Vérification seule : rien n'a été lu ni écrit.`

## 2. Générer

1. Crée une clé Plane : avatar → **Paramètres** → **Jetons d'accès personnel** → **Ajouter un jeton d'accès** → nom `PLD lecture`, expiration courte → **Générer un jeton** → copie-la. (Plane n'a pas de clé « lecture seule » : c'est le script qui ne fait que des GET.)
2. Lance :

```bash
cd ~/Desktop/Dev/ProjectOS
read -rsp 'Clé API Plane : ' PLANE_API_KEY && export PLANE_API_KEY && echo
./scripts/generer-pld.sh 2
unset PLANE_API_KEY
```

**Attendu** (1 à 2 minutes) :

```text
Plane : /home/…/projectos-pld/plane/plane-….json (… requêtes, lecture seule)
GitHub : … issues, … PR fusionnées sur la période (… requêtes, lecture seule)
Cartes : … dans le PLD, … sur la période (… terminées, … en cours, … à faire, … bloquées)
Contrôles : … à corriger, … à vérifier, … pour information
Fichiers :
  …/PLD_Flowly_Sprint2.docx
  …/Suivi_Taches_Sprint2.xlsx
  …/rapport-coherence.md
```

Autres choix de période, ou relance sans relire Plane :

```bash
./scripts/generer-pld.sh 2 --du 2026-10-02 --au 2026-12-02
./scripts/generer-pld.sh 2 --sprints "Sprint N°2" "Sprint N°3"
./scripts/generer-pld.sh 2 --plane ~/projectos-pld/plane/plane-20261106T150000Z.json
./scripts/generer-pld.sh 2 --titre "Sprint 2 – Follow-up"
```

## 3. Relire et corriger

1. Ouvre `rapport-coherence.md`. Corrige d'abord les lignes **✗ À corriger**, dans GitHub (ou Plane) :

| Problème | Où corriger |
|---|---|
| Carte sans estimation, ou hors 0,5–4 j | Projet GitHub → champ **Estimate** (jours) |
| Carte sans responsable | Issue → **Assignees** |
| Dates manquantes | Projet GitHub → **Start date**, **Target date** |
| Fiche story incomplète | Corps de l'issue (modèle « Carte PLD », section 4) |
| Fin prévue dépassée | Fermer l'issue si c'est fini, sinon décaler **Target date** |
| PR fusionnée sans carte | Ajouter `Closes #N` dans la PR, ou créer l'issue |

2. Relance la génération (`--plane …` pour ne pas relire Plane).
3. Ouvre le `.docx` dans Word : accepte **Mettre à jour les champs** (sommaire et numéros de page). Complète les `[À compléter]` restants.
4. Dépose `PLD_Flowly_Sprint2.docx` et `Suivi_Taches_Sprint2.xlsx` dans `PLD/Sprint_2/` du dépôt Epitech, 48 h avant l'échéance.

## Comment le script décide

| Sujet | Règle |
|---|---|
| Carte | Un ticket Plane (avec ses issues GitHub), ou une issue d'un projet GitHub qu'aucun ticket ne cite. Les tickets parents (phases, sprints) ne sont pas des cartes |
| État | GitHub d'abord : issue fermée = Terminé (Annulé si « not planned ») ; sinon **Status** : Backlog/Ready = À faire, In progress/In review = En cours. Sans issue : l'état Plane |
| Bloqué | Étiquette `Bloqué`/`blocked`, ou « Points bloquants » rempli (autre que « aucun ») |
| Avancement | À faire 0 %, En cours 50 % (In review 80 %), Terminé 100 % |
| Responsable | 1ᵉʳ assigné GitHub (hors `pld.ignores`), sinon auteur de la PR, sinon « Équipe (non attribué) » |
| Charge | Estimation Plane, sinon **Estimate** GitHub, sinon **Size** (XS 0,5 · S 1 · M 2 · L 3 · XL 4) |
| Fin réelle | Fermeture de l'issue GitHub, sinon « Terminé le » (ClickUp) |
| Dans la période | Commencée avant la fin de période, et pas finie avant son début |
| Cartes affichées | Toutes celles commencées avant la fin de période (les terminées restent visibles, comme le demande Epitech) |
| Numéros | `K.I` : K = membre (ordre de `pld.membres`), I = ordre de début |

### En cas de problème

| Message | Cause | Solution |
|---|---|---|
| `Configuration introuvable` | Pas de `pld.yml` | Copier `pld/pld.example.yml` |
| `Accès refusé par Plane (401)` | Clé fausse ou expirée | Recréer la clé |
| `gh a échoué` | `gh` déconnecté | `gh auth login`, puis relancer |
| `Projet GitHub n°N introuvable` | Mauvais numéro | Corriger `github.projets` dans `pld.yml` |
| `Sprint inconnu dans Plane` | Nom différent du cycle | Copier le nom exact du cycle |
| `Modèle Word introuvable` / `Feuille … absente` | Modèle Epitech absent ou modifié | Remettre le modèle officiel |
| Erreur `pip` (`hash`) | Paquet modifié ou réseau | Relancer ; si ça persiste, ne pas forcer |

### Retour arrière

Rien à défaire dans Plane ni GitHub. Le script n'écrit que dans `~/projectos-pld/` et `~/.cache/projectos/pld-venv` :

```bash
rm -rf ~/projectos-pld/PLD/Sprint_2 ~/projectos-pld/plane ~/.cache/projectos/pld-venv
```

## 4. Installer le modèle d'issue GitHub

Le modèle [`pld/modeles/carte-pld.yml`](../pld/modeles/carte-pld.yml) ajoute un formulaire « Carte PLD » : En tant que, Je veux, Afin de, Description, Definition of Done, Points bloquants. Le générateur lit ces rubriques (en français, ou en anglais pour les issues traduites par n8n).

Dans chaque dépôt où l'équipe crée des tâches (`Frontend`, `Backend`, `Mobile`, `DevOps`) :

1. Crée une branche, par exemple `modele-carte-pld`.
2. Copie le fichier :

```bash
mkdir -p .github/ISSUE_TEMPLATE
cp ~/Desktop/Dev/ProjectOS/pld/modeles/carte-pld.yml .github/ISSUE_TEMPLATE/carte-pld.yml
```

3. Commit, push, Pull Request vers la branche par défaut, merge.

**Attendu :** **Issues** → **New issue** propose **Carte PLD**.

**Retour arrière :** supprimer `.github/ISSUE_TEMPLATE/carte-pld.yml`. Les issues déjà créées ne changent pas.
