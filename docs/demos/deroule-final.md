# Déroulé final — démo Aetherix, vendredi 06/11/2026, 15:30 (visio)

> Demandé : le problème de départ · ce qui fonctionne aujourd'hui · ce que j'ai construit avec Claude Code ·
> les limites avant un pilote. **Cible : 8 minutes, puis questions.** Données fictives, dites comme telles.
> Détails et commandes complètes : `docs/demos/runbook-demo.md`.

---

## 0. Avant l'entretien

| Quand | Quoi | Vert si |
|---|---|---|
| 11:00 | `git pull origin main` puis lancer les deux scripts (§5) | les sorties correspondent à ce document |
| 11:15 | Enregistrer la **vidéo de secours** (3 min : WhatsApp + script), mention « données fictives, boucle réelle » | fichier lisible hors ligne |
| 14:30 | `fly status -a aetherix-backend` · `curl https://aetherix-backend.fly.dev/health` | machine `started`, `{"status":"ok"}` |
| 11:00 | **Rejoindre la sandbox Twilio** : envoyer `join <code>` (Console Twilio → Messaging → Try it out → Send a WhatsApp message) depuis le téléphone du profil. L'adhésion dure **72 h**. Sans elle, Twilio répond « not connected to a Sandbox » | confirmation Twilio reçue |
| 14:30 | Envoyer `prévision vendredi` au numéro sandbox depuis le téléphone | réponse avec « 🧪 Démonstration » |
| 15:15 | Fermer `backend/.env`, terminaux avec jetons, vault Obsidian, autres conversations WhatsApp | rien de privé à l'écran |
| 15:20 | Ouvrir les fenêtres dans l'ordre du §1, police du terminal agrandie | — |

## 1. Écran — fenêtres dans l'ordre

1. `docs/demos/fiche-aetherix.md` (rendu Markdown)
2. WhatsApp Desktop ou Web, **seule** la conversation sandbox visible
3. Terminal A : sortie de `demo_whatsapp_conversation.py`, déjà exécutée, remontée en haut
4. Linear HOS-357 → PR #298 (onglet « Checks »)
5. GitHub Actions, run `eval-parser-real` #24 (vert)
6. `docs/context/mape-benchmark.md`, section Recruit
7. Linear HOS-365

---

## 2. Déroulé minuté

### 0:00 — Le problème (40 s) · fenêtre 1
> « Mardi 14 h, Claire dirige le restaurant d'un hôtel indépendant. Avant l'heure limite du planning, elle doit
> décider si elle ajoute un extra pour le dîner de mercredi. Aujourd'hui, elle le fait de tête : la moyenne des
> quatre derniers mercredis. Trop de monde, ça coûte. Pas assez, le service se dégrade. »

Parties prenantes, une phrase : elle décide, la direction paie, le PMS distribue. Livraison dans ses outils :
WhatsApp ou son propre agent via MCP, **pas de dashboard**.

### 0:40 — La chaîne réelle (40 s) · fenêtre 2
Envoyer en direct `prévision vendredi`.
> « C'est la vraie chaîne : WhatsApp → Twilio → Fly → Supabase, sandbox Apaleo pour l'occupation. L'hôtel est
> fictif et le message le dit. »

**Plan B** si rien n'arrive en 20 s : « le webhook est sur un staging » → passer au terminal, sans s'attarder.

### 1:20 — Ce que fait le manager, et ce que le système en fait (1 min 40) · fenêtre 3, semaine 1
Faire défiler, s'arrêter sur 4 lignes seulement :
- `ok` → validé, **sans modèle** ;
- `mets-en 3 de plus` → le modèle lit une contre-proposition, le chiffre est lu **sans modèle** et cité en retour ;
- `pourquoi ?` → une explication, **jamais une décision** ;
- `bof, ça me paraît beaucoup` → confiance 0,6 → **rien n'est écrit sans un « oui »**.

> « Trois règles : déterministe d'abord, le modèle seulement là où le lexique ne sait pas, et rien d'écrit sous
> 0,85 de confiance sans confirmation. Chaque décision garde qui l'a prise et comment. »

Montrer au passage les lignes « Si accepté / Si refusé » du soir de match : coût et risque de manquer de bras,
avec une incertitude calibrée **sur données synthétiques**.

### 3:00 — La boucle d'apprentissage, et ce qu'elle m'a appris (1 min 30) · fenêtre 3, fin de sortie
- Semaine 2 : Claire retient **+3** au lieu de +2 les soirs d'événement.
- Passe hebdomadaire : **proposition** de passer de 15 à 12 couverts par extra. 8 décisions, dont 3
  contre-propositions, avec la mention « réels indépendants : non ». Rien n'est appliqué par la passe.
- Claire **approuve** → recommandation suivante : **toujours +2**.
> « Le ratio entre aussi dans le seuil de risque. La règle d'apprentissage supposait la demande fixe. Deux de mes
> règles ne se composent pas. Je l'ai découvert en construisant cette démo, c'est consigné, et on revient en arrière
> en un appel. C'est exactement à ça que sert la boucle. » → fenêtre 7 (HOS-365), 5 secondes.

Vocabulaire : apprentissage **approuvé par l'hôtel**, jamais « automatique ».

### 4:30 — Ce qui est mesuré (1 min) · fenêtres 5 et 6
- **Lecture des réponses** (run #24) : **98,1 %** sur 52 cas, Haiku 4.5, 3 runs. Aucune réponse écrite sans la
  confirmation exigée. « Des cas que j'ai écrits, sur un seul modèle : c'est une mesure de régression, pas de l'usage. »
- **Prévision** (Kaggle Recruit, restaurants réels, benchmark hors ligne) : Prophet bat la naïve en moyenne
  (MAPE 49,7 % contre 55,9 %), **fait jeu égal en médiane** (27,0 contre 27,6 %) et est **derrière à J+1**.
  « J'ai déclenché moi-même la clause de pivot : la valeur est dans la boucle de décision, pas dans le modèle. »

### 5:30 — Construit avec Claude Code (1 min 15) · fenêtre 4
HOS-357 : constat d'audit → périmètre **tranché et daté par moi** → critères cochés après vérification →
PR #298 → checks bloquants (eval-gate, schema-drift, public-status).
> « Claude Code écrit. Je décide du périmètre, et des gates mesurent. Quand la mesure contredit l'agent, c'est la mesure
> qui gagne. »

Deux exemples, pas plus :
- « pourquoi pas » écrit sans confirmation → **ni test supprimé, ni prompt retouché** : une règle produit, et le cas
  déclaré consommé ;
- un gate qui affichait « FAIL 0 % » sur une clé API invalide → corrigé en « non mesuré ».

BMAD en une phrase : story → critères → code → gates. J'y ai **ajouté** l'évaluation dès la conception et l'étiquetage
honnête, et j'ai **coupé** ce qui ne servait pas la preuve.

### 6:45 — Limites avant un pilote (45 s)
> « 0 utilisateur. Réels déclarés par le manager, pas de POS. Templates WhatsApp non approuvés. Défense
> prompt-injection différée. Sync PMS pas encore planifiée. Ratio appris défectueux (HOS-365). »

Critères de succès **gelés avant toute mesure** : Δ MdAPE ≥ 5 pts contre la naïve, acceptation ≥ 30 %.

### 7:30 — Ouverture (30 s)
> « Ce qui se transpose chez vos clients : l'évaluation dès la conception, l'humain sur l'irréversible, l'étiquetage
> honnête de ce qui est construit, et livrer dans les outils du client plutôt qu'un écran de plus. »

---

## 3. Plans B

| Panne | Réaction |
|---|---|
| WhatsApp ne répond pas | Une phrase, puis terminal (§2, 1:20). Ne pas déboguer en direct |
| Partage d'écran qui rame | Vidéo de secours |
| Le modèle réel lit autrement que prévu | C'est la démonstration : confiance → confirmation |
| Question technique hors sujet | « Bonne question, je vous montre après ? » Garder le minutage |

**Version 3 minutes** si le temps manque : 0:00 problème → 1:20 (4 lignes) → 3:00 (HOS-365) → 6:45 limites.

## 4. Questions probables (réponses courtes)

- **Pourquoi pas un utilisateur d'abord ?** Juste. Les 5 interviews managers (HOS-309) ne sont pas faites. Objectif
  reformulé portfolio en septembre.
- **Que se passe-t-il quand le modèle se trompe ?** Sous 0,85, rien sans « oui ». Au-dessus, la décision est citée et
  corrigeable (« corriger mardi »). La source est stockée.
- **Entraîné sur Kaggle ?** Non. Kaggle = benchmark hors ligne. Le service de démo tourne sur une série
  synthétique, dite comme telle.
- **Coût ?** ≈ 0,75 $ de LLM par hôtel et par mois. WhatsApp coûte plus cher que le modèle.
- **Le POC Anima (Lovable) ?** Seulement si on demande comment j'explore avant de construire : 30 secondes,
  « prototype fictif, derrière un gate RGPD ».
- Autres réponses : `runbook-demo.md` §6.

## 5. Sorties attendues (pour vérifier le matin)

- `demo_whatsapp_conversation.py` : récap semaine 1 = « 4 reçues · Validées 0 · Refusées 3 · Corrigées 1 ».
  Proposition « 15.0 → 12.0 ». Soir d'événement suivant « +2 (était +2) ». Retour arrière « ratio en vigueur 15 ».
- `closed_loop_demo.py` (cloud, 05/11, deux runs identiques) : erreur post-choc **15,6 % → 12,1 %**, acceptation simulée
  76,7 %, 1 rejet G-3. Si ta machine affiche autre chose, **cite ce qu'elle affiche**.
