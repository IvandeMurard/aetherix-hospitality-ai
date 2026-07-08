# Kit de démo closed-loop — tout au même endroit (HOS-310)

> **Le document à ouvrir le jour du tournage / d'une démo live.** Commandes, écrans, moments
> clés, chiffres autorisés (et interdits), messages de fond. Consolidé le 08/07/2026.

---

## 1. Lancement (2 minutes de préparation)

```bash
# Régénérer la démo (déterministe — mêmes chiffres à chaque run, seed 42)
backend/.venv/Scripts/python scripts/ops/closed_loop_demo.py

# Produit : sortie console (écran gauche) + docs/demos/closed_loop_demo.{json,md}
#           + docs/demos/whatsapp_transcript.md (écran droit)
```

Prérequis : aucun (pas de réseau, pas de DB, pas de clé API). Optionnel scène 6 : `LOGFIRE_TOKEN`
posé sur Fly (voir HOS-311 AC5) pour montrer une trace réelle.

## 2. Les trois écrans

| Écran | Contenu | Fichier / commande |
|---|---|---|
| **Gauche** | Terminal, le script qui déroule les 30 jours | commande ci-dessus, police ≥ 16pt |
| **Centre** | Schéma de la boucle, étape active surlignée | slide 5 variantes (forecast → reco → feedback → réel → G-3 → recalibration) |
| **Droite** | Fil WhatsApp manager ↔ Aetherix | [`whatsapp_transcript.md`](whatsapp_transcript.md) dans un viewer étroit (~380 px) |

Séquencier détaillé scène par scène : [`closed-loop-video-storyboard.md`](closed-loop-video-storyboard.md).

## 3. Les quatre moments à zoomer

| Jour | Ce qui se passe | Ce que ça prouve |
|---|---|---|
| **J10** | Export POS corrompu (900 couverts / 120 places) → « ⚠️ implausible — écartée, elle n'alimentera pas l'apprentissage » | Le guardrail G-3 protège la mémoire contre l'empoisonnement, avec raison typée (NFR2) |
| **J15** | ⚡ Choc de régime +25 % (contrat banquets) — les écarts montent | Le scénario qui tue les forecasts statiques |
| **J17** | « 📈 Troisième sous-estimation consécutive — un changement de régime semble en cours » | L'agent **détecte et nomme sa propre dérive** (comptage réel, pas scripté) |
| **J21/J28** | « 🔁 Modèle recalibré » puis les écarts redescendent | La boucle absorbe le changement : 15,9 % → 12,3 % |

Anticipation (à montrer au passage, J18+) : les receipts citent leurs drivers *avant* le service —
« 📍 Signal : événement local demain — impact +X % intégré » · « 🏨 Hôtel à 92 % d'occupation ».

## 4. Chiffres : ce que vous pouvez dire, et ce que vous ne pouvez pas

**✅ Autorisés (démo mécanique, données sandbox — le dire) :**
- MAPE post-choc **15,9 % → 12,3 %** après recalibration · 5 recalibrations · 1 rejet G-3 · 29 outcomes capturés
- « Script déterministe : deux runs, résultats bit-identiques »

**✅ Autorisés (mesurés sur données réelles — benchmark Recruit, HOS-307) :**
- « Sur 30 restaurants réels, le pipeline bat la baseline naïve de **6 points de MAPE** (49,7 vs 55,9 %) »
- MdAPE ~27 % en médiane — « et le benchmark documente honnêtement où il ne la bat pas »

**⛔ Interdits (jamais comme preuve produit) :**
- « 76,7 % d'acceptation » = comportement d'un manager **simulé** (artefact du paramètre de tolérance). Ne citer que comme illustration du rituel, jamais comme métrique d'adoption.
- « MAPE < 15 % », « labor cost −3 à −8 % » = **cibles** issues de la littérature marché, jamais mesurées. Statut réel des KPIs : cadre à 3 niveaux solide, valeurs `mesuré | cible | synthétique` — étiquetage complet à faire en 16.13 (HOS-313).

## 5. Le message de fond (la thèse à faire passer)

1. **Le forecast est un organe, pas le produit.** Notre propre benchmark montre que Prophet ≈ baseline naïve sur le jour typique — la couche prédictive est commoditisée.
2. **Le produit, c'est la boucle cognitive** : capture d'outcomes, mémoire opérationnelle par propriété, bornes de confiance (G-3), recalibration, explicabilité. C'est ce qu'on voit dans le transcript : un agent qui anticipe, se trompe, *le dit*, et apprend.
3. **La discipline rend tout vérifiable** : raisons typées, déterminisme, eval-gates CI — « il a dégradé proprement » est démontrable, pas déclaratif.
4. **Aetherix est la preuve, Anima est la promesse** : l'extension de cette architecture cognitive au guest (4 couches, DPIA-first) est une thèse de design — la présenter comme telle.

## 6. Liens

- Storyboard v2 (séquencier 3 min) : [`closed-loop-video-storyboard.md`](closed-loop-video-storyboard.md)
- Transcript WhatsApp complet : [`whatsapp_transcript.md`](whatsapp_transcript.md)
- Rapport + ledger : [`closed_loop_demo.md`](closed_loop_demo.md) / [`closed_loop_demo.json`](closed_loop_demo.json)
- Benchmark données réelles : [`../context/mape-benchmark.md`](../context/mape-benchmark.md) §Recruit
- Setup Logfire (scène 6) : commentaire HOS-311 (token + `flyctl secrets set`)
- Audit critique (contexte de tout ceci) : [`../context/analyse-critique-2026-07.md`](../context/analyse-critique-2026-07.md)
