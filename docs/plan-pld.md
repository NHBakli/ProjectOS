# Plan : générer le PLD depuis Plane et GitHub

Statut : **plan validé, à implémenter**. Rédigé le 2026-11-01.

## Objectif

Une commande produit le PLD Epitech d'une période, prêt à relire :

```bash
./scripts/generer-pld.sh 2
```

| Fichier produit | Rôle |
|---|---|
| `PLD/Sprint_2/PLD_Flowly_Sprint2.docx` | Le PLD, construit sur `PLD_Template.docx` officiel |
| `PLD/Sprint_2/Suivi_Taches_Sprint2.xlsx` | Le classeur, construit sur `PLD_Suivi_Taches.xlsx` officiel |
| `PLD/Sprint_2/rapport-coherence.md` | **Non remis.** Les problèmes à corriger avant la remise |

Tu relis, tu corriges dans Plane si besoin, tu relances, puis tu déposes dans le dépôt Epitech.

## Choix faits

| Sujet | Choix |
|---|---|
| Où ça tourne | Script sur ton poste. Automatisation possible plus tard. |
| Fiches stories | Modèle de description dans chaque ticket Plane. Le script extrait les rubriques et signale les manques. |
| Parties rédigées | Chiffres calculés + phrases types. Textes libres (présentation, schéma, plan alpha/bêta) dans un fichier de config. |
| Période | Un PLD = entre deux remises (Keynote 2 → Follow-up 1…). Les sprints Scrum de 2 semaines = cycles Plane. |
| Historique ClickUp | Repris dans Plane par l'API ClickUp (lecture seule), anciennes sprints = cycles Plane. Guide : [07-import-clickup.md](07-import-clickup.md). |

## Ce qu'exige Epitech (`Processus_PLD.pdf`)

- Sections : page de titre, révisions, résumé, schéma fonctionnel, tableau des cartes, fiches stories, plan alpha/bêta, rapport d'avancement.
- Carte : identifiant unique, titre, responsable, estimation **0,5 à 4 jours**, statut.
- Charge : **2 jours par personne et par mois**.
- Les cartes terminées aux PLD précédents restent visibles, statut « Terminé ».
- Dépôt : `PLD/Sprint_N/PLD_[Projet]_SprintN.docx` + `Suivi_Taches_SprintN.xlsx`, 48 h avant l'échéance.
- Notation /20 : complétude, cohérence de la charge, qualité des cartes, réel vs planifié, présentation.

## D'où vient chaque information

| Dans le PLD | Plane | GitHub (croisement) |
|---|---|---|
| ID de la carte | Identifiant du ticket (ex. `FLOW-12`) | — |
| Titre | Titre du ticket | — |
| Responsable | 1ᵉʳ assigné (les autres cités) | Assignés et auteurs des PR, pour contrôle |
| Domaine | Étiquette `Frontend` / `Backend` / `Mobile` / `DevOps` | Dépôt de l'issue |
| Charge (jours) | Estimation (points = jours) | — |
| Début / fin prévus | `start_date` / `target_date` | — |
| Statut | État Plane (groupe : backlog, à faire, en cours, terminé, annulé) | Issue ouverte/fermée |
| Avancement % | Déduit de l'état (tableau en config) | — |
| En tant que / Je veux / Afin de / DoD | Rubriques de la description | — |
| Preuve de livraison | — | PR fusionnée qui ferme l'issue (lien, date, auteur) |
| Date réelle de fin | `completed_at` | Date de fusion de la PR |
| Points bloquants | Étiquette `Bloqué` + rubrique « Points bloquants » | PR ouverte depuis longtemps |
| Rapport par membre | Cartes par responsable | PR fusionnées par auteur sur la période |
| Sprints Scrum | Cycles Plane de la période | — |

Le lien Plane → GitHub existe déjà : le workflow n8n ajoute le lien de l'issue dans chaque ticket.

## Contrôles de cohérence (rapport-coherence.md)

Chaque contrôle vise un critère de la note.

| Contrôle | Critère visé |
|---|---|
| Carte sans estimation, ou hors 0,5–4 j | Charge |
| Charge d'un membre loin de 2 j/mois sur la période | Charge |
| Carte sans responsable, sans dates, sans rubriques de story | Qualité des cartes |
| Terminé dans Plane, mais issue GitHub ouverte ou aucune PR fusionnée | Réel vs planifié |
| Issue fermée ou PR fusionnée, mais ticket pas terminé dans Plane | Réel vs planifié |
| Date de fin prévue dépassée, carte non terminée | Réel vs planifié |
| PR fusionnée sur la période sans carte Plane liée | Complétude |
| Responsable Plane ≠ auteur de la PR | Information (pas une erreur) |

## Conventions à mettre en place dans Plane (avant la 1ʳᵉ génération)

1. **Estimations** : projet → Paramètres → Estimations → système **Points** avec les valeurs `0.5`, `1`, `1.5`, `2`, `2.5`, `3`, `4` (1 point = 1 jour).
2. **Cycles** : un cycle Plane par sprint Scrum de 2 semaines, avec ses dates.
3. **Dates** : début et fin prévues sur chaque ticket.
4. **Responsable** : le 1ᵉʳ assigné est le responsable de la carte.
5. **Étiquette `Bloqué`** pour les tickets bloqués.
6. **Modèle de description**, à coller dans chaque ticket :

```text
En tant que : utilisateur de Flowly
Je veux : …
Afin de : …

Description : …

Definition of Done :
- …

Points bloquants : aucun
```

7. **Comptes Plane** pour chaque membre, avec son nom complet. Le nom affiché dans Plane est celui du PLD.

## Organisation du code

| Chemin | Rôle |
|---|---|
| `pld/generer_pld.py` | Point d'entrée : lit la config, appelle les étapes |
| `pld/source_plane.py` | Lecture **seule** de l'API Plane : projet, états, étiquettes, estimations, cycles, membres, tickets, liens |
| `pld/source_github.py` | Lecture **seule** de GitHub (GraphQL) : issues liées, PR qui les ferment, PR fusionnées de la période |
| `pld/analyse.py` | Croisement, calculs (charges, avancement), contrôles |
| `pld/sortie_xlsx.py` | Remplit le classeur officiel |
| `pld/sortie_docx.py` | Remplit le modèle Word officiel |
| `pld/pld.example.yml` | Exemple de config, sans donnée réelle |
| `pld/tests/` | Fausses données Plane et GitHub, tests sans réseau |
| `scripts/generer-pld.sh` | Crée un environnement Python isolé (versions épinglées), lance le script |

Hors Git :

| Chemin | Contenu |
|---|---|
| `~/.config/projectos/pld.yml` | Adresse Plane, slug, ID projet, périodes, membres (nom, compte GitHub), textes libres |
| `~/Downloads/PLD_Template.docx`, `PLD_Suivi_Taches.xlsx` | Modèles Epitech, chemin indiqué dans `pld.yml` |

Accès :

- **Plane** : clé API demandée au lancement (pas stockée), ou variable `PLANE_API_KEY`.
- **GitHub** : `gh auth token`, déjà connecté sur ton poste. Lecture seule.
- Le script ne **modifie rien** dans Plane ni dans GitHub.

## Sorties

**Classeur** : feuille « Avancement des tâches » remplie par membre (ID, membre, titre, charge, état, avancement, dates, points bloquants, commentaires = lien de l'issue). Feuille « Révisions » complétée. « Tableau de bord » conservé tel quel. Les colonnes de l'équipe pédagogique restent vides.

**Word** : on garde la page de titre, les styles, la table des matières et les liens internes du modèle. On remplace le contenu d'exemple section par section. Les fiches sont regroupées **par membre**, comme dans le modèle, et chaque ligne du tableau des cartes renvoie vers sa fiche. Word propose de mettre à jour la table des matières à l'ouverture.

## Étapes d'implémentation

Chaque étape se termine par un test qui passe.

0. **Reprise ClickUp** : extraction ✅ (`pld/clickup_extraire.py`), correspondances et import à faire → [07-import-clickup.md](07-import-clickup.md).
1. **Squelette** : dossier `pld/`, config d'exemple, `generer-pld.sh`, dépendances épinglées. Test : `--aide` s'affiche.
2. **Lecture Plane** + fausses données. Test local. Puis tu lances `--extraire` (lecture seule, JSON sans secret) sur le vrai Plane.
3. **Lecture GitHub** + croisement. Test sur les vraies issues (lecture seule, depuis mon poste).
4. **Contrôles** + `rapport-coherence.md`. Test : chaque contrôle a un cas qui le déclenche.
5. **Classeur Excel**. Test : ouverture du fichier, contenu des cellules relu par le test.
6. **PLD Word**. Test : conversion en PDF avec LibreOffice, relecture visuelle.
7. **Doc** `docs/08-pld.md` (guide pas à pas) et premier vrai PLD, que tu relis.

## Points à trancher demain

| Question | Proposition |
|---|---|
| Cartes des anciennes sprints | Tranché : reprises depuis ClickUp (voir étape 0). Reste à voir le lien avec les issues GitHub déjà créées. |
| ID des cartes | Identifiant Plane (`FLOW-12`) : unique et retrouvable. Le modèle Excel utilise `1.1`, `1.2`… : on peut l'afficher en plus. |
| Date de la prochaine remise | À me donner : elle fixe la période du Sprint 2. |
| Liste des membres | Nom complet, compte Plane, compte GitHub (le brouillon du Sprint 1 en donne une partie). |
| Textes libres | Reprendre ceux du brouillon du Sprint 1 (résumé, schéma fonctionnel, plan alpha/bêta) dans `pld.yml`. |
| Modèle Word trop complexe à remplir proprement | Repli : générer un document neuf qui reprend ses styles et sa structure. On décide après l'étape 6. |

## Ce qui n'est pas prévu (pour l'instant)

- Génération automatique sur le serveur, ou Pull Request dans le dépôt Documentation.
- Rédaction par une IA.
- Écriture dans Plane ou GitHub.
