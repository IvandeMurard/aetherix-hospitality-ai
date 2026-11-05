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
| 2:15 | **Ce qui marche — apprendre sans dériver** | `closed_loop_demo.py` | 30 jours simulés, choc de demande +25 % au jour 15 : erreur 15,9 % → 12,3 % après recalibration hebdomadaire (relevé du 05/11 ; relancer le script et citer le chiffre affiché). Un réel aberrant (900 couverts pour 120 places) est rejeté par une borne (G-3) au lieu d'être appris. Les règles d'effectif apprises ne s'appliquent qu'après approbation d'une personne nommée. |
| 3:15 | **Prévision : mesure sur données réelles (évaluation ≠ service)** | `docs/context/mape-benchmark.md` | Kaggle Recruit est un **benchmark hors ligne**, pas le jeu d'entraînement du service de démo (voir §6, « Entraîné sur Kaggle ? »). Kaggle Recruit (restaurants réels) : Prophet bat la baseline naïve en moyenne (MAPE 49,7 % vs 55,9 %) mais **fait jeu égal en médiane** (27,0 vs 27,6 %) et est **derrière à J+1** (28,5 vs 27,9 %). J'ai déclenché moi-même la clause de pivot : la valeur n'est pas le modèle, c'est la boucle de décision. |
| 4:00 | **Construit avec Claude Code** | Linear HOS-357 → PR #298 → CI | Une story : contexte d'audit, périmètre tranché et daté par moi, critères d'acceptation, cas golden ajoutés, gate d'éval bloquant. Puis 2 corrections où la mesure a contredit l'IA (§3). |
| 5:30 | **Limites avant pilote** | §4 | 0 utilisateur ; lecture du modèle mesurée à 98,1 % (n=52) avec 1 cas ambigu résiduel (« pourquoi pas », écrit sans confirmation, seuil = 0) ; réels déclarés par le manager (pas de POS) ; templates WhatsApp non approuvés ; défense prompt-injection différée ; staging arrêté. |
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
   - 05/11 (après changement de clé) : première vraie mesure du modèle de lecture (Haiku 4.5) → **7 cas rejetés au schéma**
     (`stance: "acknowledge"`, `intent: "none"` : le modèle mélangeait les listes). Prompt corrigé (PR #302), schéma **inchangé**
     (un échec de schéma reste un échec, ADR-0007 §15) → précision **98,1 %** (n=52, 3 runs identiques, 0 % d'échec de schéma).
     Reste 1 cas ambigu (« pourquoi pas ») non réglé volontairement : cas held-out, on ne règle pas le prompt dessus.
     Une 2ᵉ tentative (durcir `reason_route`) a fait **baisser** la précision à 96,2 % : annulée.
3. **BMAD** : montrer `tools/bmad/_bmad-output/implementation-artifacts/` (une story → son fichier) et ce que
   j'ai **ajouté** à la méthode (éval dès la conception, taxonomie de statuts) et **coupé** (Décision #24, gel Epic 16).
   Ne pas dérouler les personas.

## 4. Limites avant pilote (à dire avant qu'on les demande)

| Limite | État | Ce qui la lève |
|---|---|---|
| 0 utilisateur réel | aucun hôtel | design partner + protocole de preuve gelé (`docs/planning/protocole-de-preuve.md` : Δ MdAPE ≥ 5 pp, acceptation ≥ 30 %) |
| Lecture des réponses par le modèle | mesurée le 05/11 : 98,1 % (n=52), 1 cas ambigu résiduel ; Claude seul, pas encore Gemini ; baseline CI pas figée | HOS-342 : run CI sur `main`, puis Claude + Gemini, baselines figées |
| Réels | déclarés par le manager (`independent_actuals: false`) | POS (Epic 13) |
| Texte de la recommandation | en anglais (`format_message`) alors que la conversation est en français | traduire le formatter |
| WhatsApp | templates non approuvés, boutons derrière un flag | soumission Meta (catégorie Utility) |
| Prompt-injection | G-6 différé (HOS-114, HOS-253) | durcissement du chemin texte libre |
| Données guest (Anima) | gate DPIA fermé, 13 mesures bloquantes | rien avant ces mesures |
| Staging | **relancé le 05/11** : `aetherix-backend` v25, smoke 4/4, chaîne **WhatsApp → Twilio → Fly → Supabase** de bout en bout (`FORECAST vendredi` répond). Hôtel fictif ; modèle de prévision entraîné sur série **synthétique** | §5.3 |

## 5. Relancer l'environnement (optionnel pour la démo)

Ordre : **Supabase → Fly → Twilio → Apaleo.** Chaque étape a son test de sortie.

### 5.0 Relance express — terminal local (PowerShell, racine du repo)

Plus simple qu'une session cloud : `backend/.env`, `flyctl` et la connexion navigateur sont sur la machine.
Budget : 45 min. Arrêter à 13:30 le 06/11 si ce n'est pas vert, et faire la démo sur les scripts locaux.

```powershell
# 1. Supabase (projet imfrvrngxbtotmfbdtpf) — d'abord dans le navigateur :
#    https://supabase.com/dashboard/project/imfrvrngxbtotmfbdtpf  → « Restore » si proposé.
npx supabase login
npx supabase link --project-ref imfrvrngxbtotmfbdtpf
npx supabase db push            # applique supabase/migrations/ manquantes

# 2. Fly — compte ivandemurard@hotmail.fr (PAS le Gmail : il ne voit aucune app), org `personal`
fly auth whoami                         # doit afficher le compte hotmail ; sinon fly auth logout && fly auth login
fly apps list                           # aetherix-backend doit apparaître (déployé)
fly secrets list -a aetherix-backend    # noms + empreintes seulement ; les secrets survivent
fly deploy --remote-only -a aetherix-backend    # depuis la branche à déployer
curl https://aetherix-backend.fly.dev/health    # {"status":"ok"} ; /health ne teste PAS la base
# Preuve base + prévision + mémoire (jeton MCP : docs/context/runbook-pre-pilot.md §1.3) :
#   $env:APP_BASE_URL="https://aetherix-backend.fly.dev"; backend\.venv\Scripts\python scripts\ci\smoke_test_e2e.py --skip 2,6
# Ne pas créer d'app via « Launch from GitHub » : elle génère un doublon vide et suspendu
#   (05/11 : aetherix-hospitality-ai et aetherix-hospitality-ai-6hzt-w, à supprimer).

# 3. Connexion GitHub → Fly (déploiements suivants via Actions)
fly tokens create deploy -a aetherix-backend
#    → coller la valeur dans le secret d'Actions FLY_API_TOKEN (lien §5.5)

# 4. Apaleo (vert au 05/11 : OAuth, MCP, 243 outils ; latence MCP ~1,8 s > gate 500 ms)
$env:PYTHONIOENCODING="utf-8"   # sinon crash cosmétique final (emoji, console cp1252) → exit 1 à tort
backend\.venv\Scripts\python scripts\ops\validate_apaleo_sandbox.py
```

Si Supabase n'offre plus « Restore » (pause > 90 jours) : nouveau projet EU, `npx supabase link` sur le
nouveau ref, `db push`, puis mettre à jour `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_KEY` dans
`backend/.env` **et** `fly secrets set -a aetherix-backend …`. Les données de démo sont fictives : rien à récupérer.

### 5.1 Supabase
1. Dashboard Supabase → le projet. Un projet gratuit inactif est mis en pause après 7 jours ; il se restaure
   depuis le dashboard **pendant 90 jours seulement**, ensuite seule la sauvegarde est téléchargeable.
2. Si « Restore » est proposé → restaurer. Sinon → nouveau projet (région EU), extension `vector`, puis appliquer
   `supabase/migrations/` (`supabase db push` ou l'éditeur SQL dans l'ordre des fichiers).
3. Test : `python scripts/ci/smoke_test_e2e.py` (voir `docs/context/runbook-pre-pilot.md`) ou une requête sur `restaurant_profiles`.

### 5.2 Fly.io (compte ivandemurard@hotmail.fr, org `personal`)
1. Dashboard Fly → Billing : ajouter un moyen de paiement (l'essai est terminé, rien ne démarre sans).
2. `fly auth login` puis `fly apps list`. Si `aetherix-backend` existe ailleurs ou est pris :
   `fly apps create <nom> -o personal` et changer `app =` dans `fly.toml`.
3. Secrets (jamais dans le repo) : `fly secrets set -a <app> DATABASE_URL=… SUPABASE_URL=… SUPABASE_KEY=… ANTHROPIC_API_KEY=… MISTRAL_API_KEY=… PII_HASH_PEPPER=… TWILIO_ACCOUNT_SID=… TWILIO_AUTH_TOKEN=… TWILIO_WHATSAPP_NUMBER=… APALEO_CLIENT_ID=… APALEO_CLIENT_SECRET=… APALEO_MCP_SERVER_URL=…` (liste : `docs/ops/environment-variables.md`).
4. **Connexion GitHub** : workflow manuel `.github/workflows/fly-deploy.yml`. Créer un jeton
   `fly tokens create deploy -a <app>`, l'ajouter en secret d'Actions `FLY_API_TOKEN`, puis Actions →
   « Deploy — Fly.io staging (manual) » → Run. Le job échoue si `/health` ne répond pas 200.
5. Puis seulement : `public-status.yml` → `deployed: true` sur les entrées vérifiées.

### 5.3 Twilio WhatsApp (sandbox)
0. `TWILIO_ACCOUNT_SID` doit être l'**Account SID `AC…`** (console Twilio, page d'accueil), pas un SID de clé API `SK…` :
   le SDK du backend ne s'authentifie pas avec. (Le `backend/.env` local contenait un `SK…` le 05/11.) Poser avec `fly secrets set`, jamais dans un chat.
1. Console Twilio → Messaging → Try it out → WhatsApp sandbox : renvoyer `join <code>` depuis le téléphone
   (la session sandbox expire, il faut la rejoindre à nouveau).
2. « When a message comes in » → `https://<app>.fly.dev/webhooks/twilio/inbound` (POST).
3. Écrire au numéro **moins d'une heure avant** la démo : sans template approuvé, un message envoyé à
   l'initiative du système ne part que si le manager a écrit dans les dernières 23 h 30.
4. **Secrets Fly à poser (vérifiés le 05/11 — chacun a coupé la réponse)** : `TWILIO_ACCOUNT_SID` (`AC…`, pas `US…`/`SK…`),
   `TWILIO_AUTH_TOKEN` (celui du compte), `TWILIO_WHATSAPP_FROM` et `TWILIO_WHATSAPP_NUMBER` = `whatsapp:+14155238886`,
   `ANTHROPIC_API_KEY` (la clé de Fly est **séparée** de celle de GitHub et du `.env` local).
5. **Profil** (Supabase, table `restaurant_profiles`, tenant `demo_hotel`) : `phone_number` = votre numéro au format `+33…`
   (sinon la tâche de prévision s'arrête **en silence**), `pms_type='apaleo'`, `pms_property_id='PAR'`, `manager_locale='fr'`,
   `agent_tone_profile='luxury'` (valeurs : `casual`, `luxury`, `professional`).
6. **Test** : envoyer `FORECAST vendredi` (ou `prévision samedi`). Réponse attendue (~10 s) : titre 📊, « *N couverts* · fourchette »,
   bloc 👥 effectif, bloc 🌤 contexte (occupation lue sur Apaleo), invite 💬 et, si `FORECAST_DEMO_NOTICE=true`,
   « 🧪 Démonstration : hôtel fictif, modèle entraîné sur des données synthétiques ».
7. **Diagnostic** : `fly logs -a aetherix-backend --no-tail` (journalisation INFO depuis #305). Twilio : console →
   Monitor → Logs → Errors. `11200` = mauvaise URL de webhook ; `12200` = TwiML invalide (corrigé, `F&amp;B`) ;
   `20003` = Account SID/token ; `63007` = adresse d'expédition `whatsapp:+…` inconnue du compte.
8. Météo et événements restent « non disponibles » jusqu'aux synchronisations (météo toutes les 12 h, événements chaque jour
   à 06:00 UTC) ; l'occupation vient de `pms_sync_logs`, qu'**aucun job ne remplit** : voir §5.4.

### 5.4 Apaleo sandbox
1. **Vert le 05/11** : OAuth, MCP, 243 outils (latence MCP ~1,4 s, au-dessus du gate de 500 ms). Si `invalid_client` : secret
   révoqué → app.apaleo.com → compte `Aetherix` (IIQJ) → Apps → client `client_credentials` : régénérer, mettre à jour
   `backend/.env` et Fly.
2. Test : `cd backend` puis `python ../scripts/ops/validate_apaleo_sandbox.py` (avec `PYTHONIOENCODING=utf-8`) → exit 0 attendu
   (1 = variables, 2 = OAuth, 3 = session MCP, 4 = outils, 5 = appel).
3. **Hôtel de démo = Maison Lumen** (27 rue de Turenne, 75003 Paris), c'est la propriété sandbox `PAR` (« Hotel Paris ») reprise :
   nom, adresse, 11 tarifs rouverts jusqu'au 31/12/2027, prix posés du 05/11/2026 au 28/02/2027 (semaine 105 €, week-end 135 €,
   +25 % les jours d'événement), **1 086 réservations futures** `LUMEN-SEED-…` (06/11/2026 → 06/01/2027, dont 94 annulées,
   ~35 % avec une demande client). Script : `scripts/ops/seed_apaleo_sandbox.py` (simulation par défaut ; `--apply`, `--resume`,
   `--cleanup`). Sauvegardes de l'état d'origine hors dépôt.
4. **Limites à dire telles quelles** : (a) Apaleo refuse toute arrivée **passée**, même avec `$force` → pas d'historique, seulement
   du futur ; (b) les couverts du restaurant sont du **POS** (Epic 13), pas du PMS ; (c) l'API de lecture ne renvoie pas
   `guestComment`/`comment` : leur enregistrement n'est pas vérifié ; (d) la langue obligatoire des tarifs est `de` en plus de `en`.
5. L'occupation (« 63 % » dans le message) est lue sur la disponibilité Apaleo puis **injectée dans `pms_sync_logs` par SQL**
   (lignes `raw_payload_summary->>'source' = 'apaleo-sandbox-seed'`, 63 jours) : aucun job planifié ne synchronise le PMS.
   La montrer comme **connexion lue en direct** + « synchronisation quotidienne à brancher », pas comme un flux automatique.

### 5.5 GitHub — clé du run « modèle réel »
Le secret d'Actions `ANTHROPIC_API_KEY` renvoie 401 sur chaque run hebdomadaire depuis plusieurs semaines.

1. Nouvelle clé : https://console.anthropic.com/settings/keys → « Create Key ».
2. Secrets du repo : https://github.com/IvandeMurard/aetherix-hospitality-ai/settings/secrets/actions →
   `ANTHROPIC_API_KEY` → crayon (Update) → coller → « Update secret ». Même page pour `FLY_API_TOKEN` (« New repository secret »).
3. Lancer : https://github.com/IvandeMurard/aetherix-hospitality-ai/actions/workflows/eval-parser-real.yml →
   « Run workflow » (runs = 3) → premier chiffre réel de qualité de lecture (HOS-342).

## 6. Questions probables

- **Pourquoi Prophet si la naïve fait jeu égal ?** Le protocole gelé tranche avant de lire les résultats (seuils
  5 / 2 pp). Le produit vaut par la boucle décision → réel → apprentissage approuvé, pas par le modèle.
- **Pourquoi pas un utilisateur d'abord ?** Juste. Le plan de juillet le priorisait (5 interviews managers, HOS-309) ;
  elles ne sont pas faites. L'objectif a été reformulé portfolio en septembre (Décision #36).
- **Que se passe-t-il si le modèle se trompe ?** Sous 0,85 rien n'est écrit sans « oui » ; au-dessus, la
  décision est citée en retour et corrigeable (« corriger mardi »). La source de chaque décision est stockée.
- **Le modèle est-il entraîné sur Kaggle (données réelles) ?** Non, et il faut le dire avant qu'on le suppose. Kaggle Recruit
  (829 restaurants japonais, 2016-2017) est un **benchmark d'évaluation hors ligne** : il mesure la méthode (Prophet ≈ naïve en médiane).
  Le service de démo tourne sur un **hôtel fictif** : modèle entraîné sur une série **synthétique** de 365 jours
  (`backend/data/demo/prophet_training.json`, générée par `generate_demo_data.py`), occupation et réservations lues sur la
  sandbox Apaleo. Le 15,09 % synthétique est circulaire (Décision #33) et n'est pas cité. Le message porte la mention « 🧪 Démonstration ».
- **Pourquoi pas de données de couverts liées à la sandbox Apaleo ?** Un PMS ne porte pas les couverts du restaurant (c'est le POS,
  Epic 13) et Apaleo n'accepte pas d'historique. Réentraîner « sur Apaleo » reviendrait à fabriquer une série calée sur l'occupation :
  circulaire. Suite honnête : occupation en régresseur de Prophet (évalué), modèle de capture à taux étiqueté, puis POS / partenaire.
- **« Effectif habituel : 7 » vient d'où ?** De valeurs **par défaut** du catalogue de paramètres (`hotel_parameters.py`), annoncées comme
  telles dans le message. Le mécanisme existe (`usual_*`, `covers_per_*`, modifiables par `ops`, proposition approuvée ou `hotel_system`
  — outil de planning, SOP) mais **aucune ingestion** PMS/POS/SOP ne l'alimente encore.
- **Coût ?** ≈ 0,75 $ de LLM par propriété et par mois ; WhatsApp ≈ 1,60 $ (`docs/Cost_Model.md`). Le LLM n'est pas le poste dominant.
- **Prompt-injection ?** Non traité (G-6 différé). Atténuation partielle : le modèle ne renvoie qu'une position
  validée par schéma, jamais une action ; l'irréversible attend un humain.

## 7. Partage d'écran — hygiène

Fermer `backend/.env`, les terminaux avec jetons, le vault Obsidian. Ne pas ouvrir ADR-0012 (privé, Décision #31).
Onglets prêts : Linear HOS-357 · PR #298 · `mape-benchmark.md` · ce runbook · les deux terminaux.
