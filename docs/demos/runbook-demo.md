# Runbook démo Aetherix — entretien du 06/11/2026, 15:30 (visio)

> Demande : « quelques minutes sur un cas métier concret : le problème de départ, ce qui fonctionne
> aujourd'hui, ce que vous avez construit vous-même avec Claude Code, et les limites à lever avant un
> pilote. Des données fictives conviennent très bien. »
>
> Principe : **la démo ne dépend d'aucun service cloud.** Fly, Supabase, Twilio et Apaleo sont des
> bonus. Les deux scripts ci-dessous tournent en local, sans réseau, sur le code de production.

---

## 1. Déroulé (7 min, calqué sur les 4 points demandés)

| Temps | Point | À l'écran | À dire (l'essentiel) |
|---|---|---|---|
| 0:00 | **Problème** | `fiche-aetherix.md` | Mardi 14 h, la responsable F&B d'un hôtel indépendant doit décider si elle ajoute un extra pour le dîner de mercredi, avant l'heure limite du planning. Aujourd'hui elle le fait de tête (moyenne des 4 derniers mercredis). Trop de staff = coût, pas assez = service dégradé. |
| 0:45 | **Ce qui marche — la boucle** | `demo_whatsapp_conversation.py` | Une recommandation par jour. La réponse du manager est lue de façon **déterministe d'abord** (lexique, commandes) ; le modèle ne lit que ce que le lexique ne sait pas, sa sortie est validée par schéma, et sous 0,85 de confiance **rien n'est écrit sans un « oui »**. Une question n'est jamais une décision. Tout finit dans un registre de décisions, avec qui a décidé et comment. |
| 2:15 | **Ce qui marche — apprendre sans dériver** | `closed_loop_demo.py` | 30 jours simulés, choc de demande +25 % au jour 15 : erreur 15,6 % → 12,1 % après recalibration hebdomadaire. Un réel aberrant (900 couverts pour 120 places) est rejeté par une borne (G-3) au lieu d'être appris. Les règles d'effectif apprises ne s'appliquent qu'après approbation d'une personne nommée. |
| 3:15 | **Prévision sur données réelles** | `docs/context/mape-benchmark.md` | Kaggle Recruit (restaurants réels) : Prophet bat la baseline naïve en moyenne (MAPE 49,7 % vs 55,9 %) mais **fait jeu égal en médiane** (27,0 vs 27,6 %) et est **derrière à J+1** (28,5 vs 27,9 %). J'ai déclenché moi-même la clause de pivot : la valeur n'est pas le modèle, c'est la boucle de décision. |
| 4:00 | **Construit avec Claude Code** | Linear HOS-357 → PR #298 → CI | Une story : contexte d'audit, périmètre tranché et daté par moi, critères d'acceptation, cas golden ajoutés, gate d'éval bloquant. Puis 2 corrections où la mesure a contredit l'IA (§3). |
| 5:30 | **Limites avant pilote** | §4 | 0 utilisateur ; qualité du modèle de lecture non mesurée sur modèle réel ; réels déclarés par le manager (pas de POS) ; templates WhatsApp non approuvés ; défense prompt-injection différée ; staging arrêté. |
| 6:30 | Ouverture | — | Ce qui se transpose chez vos clients : éval dès la conception, humain dans la boucle sur l'irréversible, étiquetage honnête (Built / Synthetic / Design), livrer dans les outils du client plutôt qu'un dashboard. |

**Vidéo de secours** : enregistrer les deux scripts le 06/11 au matin (3 min, mention « données fictives, boucle réelle »). Elle ferme HOS-310 AC3.

## 2. Commandes (Windows, depuis la racine du repo)

```powershell
cd backend; uv sync; cd ..
backend\.venv\Scripts\python scripts\ops\demo_whatsapp_conversation.py
backend\.venv\Scripts\python scripts\ops\closed_loop_demo.py --days 30 --out eval\reports\closed_loop_demo.json
```

Avec le **modèle réel** (recommandé si une clé valide existe ; sinon les lignes affichent `SCRIPTÉ`) :

```powershell
$env:ANTHROPIC_API_KEY="..."; backend\.venv\Scripts\python scripts\ops\demo_whatsapp_conversation.py --model claude:claude-haiku-4-5-20251001
```

Répéter une fois le mode réel avant l'entretien : un modèle réel peut lire « bof, ça me paraît beaucoup »
autrement que le script. C'est un bon moment de démo (confiance → confirmation), pas un incident.

Ce que montre `demo_whatsapp_conversation.py` (une semaine, Hôtel Kléber fictif) :

| Réponse du manager | Chemin | Ce qui est écrit |
|---|---|---|
| `ok` | accusé simple, 1 reco en attente, < 12 h | validation (`bare_ack_rule`) |
| `pas besoin` + raison | lexique de positions | refus ; la raison est stockée à part, ne change jamais la décision |
| `mets-en 3 de plus` | modèle → `counter_value`, chiffre lu sans modèle | correction, effectif retenu = 3, cité en retour |
| `pourquoi ?` | question | explication, **aucune** décision |
| `bof, ça me paraît beaucoup` | modèle, confiance 0,6 | rien avant « oui » → refus `model_confirmed` |
| `corriger mardi refus` + `oui` | commande, confirmation | décision remplacée (`manager_revision`) |
| `recap semaine` | gabarit déterministe, sans LLM | récap : 4 reçues, écart prévision/réel sur 3 jours mesurés |

## 3. « Construit avec Claude Code » — les preuves à montrer

1. **Story HOS-357** (Linear, cases cochées après vérification le 05/11) → PR #298 → tests + 6 cas golden
   `parser-question-*`. Montre : décision produit datée (« une question n'est jamais une décision »),
   critères vérifiables, gate d'éval, et la phrase honnête « validation manuelle non faisable ».
2. **Quand la mesure a contredit l'IA** :
   - baseline parser à 1,0 = **circulaire** (le faux classifieur était noté contre lui-même) → supprimée (Décision #37) ;
   - MAPE synthétique 15,09 % = **circulaire** (données générées avec les régresseurs de Prophet) → gate interne seulement (Décision #33) ;
   - page `/dashboard` qui affichait « Live from Apaleo » avec des chiffres codés en dur → supprimée (HOS-355) ;
   - 05/11 : le run hebdomadaire « modèle réel » affichait FAIL 0 % alors que la clé API était invalide → corrigé en NON MESURÉ (commit `b5541a8`).
3. **BMAD** : montrer `tools/bmad/_bmad-output/implementation-artifacts/` (une story → son fichier) et ce que
   j'ai **ajouté** à la méthode (éval dès la conception, taxonomie de statuts) et **coupé** (Décision #24, gel Epic 16).
   Ne pas dérouler les personas.

## 4. Limites avant pilote (à dire avant qu'on les demande)

| Limite | État | Ce qui la lève |
|---|---|---|
| 0 utilisateur réel | aucun hôtel | design partner + protocole de preuve gelé (`docs/planning/protocole-de-preuve.md` : Δ MdAPE ≥ 5 pp, acceptation ≥ 30 %) |
| Lecture des réponses par le modèle | non mesurée sur modèle réel (secret GitHub invalide) | HOS-342 : run réel Claude + Gemini, baselines figées |
| Réels | déclarés par le manager (`independent_actuals: false`) | POS (Epic 13) |
| Texte de la recommandation | en anglais (`format_message`) alors que la conversation est en français | traduire le formatter |
| WhatsApp | templates non approuvés, boutons derrière un flag | soumission Meta (catégorie Utility) |
| Prompt-injection | G-6 différé (HOS-114, HOS-253) | durcissement du chemin texte libre |
| Données guest (Anima) | gate DPIA fermé, 13 mesures bloquantes | rien avant ces mesures |
| Staging | arrêté (essai Fly expiré) | §5 |

## 5. Relancer l'environnement (optionnel pour la démo)

Ordre : **Supabase → Fly → Twilio → Apaleo.** Chaque étape a son test de sortie.

### 5.1 Supabase
1. Dashboard Supabase → le projet. Un projet gratuit inactif est mis en pause après 7 jours ; il se restaure
   depuis le dashboard **pendant 90 jours seulement**, ensuite seule la sauvegarde est téléchargeable.
2. Si « Restore » est proposé → restaurer. Sinon → nouveau projet (région EU), extension `vector`, puis appliquer
   `supabase/migrations/` (`supabase db push` ou l'éditeur SQL dans l'ordre des fichiers).
3. Test : `python scripts/ci/smoke_test_e2e.py` (voir `docs/context/runbook-pre-pilot.md`) ou une requête sur `restaurant_profiles`.

### 5.2 Fly.io (org `ivan-de-murard`)
1. Dashboard Fly → Billing : ajouter un moyen de paiement (l'essai est terminé, rien ne démarre sans).
2. `fly auth login` puis `fly apps list -o ivan-de-murard`. Si `aetherix-backend` existe ailleurs ou est pris :
   `fly apps create <nom> -o ivan-de-murard` et changer `app =` dans `fly.toml`.
3. Secrets (jamais dans le repo) : `fly secrets set -a <app> DATABASE_URL=… SUPABASE_URL=… SUPABASE_KEY=… ANTHROPIC_API_KEY=… MISTRAL_API_KEY=… PII_HASH_PEPPER=… TWILIO_ACCOUNT_SID=… TWILIO_AUTH_TOKEN=… TWILIO_WHATSAPP_NUMBER=… APALEO_CLIENT_ID=… APALEO_CLIENT_SECRET=… APALEO_MCP_SERVER_URL=…` (liste : `docs/ops/environment-variables.md`).
4. **Connexion GitHub** : workflow manuel `.github/workflows/fly-deploy.yml`. Créer un jeton
   `fly tokens create deploy -a <app>`, l'ajouter en secret d'Actions `FLY_API_TOKEN`, puis Actions →
   « Deploy — Fly.io staging (manual) » → Run. Le job échoue si `/health` ne répond pas 200.
5. Puis seulement : `public-status.yml` → `deployed: true` sur les entrées vérifiées.

### 5.3 Twilio WhatsApp (sandbox)
1. Console Twilio → Messaging → Try it out → WhatsApp sandbox : renvoyer `join <code>` depuis le téléphone
   (la session sandbox expire, il faut la rejoindre à nouveau).
2. « When a message comes in » → `https://<app>.fly.dev/webhooks/twilio/inbound` (POST).
3. Écrire au numéro **moins d'une heure avant** la démo : sans template approuvé, un message envoyé à
   l'initiative du système ne part que si le manager a écrit dans les dernières 23 h 30.

### 5.4 Apaleo sandbox
1. Le serveur MCP Apaleo de la session Claude Code ne se connecte plus (`CONNECTION_CLOSED`) : identifiants
   expirés ou rotés (possiblement lors de la rotation des clés de juillet, Décision #30).
2. app.apaleo.com → compte sandbox → Apps → client `client_credentials` : régénérer le secret, mettre à jour
   `backend/.env` (local) et Fly.
3. Test : `cd backend` puis `python ../scripts/ops/validate_apaleo_sandbox.py` → exit 0 attendu (1 = variables,
   2 = OAuth, 3 = session MCP, 4 = outils, 5 = appel).
4. La sandbox n'a pas de données F&B réalistes (HOS-353) : la montrer comme **connexion**, pas comme source de la démo.

### 5.5 GitHub — clé du run « modèle réel »
Le secret d'Actions `ANTHROPIC_API_KEY` renvoie 401 sur chaque run hebdomadaire depuis plusieurs semaines.
Le remplacer (Settings → Secrets and variables → Actions), puis lancer « Eval — inbound parser (real model, opt-in) »
→ premier chiffre réel de qualité de lecture (HOS-342).

## 6. Questions probables

- **Pourquoi Prophet si la naïve fait jeu égal ?** Le protocole gelé tranche avant de lire les résultats (seuils
  5 / 2 pp). Le produit vaut par la boucle décision → réel → apprentissage approuvé, pas par le modèle.
- **Pourquoi pas un utilisateur d'abord ?** Juste. Le plan de juillet le priorisait (5 interviews managers, HOS-309) ;
  elles ne sont pas faites. L'objectif a été reformulé portfolio en septembre (Décision #36).
- **Que se passe-t-il si le modèle se trompe ?** Sous 0,85 rien n'est écrit sans « oui » ; au-dessus, la
  décision est citée en retour et corrigeable (« corriger mardi »). La source de chaque décision est stockée.
- **Coût ?** ≈ 0,75 $ de LLM par propriété et par mois ; WhatsApp ≈ 1,60 $ (`docs/Cost_Model.md`). Le LLM n'est pas le poste dominant.
- **Prompt-injection ?** Non traité (G-6 différé). Atténuation partielle : le modèle ne renvoie qu'une position
  validée par schéma, jamais une action ; l'irréversible attend un humain.

## 7. Partage d'écran — hygiène

Fermer `backend/.env`, les terminaux avec jetons, le vault Obsidian. Ne pas ouvrir ADR-0012 (privé, Décision #31).
Onglets prêts : Linear HOS-357 · PR #298 · `mape-benchmark.md` · ce runbook · les deux terminaux.
