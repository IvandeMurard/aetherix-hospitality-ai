# Fiche — Context is King #6

> Mardi 22 septembre 2026 · 18:30 · Paris · [Luma](https://luma.com/context-vk3v)
> **Objectif : être mémorisé par 4-5 personnes.** Pas pitcher un produit, pas lever des fonds.
> Fiche de préparation networking. Aucune valeur d'archive projet — statut `Design` au sens de `docs/context/status-taxonomy.md` ne s'applique pas ici, ce document n'est pas une surface produit.

---

## 1. Pitch 30 secondes

> « Je construis un système multi-agents pour les opérations hôtelières. Le truc intéressant n'est pas le modèle : c'est que **chaque recommandation est stockée à côté de ce qui s'est réellement passé** — y compris quand le manager a fait l'inverse et qu'il avait raison. Et **je publie les cas où ma prévision est moins bonne qu'un calcul basique.** »

La dernière phrase est celle qui fait lever un sourcil. Dans une salle de démos, celui qui publie ses échecs est le seul dont on se souvient.

### Si on creuse — 2 min

1. Des agents spécialisés qui **observent et ne décident jamais**
2. Un orchestrateur qui détient toute la décision — **pas encore construit, volontairement**
3. Un journal qui relie chaque reco, la réponse humaine et le résultat réel

### À dire d'entrée, sans gêne

- « 5 agents spécifiés, **un seul qui tourne** »
- « Solo depuis fin 2025 »
- « **Zéro utilisateur réel.** J'ai le mécanisme, pas un acquis. »

---

## 2. Trois munitions, par ordre de sortie

Même message sous trois angles : *je sais mesurer, je sais ne pas construire, je sais dire ce qui ne marche pas.*

### 1 — Mon eval bloque le merge, mais j'ai dû prouver qu'elle était fiable avant

Si une modif dégrade la qualité, la CI sort en erreur et la PR ne passe pas. Avant d'armer ça, il fallait prouver que le test ne se déclenche pas au hasard : **3 exécutions, résultat identique, variance 0,00**. Idem pour le juge LLM — grille binaire, jeu annoté à la main, accord mesuré avec l'humain (**kappa ≥ 0,8**) avant de le laisser noter seul.

> « Un gate instable, c'est pire que pas de gate. Donc je qualifie l'instrument avant de m'en servir comme juge. »

**Cible : tout le monde.** C'est le sujet le moins bien traité de la salle.

### 2 — J'ai instruit le dossier « graphe de contexte » et j'ai décidé de ne pas le construire

Deux talks graphes ce soir. Extension graphe indisponible sur l'infra, solution maison retenue, **puis tout différé** : la moitié des requêtes s'appuyait sur une table inexistante, l'autre doublonnait ce qui existe déjà. Design rangé, condition de reprise écrite. **Savoir ne pas construire est la compétence qu'on achète.**

> « J'ai conclu que je n'avais pas encore gagné le droit d'avoir un graphe. Chez vous, qu'est-ce qui déclenche ce droit ? »

**Cible : Alcaraz (AWS) · Jouvance (Amundi).**

### 3 — J'ai outillé ma propre contradiction

Cinq étiquettes obligatoires sur toute surface — **Built / Shadow-mode / PoC synthétique / Design / Research** — vérifiées automatiquement en CI. « Built » ne veut pas dire « adopté », et l'étiquette floue « Built (PoC) » est interdite.

> « C'est un projet solo, personne n'est là pour me contredire. Donc j'ai automatisé la contradiction. »

**Cible : en 2e temps, avec n'importe qui.** C'est ce qui rend croyable tout le reste.

---

## 3. Ce qu'on va te demander

**« Ça tourne chez combien d'hôtels ? »**
→ **Zéro.** Le staging tourne, le pilote n'a pas commencé. J'ai le mécanisme en place, pas un avantage accumulé. *Dis-le vite et sans gêne.*

**« Pourquoi 5 agents et pas un seul gros ? »**
→ *Meilleure réponse du répertoire, à apprendre.* Les frontières sont tracées là où les **régimes juridiques** diffèrent, pas là où les capacités diffèrent. Inférer sur un client = donnée personnelle sous DPIA. Le savoir-faire du personnel = droit du travail. Les couverts et la météo = ni l'un ni l'autre. Découper entre agents qui partagent le même régime coûte de la coordination et ne rapporte rien.

**« Pourquoi pas LangGraph / CrewAI / un framework ? »**
→ Je n'ai qu'un agent vivant. Un graphe se paie en routage, parallélisme ou durabilité — avec un seul nœud qui répond, **il n'y a rien à router**. Je le construirai quand un deuxième aura des utilisateurs.

**« Ta prévision, elle est bonne ? »**
→ Sur données synthétiques, 15 % d'erreur — **mais c'est circulaire, j'ai généré les données**. Sur le vrai jeu : 6 points mieux qu'un calcul naïf en moyenne, **match nul en médiane**. Donc : pas encore prouvé. *Cette réponse te fait gagner la conversation.*

**« La mémoire d'agent est une commodité. C'est quoi ton edge ? »**
→ Exactement, et je le dis dans le README. Ce qui n'est **pas** commodité, c'est la boucle : ce que l'humain fait de chaque reco, ce qui se passe ensuite, et l'écart entre les deux — enregistré **contre** la reco qui l'a précédé.

**« Tu cherches quoi ? »**
→ « Une équipe qui a ces problèmes-là pour de vrai, avec des utilisateurs. » **Prépare-la : c'est le vrai objectif de la soirée.**

---

## 4. Mémoire & contexte, agent par agent

Le fil qui relie le projet au thème de la soirée : **le Mesh est une taxonomie du contexte hôtelier, découpée par durée de vie et par régime de rétention.**

| Agent | Sa mémoire | Contexte interne | Contexte externe |
|---|---|---|---|
| **Aetherix** · Built | Mémoire opérationnelle privée par hôtel : feedbacks managers, décisions, résultats | couverts, staffing, historique des overrides | météo, événements locaux, occupation |
| **Anima** · PoC synthétique | 4 couches par durée de vie : le séjour → 30 j → 36 mois → cohortes anonymes | séjours, plaintes, préférences observées | vol en retard, CRM, avis en ligne |
| **Tacet** | Patterns environnementaux par zone et saison | — | bruit, travaux, météo, open data |
| **Peritia** · Design | Le savoir-faire de la maison — celui qui part quand le chef concierge démissionne | routines, fournisseurs, tours de main | le quartier |
| **Orchestrateur** · Design | **Aucune, volontairement** — sans état | lit tout, ne stocke rien | — |

**Idée à vendre nº1** — « Son vol a 3 h de retard ce soir » et « il est sensible au bruit depuis 2023 » ne vivent pas dans la même base et ne se périment pas au même rythme. *C'est le sujet du talk de Jean Duquenne, dans un autre domaine.*

**Idée à vendre nº2** — Le seul composant qui décide est le seul qui n'a **aucune** mémoire. Contre-intuitif → bonne discussion.

---

## 5. Qui aborder, avec quoi

**Stan Dmitriev** — Aiven · talk « Context Gates » · **Priorité 1**
Il automatise à la source ce que tu as fait à la main pendant un an : capturer le *pourquoi* d'une décision au seul moment où il existe. *« Voilà où ma discipline manuelle a cédé. »* Échange entre pairs, pas une question — et c'est l'organisateur.

**Anthony Alcaraz** — AWS · Agentic GraphRAG
Munition 2. Il écrit un O'Reilly dessus : un contre-cas argumenté l'intéresse plus qu'un acquiescement.

**Jeremy Jouvance** — Amundi · Graph Engineering
Son « le graphe est la couche manquante » vs ton « avec un seul agent vivant, il n'y a rien à router ». Vrai désaccord = vraie conversation.

**Jean Duquenne** — CTO Certo · conformité cosmétique
Son talk = « combien de contexte chaque vérification a vraiment besoin ». C'est ton tableau mémoire, autre domaine. Puis : *« le régime juridique est ce qui trace mes frontières d'agents. »*

**Yash Pabbisetti** — CTO GoCanopy
Passé de SQL généré → workflow → boucle d'agent. Demande **ce qui a déclenché chaque passage** : c'est la réponse dont tu as besoin pour ton orchestrateur.

**Moustapha Ebnou** — CTO Cominty · harness de prod
Terrain commun : garde-fous à l'exécution, coupe-circuits, bornes de sécurité. Comparez vos façons de logger *pourquoi* un garde-fou s'est déclenché.

**Elaia · Daphni** — VC présents
Zéro pitch. *« Je ne lève pas, je cherche une équipe qui a ce problème — qui, dans vos portefeuilles, fait du multi-agents sur données réelles ? »*

---

## 6. À ne pas faire

- **Ne dis jamais « ma startup ».** Toute ambiguïté ici détruit la crédibilité que la munition 3 t'achète.
- **Ne pitche pas les 5 agents comme s'ils existaient.** Deux n'ont pas une ligne de code. Dis-le dans les 20 premières secondes, sinon quelqu'un ouvre le repo et le trouve tout seul.
- **Ne parle pas d'Anima en premier.** Le plus séduisant et le plus fragile. Garde-le pour « et ensuite ? ».
- **Zéro jargon interne.** Les numéros d'ADR, de décision ou de ticket ne veulent rien dire hors du repo. Dis l'idée, jamais le numéro.

---

## 7. Pratique & après

- **Le repo public est ton support.** Le schéma du README est déjà légendé « les traits pleins portent du trafic, les pointillés non » — il fait le travail tout seul.
  `github.com/IvandeMurard/Hospitality-Multi-agent-Architecture`
- **Pose 3 questions, ne fais pas que répondre.**
  (a) Comment vous mesurez qu'un agent *s'améliore*, pas juste qu'il tourne ?
  (b) Qu'est-ce qui a déclenché votre passage de workflow à boucle d'agent ?
  (c) Votre couche de mémoire, vous la construiriez encore aujourd'hui ?
- **Follow-up demain matin, pas dans 3 jours.** LinkedIn, une phrase spécifique à ce qui a été dit. C'est là que se joue la valeur réelle de la soirée.

---

## 8. Glossaire — si on emploie ces mots

| Terme | En clair |
|---|---|
| **Eval / gate** | Test automatique de la qualité d'un agent ; « gate » = il bloque la mise en production s'il échoue |
| **Graphe de contexte** | Stocker l'info comme un réseau de nœuds reliés, au lieu d'une liste de morceaux récupérés par ressemblance |
| **RAG / vectoriel** | Ce que tu fais : retrouver les passages les plus *ressemblants* à la question, sans structure entre eux |
| **Harness** | La tuyauterie autour du modèle : outils, état, reprise sur erreur, observabilité |
| **MCP** | Le standard par lequel tes agents exposent leurs capacités à un autre agent |
| **HITL** | Human-in-the-loop : l'humain valide. Chez toi le manager décide, toujours |
| **Baseline naïve** | Le calcul bête (« comme mardi dernier ») qu'un vrai modèle doit battre pour mériter son coût |
| **Kappa de Cohen** | Mesure d'accord entre deux juges. Ton seuil : 0,8 avant de laisser un LLM noter seul |

---

*Networking 20:30 – 21:30. Si tu ne retiens qu'une chose : munition 1.*
