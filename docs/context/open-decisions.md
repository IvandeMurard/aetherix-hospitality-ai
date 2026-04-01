# Décisions ouvertes

> Mettre à jour quand une décision est tranchée — déplacer dans CLAUDE.md §Décisions architecturales.
> Les décisions tranchées ne doivent pas rester ici.

---

## Techniques

- [ ] **Embedding strategy** : pgvector vs Qdrant pour RAG (pgvector actuel, réévaluer si >50K patterns / >50 hôtels)
- [ ] **MCP server** : FastAPI endpoint dédié vs sidecar process séparé
- [ ] **Intégration Apaleo** : MCP direct vs API raw ? (Composio = Inventory uniquement, raw REST = path F&B actuel)
- [ ] **Apaleo alpha direct** : obtenir l'invite pour couvrir occupancy/revenue via MCP

## Produit

- [ ] **Pricing model** : par hôtel / par prédiction / hybrid — non décidé
- [ ] **PMS priorité live** : Apaleo (sandbox dispo, API-first) vs Mews (vision alignée, marketplace)
- [ ] **ROI dashboard vs WhatsApp** : afficher "€ économisés ce mois-ci" + évolution précision forecast 90j → via dashboard Next.js ou rapport WhatsApp hebdomadaire ? (dashboard = surface à maintenir, WhatsApp = ambiant mais moins visuel)
- [ ] **Food waste tracking** : intégrer predicted prep vs actual waste en Phase 4 (€ gaspillés évités) ou Phase 5 avec POS data ? (~115g/couvert, ~25% gaspillage moyen FR)

## Distribution

- [ ] **Agent Hub Apaleo** : cibler une entrée comme agent F&B spécialisé dès Phase 1 (HOS-101)
- [ ] **MCP Alpha Group Apaleo** : rejoindre community.apaleo.com pour accès early

## KPIs à instrumenter (Phase 1)

- `tool_success_rate` > 99.5%
- `p95_latency` < 500ms
- `schema_stability` = 0 breaking changes par sprint
- `agent_retry_rate` < 1%
- `MAPE` couverts < 15%
- `recommendation_acceptance_rate` (alerte si < 30%)
- `labor_cost_variance` cible –3% à –8%
