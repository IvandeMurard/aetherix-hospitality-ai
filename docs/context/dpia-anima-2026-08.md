# DPIA Anima — analyse de conformité RGPD/CNIL (gate Décision #20)

> **Statut du document :** analyse de conformité préalable. Livrable de l'Epic
> [HOS-229](https://linear.app/hospitalityagent/issue/HOS-229/epic-2-compliance-gate-rgpdcnil-dpia)
> (« Compliance Gate — RGPD/CNIL + DPIA »), DoD ligne 4 : *gate decision recorded in `docs/context/`*.
> **Date :** 01/08/2026 · **Auteur :** session Claude, sur cadrage Ivan de Murard.
>
> **Statut de la brique analysée** (taxonomie [`status-taxonomy.md`](status-taxonomy.md), Décision #33) :
> Anima = **Synthetic PoC**. Le traitement décrit ici **n'existe pas** : aucune donnée personnelle réelle
> n'a jamais transité par les quatre couches. Tout ce document est donc rédigé au **conditionnel** —
> il décrit ce qui *serait* traité si le build Phase 4 démarrait, et sous quelles conditions il pourrait
> démarrer. Une phrase au présent de l'indicatif sur le traitement Anima serait un drift.
>
> **Périmètre de la session qui a produit ce document :** analyse uniquement. Aucun schéma modifié,
> aucun ADR créé, aucun code écrit. Les conclusions qui remettent en cause l'architecture 4 couches
> sont **signalées au §10** et laissées à l'arbitrage d'Ivan — elles ne sont appliquées nulle part.

---

## 0. Ce que ce document est, et ce qu'il n'est pas

**Ce qu'il est.** Une analyse structurée selon l'article 35(7) RGPD et la méthode PIA de la CNIL,
appliquée à l'architecture Anima telle que spécifiée par la Décision #20, la Décision #26,
[`ADR-0011`](../adr/0011-learning-engine-hive-v2.md) et
[`mesh-architecture.md §2 Anima`](../mesh-architecture.md). Elle sert à répondre à une question
binaire : *le gate non-négociable de la Décision #20 peut-il être levé ?*

**Ce qu'il n'est pas.**

1. **Pas une DPIA signée.** Une DPIA est un acte du **responsable de traitement**, opposable, daté,
   revu par un DPO. Le responsable de traitement des données guest est **l'hôtel**, pas Aetherix
   (§2). Ce document est le matériau qu'Aetherix doit fournir à l'hôtel au titre de l'art. 28(3)(f),
   pas la DPIA de l'hôtel.
2. **Pas un avis juridique.** Aucun juriste ni DPO n'a relu ce texte. Plusieurs qualifications
   retenues ici (base légale du profilage durable, statut art. 9 des préférences alimentaires,
   frontière AI Act) sont défendables mais **contestables** — elles nécessitent une validation par
   un conseil avant tout engagement contractuel. Là où l'incertitude est réelle, elle est nommée.
3. **Pas définitif.** Une DPIA sur un système non construit est structurellement provisoire :
   elle décrit des flux de données spécifiés, pas observés. Elle **devra être refaite** sur le
   système réel avant mise en production (art. 35(11)), et le simple fait qu'elle soit
   pré-implémentation est en soi une limite de fiabilité.
4. **Pas une extension du Mesh.** Le plan 90 j gèle Anima
   ([`plan-90j-proof-visibility.md`](../planning/plan-90j-proof-visibility.md) §« Ce qu'on ne fait
   PAS »). Ce document ne conçoit rien : il conditionne. Il est le **préalable** posé par la
   Décision #20, pas une reprise du design.

---

## 1. La DPIA est-elle juridiquement obligatoire ?

Oui, et sans ambiguïté. Test des 9 critères EDPB (WP248 rév.01) — deux critères suffisent à
déclencher l'obligation de l'art. 35 :

| # | Critère WP248 | Anima | Justification |
|---|---|---|---|
| 1 | Évaluation / scoring | ✅ | `get_emotional_risk` → `risk_score` + `drivers`. C'est un score comportemental nominatif. |
| 2 | Décision automatisée à effet significatif | ⚠️ partiel | Décision #6 (human-in-the-loop) maintient l'humain dans la boucle. Mais l'usage cible — *« décider contextuellement sans baisser les prix »* — implique un **traitement différencié** guest par guest (geste commercial, surclassement, priorité d'intervention). Voir §5.3. |
| 3 | Surveillance systématique | ✅ | Observation continue du séjour : plaintes, humeur inférée, retards de vol, sentiment. |
| 4 | Données sensibles ou **hautement personnelles** | ✅ | L'état émotionnel inféré est « hautement personnel » au sens WP248 même s'il n'est pas art. 9 (§5.1). Et certaines claims *sont* art. 9 (§5.2). |
| 5 | Grande échelle | ✅ à terme | Mono-propriété au démarrage, mais la cible (multi-tenant, Hive prior cross-réseau) est explicitement à l'échelle. |
| 6 | Croisement de jeux de données | ✅ | PMS + CRM partenaire + API vol + reviews publiques + feedback Aetherix. Croisement par `guest_id` de sources collectées à des fins distinctes. |
| 7 | Personnes vulnérables | ⚠️ | Asymétrie structurelle client/exploitant ; possibilité de mineurs (« famille de 4 »), de personnes âgées, de données de santé incidentes. |
| 8 | Usage innovant | ✅ | Inférence émotionnelle par LLM, mémoire vectorielle, priors fédérés. |
| 9 | Fait obstacle à l'exercice d'un droit | ❌ | Non identifié. |

**6 critères pleins + 2 partiels.** L'obligation est établie plusieurs fois. Le gate de la
Décision #20 n'est donc pas une prudence maison : c'est une obligation légale. Corollaire utile
côté commercial — c'est un argument de sérieux, pas une contrainte à minimiser.

---

## 2. Qui est responsable de quoi — et le point qui coince

La [fiche prospect](perimetre-et-conformite-prospect.md) §Partie B pose la structure cible :
Aetherix = **sous-traitant** pour les données guest, **responsable** pour les coordonnées manager.
Cette structure tient pour Aetherix (nœud F&B). **Elle ne tient pas telle quelle pour Anima.**

| Traitement | Rôle Aetherix | Analyse |
|---|---|---|
| Couches Working / Episodic / Semantic, pour un hôtel | **Sous-traitant** | Finalités et moyens essentiels déterminés par l'hôtel ; Anima exécute sur instruction. Tient, sous réserve d'une DPA (art. 28) réelle. |
| Couche **Segment — portée locale** | Sous-traitant (limite) | Agrégats calculés sur les seules données d'une propriété, au bénéfice de cette propriété. Tient, tant que le résultat ne quitte pas la propriété. |
| Couche **Segment — Hive prior** (Phase 5) | **Responsable de traitement** (ou co-responsable) | ⚠️ Aetherix décide *seul* de la finalité (améliorer le produit cross-réseau), des moyens (embeddings metadata hôtel, partial pooling, seuils de divergence) et des bénéficiaires (les autres hôtels). Ce n'est plus de la sous-traitance : c'est un traitement propre d'Aetherix, alimenté par des données d'hôtels tiers. |
| **Store outcome** de-identified (ADR-0011 D4) | Responsable, si les données restent personnelles | Voir §10.2 : la qualification « personal-data-free by construction » est contestée. |

**Conséquence pratique.** Le passage à la fédération fait basculer Aetherix du statut de
sous-traitant à celui de responsable de traitement, avec tout ce que ça implique : base légale
propre, information des personnes, registre art. 30 en tant que responsable, réponse directe aux
demandes de droits, et responsabilité directe en cas de manquement. La DPA type prévue par la
Story 7.5 doit donc être **à deux étages** (sous-traitance opérationnelle + partage anonymisé
Hive avec base légale distincte et opt-out hôtel), et pas un modèle sous-traitant standard.

---

## 3. Description du traitement (art. 35(7)(a))

### 3.1 Finalités, par couche

| Couche | Finalité déclarée | Personnes concernées |
|---|---|---|
| **Working** | Réagir pendant le séjour à un événement en cours (vol retardé, plainte bruit, arrivée tardive) : geste opérationnel, ton du message, compensation. | Client hébergé |
| **Episodic** | Contextualiser les recommandations sur le séjour courant (+ queue courte) : upsell pertinent, late check-out, recommandation resto. | Client hébergé |
| **Semantic** | Reconnaissance inter-séjours et priorisation : profil durable, niveau de geste commercial, priorité d'intervention. | Client récurrent |
| **Segment (local)** | Prédire les besoins d'un client sans historique par cohorte de la propriété. | Ensemble des clients de la propriété |
| **Segment (Hive prior, Ph. 5)** | Idem, par priors appris sur le réseau d'hôtels. | Ensemble des clients du réseau |
| **Store outcome** (D4) | Apprentissage de politique : quelle action a produit quel résultat, dans quel contexte. | Indirectement, tous |

**Point de méthode.** Ces finalités doivent être écrites **séparément** dans le registre, avec
une base légale par finalité (§4). Les fusionner en une finalité unique — « améliorer
l'expérience client » — serait une finalité non déterminée au sens de l'art. 5(1)(b) : trop large
pour permettre à qui que ce soit d'exercer un droit d'opposition ciblé.

### 3.2 Catégories de données

Les exemples ci-dessous sont ceux de `mesh-architecture.md §2` — donc représentatifs de l'intention,
pas hypothétiques.

| Couche | Données citées dans la spec | Qualification |
|---|---|---|
| Working | « Vol retardé de 3 h · vient de se plaindre du bruit · arrivé fatigué » | Données de comportement + **état inféré** (« fatigué ») |
| Episodic | « 2× restaurant, **menu végétarien**, SPA mardi, demande oreillers » | Comportement + **préférence alimentaire → potentiellement art. 9** (§5.2) |
| Semantic | « VIP depuis 2023 · 12 séjours · sensible bruit · 19 °C · **anniversaire juin** · **famille de 4** » | Profil durable + date partielle de naissance + composition du foyer |
| Segment | « 73 % late check-out, F&B > SPA » | Agrégat — **anonyme sous condition** (§10.3) |
| Outcome | `(context-features, action, propensity, outcome)` + CSAT / plainte / repeat-booking | **Contesté** (§10.2) |
| Transverse | `confidence`, `evidence_count`, `last_confirmed`, `decay_rate` | Métadonnées d'inférence — également des données personnelles (elles portent sur une personne identifiée) |

### 3.3 Destinataires, sous-traitants ultérieurs, transferts

Chaîne à documenter intégralement dans la DPA **avant** tout build (art. 28(2) et (4) : chaque
sous-traitant ultérieur doit être autorisé et listé) :

| Maillon | Rôle | Point de vigilance |
|---|---|---|
| Supabase / PostgreSQL / pgvector | Stockage Episodic + Semantic | Région d'hébergement à figer en UE ; RLS ; chiffrement au repos |
| Upstash Redis | Working memory | Région UE ; **le TTL Redis est une éviction, pas une preuve d'effacement** (snapshots, réplicas, sauvegardes) |
| Fournisseur LLM (inférence émotionnelle) | Sous-traitant ultérieur **du cœur du traitement** | Transfert hors UE probable (chapitre V) → CCT/DPF à vérifier ; **rétention zéro et non-entraînement contractuels obligatoires** ; option résidence UE / déploiement auto-hébergé à instruire |
| Fournisseur d'embeddings | Vectorisation Semantic | Même analyse ; les embeddings dérivés de données personnelles **restent** des données personnelles |
| CRM partenaire (Duve / HiJiffy / Canary / Akia) | Source | Vérifier que la DPA de l'hôtel avec le CRM autorise la ré-exportation vers Anima ; sinon collecte hors base légale à la source |
| API vol (FlightAware ou équiv.) | Source | Le n° de vol est une donnée de localisation ; finalité et durée strictes |
| Reviews TripAdvisor / Booking | Source | Contenu public ≠ librement réutilisable ; le rattachement d'un avis à un `guest_id` est une **ré-identification** et change la nature du traitement |
| Fly.io (`cdg`) | Compute | Région UE — OK |

---

## 4. Nécessité et proportionnalité — base légale par finalité (art. 6)

C'est le point le plus faible de l'architecture actuelle : **aucune base légale n'est écrite nulle
part**. La Décision #20 dit « consentement explicite », `mesh-architecture.md` §Prérequis dit
« consentement explicite, retention policy, droit à l'oubli » — mais un consentement unique et
global pour les quatre couches ne serait pas valide (il ne serait ni spécifique, ni libre, si le
service en dépend).

| Finalité | Base proposée | Solidité | Analyse |
|---|---|---|---|
| Working — réaction opérationnelle pendant le séjour | **Contrat** art. 6(1)(b) *ou* **intérêt légitime** art. 6(1)(f) | Solide | Gérer une plainte bruit ou un vol retardé relève de l'exécution normale de la prestation d'hébergement. Attente raisonnable du client : oui. |
| Episodic — recommandation contextuelle | **Intérêt légitime** art. 6(1)(f) | Moyenne | Tient avec un test de mise en balance écrit + opt-out effectif. **Bascule si la recommandation devient de la prospection** : l'upsell ciblé est de la prospection commerciale → droit d'opposition **absolu** art. 21(2), et le canal (e-mail, WhatsApp) relève en plus d'ePrivacy. |
| Semantic — profil durable inter-séjours | **Consentement** art. 6(1)(a) | ⚠️ Faible en intérêt légitime | Un dossier émotionnel cumulé sur 12 séjours et plusieurs années **dépasse l'attente raisonnable** d'un client d'hôtel. L'intérêt légitime est ici difficilement défendable. Recommandation : consentement spécifique, granulaire, retirable, **découplé** de la réservation (sinon non libre), obtenu par l'hôtel et **propagé techniquement à Anima** — ce qui suppose un champ de consentement qui n'existe dans aucun schéma actuel. |
| Segment local | Intérêt légitime, puis **hors champ** si anonymisation prouvée | Moyenne | Le calcul de l'agrégat est un traitement ; son résultat sort du RGPD *seulement si* l'anonymisation résiste aux tests WP29 05/2014 (individualisation / corrélation / inférence). Voir §10.3. |
| Hive prior | **Intérêt légitime d'Aetherix** (responsable, §2) | À construire | Nécessite : test de mise en balance propre, information des personnes, opt-out par hôtel **et** plancher de k-anonymat (décision ouverte non tranchée). |
| Store outcome | Dépend de sa qualification | Contesté | Si personnel → base légale requise + droits applicables. Voir §10.2. |

### 4.1 Minimisation (art. 5(1)(c))

Ce que l'architecture fait déjà bien, et qu'il faut porter au crédit du design :

- **Le scope-gating est une mesure de minimisation, pas une optimisation de latence.** Le paramètre
  obligatoire `scope` de `query_guest_profile` impose au consommateur de déclarer quelle couche il
  interroge. C'est exactement ce que demande l'art. 5(1)(c). À valoriser comme tel dans la DPA.
- **`scope="all"` comme anti-pattern loggé** est le corollaire correct. Mais un warning **ne suffit
  pas** : à partir du moment où le scope est le mécanisme de minimisation, `"all"` doit être
  **refusé** par défaut et n'être ouvert que par autorisation explicite et tracée, sinon la mesure
  est déclarative. C'est un durcissement, pas un changement d'architecture.
- **La garde anti-god-object (D1)** — Anima ne décide pas, ne fédère pas — est aussi une mesure de
  séparation des finalités. Elle vaut d'être documentée en ces termes juridiques.

Ce qui manque : aucune règle ne dit **quelles** données ne doivent pas entrer. « Humeur inférée » est
une catégorie ouverte. Il faut une liste négative explicite (§9, M-3).

---

## 5. Profilage émotionnel : le cœur du risque

### 5.1 L'émotion inférée est-elle une donnée « sensible » au sens de l'art. 9 ?

**Non, pas en tant que telle** — et il faut être précis là-dessus, parce que la Décision #20 emploie
la formule « donnée personnelle sensible » et que cette imprécision peut se retourner contre le
projet dans les deux sens (sur-promesse de rigueur, ou fausse sécurité).

L'art. 9 est une **liste fermée** : origine raciale/ethnique, opinions politiques, convictions
religieuses/philosophiques, appartenance syndicale, données génétiques, biométriques
d'identification, de santé, vie/orientation sexuelle. « État émotionnel » n'y figure pas.

**Mais** :

- L'état émotionnel inféré est une donnée **hautement personnelle** au sens du WP248 (critère 4),
  ce qui déclenche la DPIA et un niveau d'exigence renforcé — sans le régime d'interdiction de l'art. 9.
- Il devient art. 9 **par ce qu'il révèle** : « déprimé », « anxieux », « en deuil », « fatigué de
  manière chronique » relèvent de la **santé**. La liste des `drivers` de `get_emotional_risk`
  (« fatigué », « déçu_précédent », « anniversaire_raté ») est aujourd'hui bénigne, mais rien dans
  l'architecture n'empêche un driver de santé d'y entrer — a fortiori si l'inférence est faite par
  un LLM en texte libre plutôt que par une énumération fermée.

**Conclusion opérationnelle :** l'ensemble des `drivers` doit être une **énumération fermée, revue
et validée**, pas une sortie libre de LLM. C'est la mesure la plus économique du document et elle
protège le régime juridique entier du système.

### 5.2 Les claims qui sont art. 9 dès aujourd'hui, dans les exemples de la spec

L'exemple Episodic de `mesh-architecture.md` contient **« menu végétarien »**. Une préférence
alimentaire enregistrée durablement peut révéler une conviction religieuse (halal, casher) ou une
donnée de santé (allergie, intolérance, régime médical). La CJEU retient une lecture large de la
révélation indirecte (C-184/20). Trois options, à arbitrer :

1. Ne stocker que le **fait opérationnel** sans sa cause (`menu_sans_viande` en préférence de
   service), en interdisant tout champ « raison ».
2. Traiter ces claims sous le **consentement explicite** de l'art. 9(2)(a), avec un cycle de vie séparé.
3. Les exclure de la couche Semantic (durable) et ne les autoriser qu'en Episodic (séjour + queue).

Aucune n'est gratuite ; toutes sont préférables au statu quo, qui stocke de façon permanente et
sans qualification une donnée potentiellement art. 9.

### 5.3 Article 22 — décision automatisée

La Décision #6 (pas d'auto-actions, human-in-the-loop) est la mesure qui met Anima hors du champ de
l'interdiction de l'art. 22(1), qui ne vise que les décisions **exclusivement** automatisées. Trois
réserves :

- L'intervention humaine doit être **effective** : un manager qui valide en un clic une
  recommandation qu'il ne peut pas contester ne constitue pas une intervention humaine au sens du
  WP251. La preuve d'effectivité doit être instrumentée (taux de rejet observé, possibilité de
  contre-décision, exposition des `drivers` au manager).
- L'usage cible — traitement différencié sans baisse de prix — produit une **discrimination de
  service** guest par guest fondée sur un score. Même hors art. 22, ça expose au risque équité :
  un score qui corrèle avec la nationalité, la langue ou le canal de réservation reproduira ce
  biais dans les gestes commerciaux. Un test d'équité doit être une condition de mise en production,
  pas une amélioration ultérieure.
- Si un jour le geste devient **tarifaire** (Phase 5, Revenue Orchestration), l'analyse art. 22
  change de nature : effet « significatif » beaucoup plus plaidable. À re-DPIA à ce moment-là.

### 5.4 AI Act (règlement (UE) 2024/1689) — où passe la frontière

Analyse à valider par un conseil, mais la ligne est nette :

- L'art. 3(39) définit un « système de reconnaissance des émotions » comme inférant les émotions
  **sur la base de données biométriques**. Anima infère à partir de texte, de comportement et
  d'événements logistiques → **hors définition**. Donc : ni Annexe III (haut risque), ni obligation
  de transparence de l'art. 50(3).
- L'art. 5(1)(f) interdit l'inférence d'émotions **sur le lieu de travail**. Ne vise pas les
  clients d'un hôtel. **Mais ça vise le personnel de l'hôtel** : si un signal de sentiment est un
  jour calculé sur un employé (via les feedbacks managers, les plaintes nominatives, les retours
  d'équipe), on tombe dans une pratique **interdite**, pas simplement réglementée. À poser comme
  ligne rouge écrite.
- **Le point de bascule à surveiller :** la vision Phase 5 « Aetherix Voice » ([`vision-future.md`](vision-future.md)).
  Dès qu'une émotion est inférée depuis la **voix**, on est sur de la donnée biométrique →
  art. 9 **et** Annexe III haut risque **et** art. 50(3). Le coût de conformité change d'ordre de
  grandeur. Ce n'est pas un problème aujourd'hui ; c'en est un le jour où les deux briques se
  rencontrent, et personne ne le verra venir si ce n'est pas écrit maintenant.

### 5.5 Le risque que `decay_rate` traite déjà

L'addendum du 20/07 à l'ADR-0011 (Grassi) nomme correctement le risque : une mémoire algorithmique
qui ne connaît « ni la grâce ni l'oubli » crée une asymétrie durable entre le système et la personne.
`decay_rate` est la réponse de design à ce risque, et c'est un vrai point fort — **à une condition
que le §7 détaille : la pondération n'est pas l'effacement.** Un `decay_rate` qui fait tendre la
confiance vers zéro sans jamais supprimer la ligne ne satisfait ni l'art. 5(1)(e) ni l'art. 17.
La grâce, ici, c'est un `DELETE`.

---

## 6. Durées de conservation par couche (art. 5(1)(e))

Le cœur de la commande. État actuel de la spec, problème, et proposition.

| Couche | Durée spécifiée | Problème | Durée proposée | Déclencheur | Mécanisme d'effacement |
|---|---|---|---|---|---|
| **Working** | « Durée du séjour » (TTL Redis) | « Durée du séjour » est un **événement**, pas une durée : que se passe-t-il en cas de no-show, de séjour prolongé, de check-out non enregistré ? Un TTL Redis est une éviction — il ne prouve rien sur les réplicas, snapshots et sauvegardes. | **Check-out + 24 h**, plafond dur **7 j** quel que soit l'état du séjour | Événement `check_out`, ou expiration du plafond | TTL **+** job de balayage des clés orphelines **+** politique de rétention des sauvegardes Redis alignée (≤ 7 j) |
| **Episodic** | « Séjour + 30 j » | Le 30 j n'est justifié nulle part. Il est en outre **incohérent** avec le 90 j retenu pour les données PMS brutes (Story 7.5, AC5) : deux durées pour des données qui décrivent le même séjour. | **Séjour + 30 j**, conservé mais **justifié** : fenêtre de réclamation/litige post-séjour. Aligner explicitement ou documenter l'écart avec le 90 j PMS | `check_out + 30 j` | Job `pg_cron` de suppression, **pas** d'archivage silencieux |
| **Semantic** | **∞ (permanent)** | ⚠️ **Non conforme en l'état.** « Permanent » est l'exact contraire de la limitation de conservation. Aucune finalité ne justifie une conservation illimitée d'un profil comportemental. `decay_rate` **pondère**, il ne supprime pas. | **36 mois glissants depuis le dernier séjour** (24 mois si la base est le consentement — alignement sur la doctrine CNIL prospection), prolongeable par re-consentement explicite | `last_stay_date + 36 mois`, ou retrait du consentement (immédiat) | Suppression de la ligne **et du vecteur** pgvector ; purge du cache d'embeddings ; cascade §8 |
| **Segment (local)** | ∞ | Acceptable **uniquement si** l'agrégat est réellement anonyme. Un k-means nocturne sur les clients d'une seule propriété, avec cohortes potentiellement petites, ne l'est pas par défaut (§10.3). | **Aligné sur Semantic (36 mois)** — arbitrage HOS-323 du 01/08 : aucun anonymat revendiqué, donc la couche reste dans le régime données personnelles | Recompute nocturne | Recompute avec plancher **k = 20** + garde de concentration ~90 % ; sous le seuil, **dégradation vers une cohorte plus grossière** (jamais un k plus bas) |
| **Segment (Hive prior)** | ∞ (Phase 5) | Idem, aggravé : agrégation cross-propriétés sous responsabilité Aetherix (§2). | ∞ sous les mêmes conditions **+** opt-out hôtel effectif rétroactivement | — | Recalcul du prior à l'exclusion de l'hôtel sorti — **techniquement non trivial**, à prévoir dès le design |
| **Store outcome** (D4) | Non spécifiée | Une rétention non spécifiée sur un store dont la nature juridique est contestée (§10.2) est le pire des deux mondes. | À spécifier explicitement, bornée par le besoin d'apprentissage (proposition : **24 mois**), et **re-qualifiée** avant toute décision | — | Suppression ou ré-agrégation |

**Trois principes transverses à écrire quelque part :**

1. **Une durée par couche, pas une durée par système.** C'est précisément ce que la séparation
   temporelle en 4 couches rend possible — c'est son meilleur argument de conformité et il faut le
   dire ainsi : *l'architecture 4 couches est une mesure de protection des données, pas seulement
   une optimisation de latence.*
2. **`decay_rate` ≠ effacement.** Les deux sont nécessaires : la pondération sert la qualité de
   l'inférence (art. 5(1)(d), exactitude) ; la suppression sert la limitation de conservation
   (art. 5(1)(e)). Confondre les deux serait l'erreur la plus coûteuse de ce dossier.
3. **Les sauvegardes font partie de la durée de conservation.** Un profil supprimé en base mais
   présent dans 90 j de snapshots Supabase n'est pas supprimé. La politique de sauvegarde doit être
   documentée et bornée dans la DPA.

---

## 7. Droits des personnes (art. 12 à 22)

Un tableau de faisabilité, couche par couche, plutôt qu'une déclaration d'intention. La colonne
« état » qualifie l'architecture spécifiée, pas un système existant.

| Droit | État | Ce qui manque |
|---|---|---|
| **Information** (12-14) | ❌ Absent | Le client n'interagit jamais avec Anima ; il ignorerait son existence. Il faut une notice en deux niveaux fournie **par l'hôtel** : mention courte à la réservation/check-in + notice complète mentionnant nommément l'inférence d'état émotionnel, la logique du profilage et les durées du §6. Une notice qui tait le mot « émotionnel » serait une information incomplète. |
| **Accès** (15) | ⚠️ Partiel | `ProfileSnapshot` rend l'export techniquement facile — c'est un point fort. Deux difficultés : (a) l'art. 15(1)(h) impose de communiquer *la logique sous-jacente* du profilage ; (b) restituer `risk_score: 0.8, drivers: [déçu_précédent, fatigué]` est juridiquement dû et humainement délicat. Ça se prépare (formulation, contextualisation), ça ne se contourne pas. |
| **Rectification** (16) | ❌ **Absent par construction** | L'architecture n'a **aucun chemin de rectification**. Les claims sont dérivées d'observations ; rien ne permet à une personne de contester « sensible bruit » ou « déçu précédemment ». Or une inférence erronée est une donnée inexacte au sens de l'art. 5(1)(d). Il faut un mécanisme de claim contestée/verrouillée qui **survive au recompute nocturne** — sinon la rectification est écrasée à la nuit suivante. |
| **Effacement** (17) | ⚠️ Conçu, non prouvé | La cascade doit atteindre : Redis (+ sauvegardes), PostgreSQL Episodic, **pgvector Semantic (ligne *et* vecteur)**, les nodes `Guest`/`Stay`/`Sentiment` réservés par l'ADR-0008, les agrégats Segment (recompute), le store outcome (si personnel), et les logs. La NFR1 de HOS-229 le pose ; rien ne le démontre. Une DSAR non tenue dans les délais est un manquement, pas un bug. |
| **Limitation** (18) | ❌ Absent | Aucune notion d'état « gelé » dans le modèle. |
| **Portabilité** (20) | ⚠️ | Ne s'applique qu'aux bases consentement/contrat, donc à Semantic si le §4 est suivi. `ProfileSnapshot` en JSON répond au format ; les inférences propres au système n'entrent pas dans le champ (fournies par le responsable, non « fournies par la personne »). |
| **Opposition** (21) | ❌ Absent | Point critique : l'opposition doit être honorée **à la lecture**, pas seulement à l'écriture. Un client opposé dont les données restent interrogeables par `query_guest_profile` n'est pas protégé. Il faut un drapeau d'exclusion évalué **côté serveur, dans le chemin de requête**, pour les 4 couches et les agrégats. Et pour la prospection (art. 21(2)), le droit est **absolu** : aucun test de mise en balance. |
| **Non-soumission à décision automatisée** (22) | ✅ sous condition | Couvert par Décision #6, sous les réserves du §5.3. |

---

## 8. Analyse des risques (art. 35(7)(c))

Méthode CNIL : trois événements redoutés, plus les risques spécifiques au profilage.
Gravité et vraisemblance évaluées **pour le système cible**, pas pour le PoC synthétique.

| # | Risque | Gravité | Vraisemblance | Commentaire |
|---|---|---|---|---|
| R1 | **Accès illégitime** à un profil émotionnel (fuite, accès interne, erreur de tenant) | **Maximale** | Moyenne | Un dossier « VIP, s'est plaint, déçu, anxieux, famille de 4 » est un document intime. Fuite = préjudice moral direct, non réparable. Le RLS et le `hotel_id` server-side atténuent le cross-tenant, pas l'accès interne. |
| R2 | **Fuite inter-couches** (`scope="all"`, jointure applicative) | Importante | Moyenne | Le scope-gating est la mesure ; elle est aujourd'hui **déclarative** (warning) et non contraignante. |
| R3 | **Ré-identification** depuis Segment ou Hive | Importante | Moyenne-haute | Cohortes petites en mono-propriété ; plancher de k-anonymat non tranché (décision ouverte). §10.3. |
| R4 | **Inférence erronée durable** (« déçu », « difficile ») orientant le service pendant des années | Importante | **Haute** | Aucun chemin de rectification (§7) ; `decay_rate` ralentit, n'annule pas. Risque le plus probable de tous. |
| R5 | **Discrimination de service** — le score corrèle avec nationalité/langue/canal | Importante | Moyenne | Aucun test d'équité prévu. §5.3. |
| R6 | **Asymétrie mémorielle** — le système sait mieux que la personne ne se souvient | Modérée à importante | Haute si rétention ∞ | Risque nommé par l'addendum ADR-0011 ; traité par decay **et** rétention bornée (§6), pas par decay seul. |
| R7 | **Exposition à un sous-traitant LLM** — le prompt d'inférence contient le contexte guest | Importante | Haute | Chaque appel d'inférence exporte des données personnelles vers le fournisseur. Rétention zéro + non-entraînement + région = obligatoires, contractuellement, pas par confiance. |
| R8 | **Émotion inférée sur le personnel** | **Maximale** (pratique interdite) | Faible mais non nulle | AI Act art. 5(1)(f). Le feedback manager d'Aetherix arrive déjà dans Anima comme source (§3.3) ; la frontière est plus fine qu'elle n'en a l'air. |
| R9 | **Modification non désirée** (corruption d'un profil, mauvais `guest_id`) | Importante | Moyenne | Le PoC a documenté un alias `guest-0001`→`G001` : les collisions d'identifiants inter-nœuds sont un risque réel, pas théorique. |
| R10 | **Disparition** (perte de données) | Faible | Faible | Impact opérationnel, pas de préjudice direct pour la personne. |
| R11 | **Consentement invalide** (groupé avec la réservation, non retirable, non propagé) | Importante | Haute en l'absence de design | Si Semantic repose sur un consentement non valide, **toute la couche est illicite** — et pas seulement inconforme. |

---

## 9. Mesures (art. 35(7)(d))

Séparées en ce qui existe et ce qui reste à construire. Aucune de ces mesures n'est implémentée
ici — ce sont des conditions, pas des livrables.

### 9.1 Ce qui existe déjà et compte comme mesure

| Mesure | Risques couverts | Source |
|---|---|---|
| Séparation temporelle en 4 couches | R2, R6 | Décision #20 |
| `scope` obligatoire sur `query_guest_profile` | R2 | Décision #20 |
| Garde anti-god-object : Anima informe, l'Orchestrateur décide | R5, art. 22 | ADR-0011 D1 |
| Human-in-the-loop (pas d'auto-actions) | art. 22, R5 | Décision #6 |
| `decay_rate` / `confidence` / `last_confirmed` | R4, R6 | ADR-0011 D2 |
| RLS multi-tenant (14 tables), `hotel_id` server-side, HMAC webhooks | R1 | Décision #30, audit Q2 |
| Posture sandbox / non-PII maintenue | tous | Décision #30 |

### 9.2 Ce qui doit être construit avant tout traitement réel

| Réf. | Mesure | Risque | Nature |
|---|---|---|---|
| M-1 | Rétention bornée sur Semantic (36 mois glissants) + jobs de suppression réels sur les 4 couches | R6, art. 5(1)(e) | **Bloquante — touche la spec (§10.1)** |
| M-2 | `scope="all"` **refusé** par défaut, autorisation explicite et tracée ; journal d'audit de toute requête (qui, quel scope, quelle finalité) | R2 | Bloquante |
| M-3 | Énumération **fermée** des `drivers` ; liste négative des catégories interdites (santé, religion, opinions, orientation) ; filtre en entrée **et** en sortie de LLM | R1, art. 9 | Bloquante |
| M-4 | Design du consentement : granulaire par finalité, retirable, découplé de la réservation, **propagé jusqu'à Anima** et évalué à la requête | R11 | Bloquante |
| M-5 | Chemin de rectification + claim verrouillée survivant au recompute | R4 | Bloquante |
| M-6 | Drapeau d'opposition évalué **côté serveur dans le chemin de lecture**, 4 couches + agrégats | R5, art. 21 | Bloquante |
| M-7 | DSAR de bout en bout **testée** (accès + effacement), incluant vecteurs pgvector, nodes graphe et sauvegardes | R1, art. 15/17 | Bloquante |
| M-8 | Plancher de k-anonymat tranché et **appliqué au recompute** ; opt-out hôtel rétroactif sur Hive | R3 | Bloquante avant Segment prod |
| M-9 | Contrats sous-traitants LLM/embeddings : rétention zéro, non-entraînement, région ; chaîne art. 28(4) complète | R7 | Bloquante |
| M-10 | Ligne rouge écrite : **aucune inférence émotionnelle sur le personnel** ; **aucune entrée biométrique** (voix, visage) sans nouvelle DPIA | R8, AI Act | Bloquante (écriture) |
| M-11 | Notice d'information en deux niveaux, fournie par l'hôtel, nommant l'inférence émotionnelle | art. 12-14 | Bloquante |
| M-12 | DPA à deux étages (sous-traitance + Hive responsable) — cf. §2 | art. 28 | Bloquante |
| M-13 | Test d'équité du score (corrélation avec nationalité/langue/canal) avant prod | R5 | Bloquante |
| M-14 | `DPO_EMAIL` provisionné ; registre art. 30 tenu des deux côtés (sous-traitant + responsable) | art. 30/37 | Administrative |
| M-15 | Politique de sauvegarde bornée et documentée (Redis + Supabase) | R1, §6 | Technique |

---

## 10. Conclusions qui remettent en cause l'architecture — signalées, non modifiées

> Conformément au cadrage : ces quatre points sont des **constats**, portés à l'arbitrage d'Ivan.
> Aucun document d'architecture n'a été modifié, aucun ADR n'a été créé.

### 10.1 La couche Semantic est spécifiée « permanente, TTL ∞ » — c'est non conforme

Décision #20 et `mesh-architecture.md §2` définissent Semantic comme « pgvector (permanent) · TTL ∞ ».
Aucune analyse de proportionnalité ne peut justifier une conservation illimitée d'un profil
comportemental et émotionnel. Ce n'est pas un détail de paramétrage : la permanence est présentée
comme une **propriété de la couche**, ce qui la distingue des trois autres.

**Ce que ça implique, à l'arbitrage :** soit la couche Semantic reçoit une durée bornée — et la
définition de la couche change (« permanent » devient « durable, borné, glissant ») — soit Anima ne
peut pas traiter de données réelles. Il n'y a pas de troisième voie. Le coût du design est faible
(un champ `last_stay_date` + un job) ; c'est la **description** de l'architecture qui doit bouger,
pas nécessairement son code.

Note : `decay_rate` a probablement créé l'illusion que la question était traitée. Elle ne l'est pas —
la pondération et l'effacement sont deux obligations distinctes (§5.5, §6).

### 10.2 La qualification « personal-data-free by construction » du store outcome est contestable

L'ADR-0011 D4 affirme que le triple `(context-features, action, propensity, outcome)` est
« de-identified », « aucun champ identifiable », et que la fédération « opère entièrement au-dessus
de la ligne personal-data ». C'est l'argument qui permet à la fédération d'échapper au régime RGPD.

Il est fragile. L'absence d'identifiant direct ne fait pas l'anonymat (considérant 26 + WP29 05/2014 :
il faut résister à l'**individualisation**, la **corrélation** et l'**inférence**). Or le triple
combine : un vecteur de features de contexte potentiellement fin, un horodatage implicite, une
propriété, et un outcome. Dans un hôtel de taille moyenne, un jour donné, « segment X + situation Y +
action Z + plainte » peut **individualiser** une personne — surtout joint aux données que l'hôtel
détient par ailleurs, ce qui est le test pertinent (moyens raisonnablement susceptibles d'être
utilisés, *par quiconque*, pas seulement par Aetherix).

**Ce que ça implique :** si le store est pseudonyme et non anonyme, alors il porte des données
personnelles, il lui faut une base légale, une durée, et il entre dans le périmètre des demandes
d'effacement — ce que D4 exclut explicitement en le posant « séparé d'Anima ». Ce n'est pas fatal :
c'est une **preuve à produire** (analyse de ré-identification, granularité maximale des
`context-features`, agrégation temporelle, plancher de cohorte), pas une affirmation à poser dans un
ADR. Tant que la preuve n'existe pas, la position par défaut doit être « pseudonyme ».

### 10.3 La couche Segment est présentée comme anonyme sans plancher de k-anonymat tranché

« Aggregations anonymisées », « k-means nocturne ». Le plancher de k-anonymat est encore une
**décision ouverte** (`open-decisions.md`, « Floor k-anonymat couche Segment — avant build Segment
production »). Or l'anonymat de la couche est ce qui la sort du RGPD et ce qui rend la fédération
défendable.

**Ce que ça implique :** l'ordre est inversé. Le plancher n'est pas un paramètre à régler avant le
build — c'est le **prérequis qui détermine si la couche 4 est un traitement de données personnelles
ou pas**, donc si elle est dans le périmètre de la DPIA, des droits et des durées. Il devrait être
tranché ici, avant, et pas à la construction.

> ✅ **Tranché le 01/08/2026** (HOS-323, arbitrage Ivan) — `open-decisions.md` §Resolved.
> **k = 20** clients par cohorte · **garde de concentration** : un attribut homogène au-delà de ~90 %
> n'est pas servi (k-anonymat seul ne protège pas des **attributs** — attaque par homogénéité, d'où
> la l-diversité ; k=5 vaut pour des comptages, pas pour « 73 % late check-out ») · sous le seuil,
> **dégradation vers une cohorte plus grossière**, jamais un k plus bas.
>
> **Et surtout : aucun anonymat n'est revendiqué.** La couche 4 reste dans le régime des données
> personnelles. Motif assumé — aucune relecture juridique n'est finançable à ce stade, et l'anonymat
> est la qualification la plus lourde du dossier. On ne s'appuie pas sur une qualification qu'on ne
> peut pas faire valider ; la revendiquer à tort coûte bien plus que ne pas la revendiquer, et
> s'en abstenir ne coûte **rien aujourd'hui** puisque la couche n'est pas construite. La
> revendication reste ouverte plus tard, adossée à une analyse de ré-identification et à la
> relecture du DPO du design-partner — à qui la DPIA appartient de toute façon (§2).

À noter que la Décision #24 (graphe de contexte) désignait déjà `Cohort` comme la **frontière
d'anonymisation** — la frontière est identifiée dans le corpus, mais elle n'a jamais été chiffrée.

### 10.4 La fédération fait sortir Aetherix du statut de sous-traitant

Développé au §2. La fiche prospect présente une structure simple (Aetherix sous-traitant pour les
données guest). Dès la Phase 5 / Hive prior, ce n'est plus exact. Ce n'est pas une objection au
design — c'est une **conséquence contractuelle et documentaire** que la DPA type doit absorber, et
qu'il vaut mieux découvrir maintenant qu'en due diligence d'un acheteur.

**Ce qui n'est pas remis en cause :** la séparation en 4 couches temporelles elle-même est, du point
de vue de la protection des données, la meilleure décision du dossier. Elle rend possible une durée
par finalité, un scope-gating, et une minimisation opposable. Aucune des conclusions ci-dessus ne
suggère de revenir à un modèle mono-couche — au contraire, trois d'entre elles reprochent à
l'architecture de ne pas aller **assez loin** dans la logique qu'elle a elle-même posée.

---

## 11. Verdict du gate (Décision #20)

**Le gate n'est pas levé.**

Ce qui est acquis : l'obligation de DPIA est établie (§1), le traitement est décrit (§3), les bases
légales sont identifiées avec leurs faiblesses (§4), les risques sont caractérisés (§8), et les
mesures nécessaires sont listées et priorisées (§9). C'est le matériau d'entrée d'une DPIA. Ce n'est
pas une DPIA opposable, et ça ne le sera jamais tant que quatre choses manqueront :

1. **Une relecture par un conseil / DPO.** Trois qualifications structurantes en dépendent : base
   légale de Semantic, statut art. 9 des préférences alimentaires, frontière AI Act.
   **Contrainte assumée (01/08/2026) : aucune relecture juridique n'est finançable à ce stade.**
   Elle n'est pas abandonnée, elle est **déplacée sur W5** : la DPIA appartient au responsable de
   traitement, donc à l'hôtel, qui a un DPO ou un conseil — la faire relire par lui est d'ailleurs
   plus crédible que de la faire relire par le sien. En attendant, la posture par défaut est
   **conservatrice partout où une qualification ne peut pas être validée** — c'est le raisonnement
   qui a produit l'arbitrage HOS-323 (aucun anonymat revendiqué, §10.3). Appuis gratuits qui
   sécurisent la forme sans remplacer l'avis : guide PIA et logiciel PIA de la CNIL, cliniques
   juridiques universitaires, heures juridiques d'incubateur.
2. **Les quatre arbitrages du §10.** Deux d'entre eux (rétention Semantic, plancher k-anonymat)
   déterminent le périmètre même du traitement — on ne peut pas finaliser une DPIA sans eux.
3. **Les 13 mesures bloquantes du §9.2** conçues, pas seulement listées.
4. **Le responsable de traitement.** La DPIA appartient à l'hôtel. Il n'y a pas d'hôtel : zéro
   design-partner à ce jour. Une DPIA sans responsable identifié est un exercice, pas un acte.

### Conditions de levée, dans l'ordre

| # | Condition | Dépend de |
|---|---|---|
| C1 | Arbitrage des 4 points du §10 (Ivan) | — |
| ~~C2~~ | ~~Plancher de k-anonymat tranché et chiffré~~ — ✅ **fait 01/08/2026** (HOS-323 : k=20, garde de concentration, aucun anonymat revendiqué, dégradation vers cohorte plus grossière) | — |
| C3 | Durées de conservation §6 actées comme spec, y compris la rétention bornée de Semantic | C1 |
| C4 | Design consentement + opposition + rectification (M-4, M-5, M-6) | C3 |
| C5 | `docs/GDPR-DATA-INVENTORY.md` livré (Story 7.5, non fait) — préalable factuel, Anima ne peut pas être conforme si Aetherix n'a pas son propre inventaire | Story 7.5 / HOS-115 |
| C6 | DPA à deux étages rédigée | §2 · C5 |
| C7 | Un design-partner identifié, responsable de traitement, qui adopte la DPIA | pilote réel |
| C8 | Relecture juridique — **portée par le DPO / conseil du design-partner**, non finançable en propre | C7 |
| C9 | DSAR testée de bout en bout sur le système réel | build |

**Séquencement par rapport au gel Epic 16.** C1, C2 et C3 sont des décisions, pas du build : elles
tiennent en une session d'arbitrage et ne consomment pas d'heures de preuve. C4 à C9 sont du travail
Phase 4 et **doivent rester gelés** — les entamer maintenant serait exactement le design fiction que
le plan 90 j proscrit. La lecture honnête : ce document rend le gate *documenté*, il ne le rend pas
*franchissable*, et il n'y a aucune raison de vouloir le franchir avant qu'un hôtel réel existe.

---

## 11 bis. Les 5 murs — ce que le discours ne franchit pas

> Ajouté le 01/08/2026 après revue. Le reste du document se règle par spécification et par build ;
> ces cinq points-là, non. Ils sont classés par **ce qui les débloque**, pas par difficulté — c'est
> le critère qui décide s'ils rentrent dans le sprint courant ou s'ils restent gelés.

| # | Mur | Pourquoi il ne se reformule pas | Débloqué par | Placement |
|---|---|---|---|---|
| **W1** | **Rectification d'une inférence** — une personne doit pouvoir contester « sensible bruit » ou « déçu précédemment », et la contestation doit survivre au recompute nocturne | Un droit sans mécanisme est une phrase. Ici il n'existe **aucun** chemin : les claims sont dérivées, jamais amendables | Design (M-5) | 🔒 Phase 4 — gelé |
| **W2** | **Anonymat de Segment et du store outcome** | Propriété empirique. Aucune formulation ne rend anonyme une cohorte de 4 personnes | Un **chiffre** (plancher k) + une analyse de ré-identification | ✅ **Chiffre tranché 01/08** (k=20 + garde, aucun anonymat revendiqué — HOS-323) · 🔒 la preuve reste à produire |
| **W3** | **Consentement libre pour Semantic** — donc découplé de la réservation | Contrainte commerciale imposée à l'hôtel, pas une clause à rédiger. Un consentement groupé avec la résa est nul, quelle que soit sa rédaction | Négociation design-partner | 🔒 Phase 4 — dépend de W5 |
| **W4** | **DSAR testée de bout en bout** (accès + effacement, incluant vecteurs pgvector et sauvegardes) | Un test passe ou ne passe pas. C'est le seul point du dossier qui produit une preuve binaire | Build (M-7) | 🔒 Phase 4 — gelé |
| **W5** | **Aucun responsable de traitement n'existe** — zéro design-partner | La DPIA appartient au responsable. Sans hôtel, ce document reste un exercice | Recrutement design-partner (Epic 16) | 🟠 **Déjà dans le plan actif** — c'est la dépendance racine |

**Lecture de la priorisation.** Un seul de ces cinq murs entre dans le sprint courant : le
**chiffre** de W2, parce que c'est une décision et non du build — elle coûte une session d'arbitrage
et elle conditionne le périmètre juridique de la couche 4. W5 est déjà le cœur du plan 90 j sous un
autre nom. W1, W3 et W4 sont du travail Phase 4 et **doivent rester gelés** : les entamer maintenant
serait le design fiction que le plan proscrit, et W3 comme W4 sont de toute façon indécidables sans
W5.

**Le piège à nommer.** Quatre de ces cinq murs ne se voient pas en lisant la documentation — ils ne
se révèlent qu'au moment où quelqu'un teste. C'est exactement ce qu'un DPO d'acheteur teste en
premier, et c'est la raison pour laquelle « c'est surtout sémantique » est une lecture dangereuse du
reste du document : les 70 % solubles par rédaction et par build sont réels, mais ce sont les 30 %
restants qui décident si Anima est déployable.

---

## 12. Suites

- **À arbitrer par Ivan** : les 4 points du §10. S'ils sont retenus, ils appellent un amendement de
  la Décision #20 (durées) et une note dans `open-decisions.md` (k-anonymat) — **non faits ici**,
  volontairement.
- **À ne pas faire maintenant** : DPA, inventaire, consentement, code. Gel Epic 16.
- **À relire avant tout contact prospect sur Anima** : §5.1 — la formule « donnée personnelle
  sensible » de la Décision #20 est juridiquement imprécise. « Donnée hautement personnelle, sensible
  au sens du WP248, et sensible au sens de l'art. 9 lorsqu'elle révèle la santé ou une conviction »
  est exact et plus solide.
- **À revoir** : ce document, dans son intégralité, avant toute mise en production (art. 35(11)).

Voir aussi : [`decisions-architecturales.md`](decisions-architecturales.md) §20 et §26 ·
[`ADR-0011`](../adr/0011-learning-engine-hive-v2.md) · [`mesh-architecture.md`](../mesh-architecture.md) §2 ·
[`perimetre-et-conformite-prospect.md`](perimetre-et-conformite-prospect.md) ·
[`status-taxonomy.md`](status-taxonomy.md) · [`security-review-2026-Q2.md`](security-review-2026-Q2.md)
