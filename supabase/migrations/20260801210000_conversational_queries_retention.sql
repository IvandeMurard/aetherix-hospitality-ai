-- Story 7.5 / HOS-115 (AC5) — rétention et pseudonymisation de `conversational_queries`.
--
-- Contexte : cette table persiste le numéro de l'expéditeur et le corps du
-- message entrant, en clair, sans durée — par conception, c'était le mécanisme
-- d'idempotence. Le correctif Q2-03 (PR #187) avait traité les logs et laissé
-- la table intacte. Voir docs/GDPR-DATA-INVENTORY.md §6.2.
--
-- Trois opérations, dans cet ordre.

-- 1. Index sur created_at — la purge quotidienne balaie par date. Sans lui,
--    chaque passage est un seq scan sur une table qui ne fait que grossir.
CREATE INDEX IF NOT EXISTS idx_conversational_queries_created_at
    ON conversational_queries (created_at);

-- 2. Purge immédiate de l'arriéré au-delà de 90 jours.
--    Rejouable : une seconde exécution ne trouve plus rien.
DELETE FROM conversational_queries
WHERE created_at < now() - INTERVAL '90 days';

-- 3. Neutralisation des numéros en clair restants.
--
--    L'application stocke désormais un HMAC-SHA256 poivré (`hmac256:…`,
--    app/core/pii.digest_identifier). Le poivre est un secret applicatif : cette
--    migration ne peut pas le lire, donc elle ne peut pas recalculer les digests
--    des lignes existantes.
--
--    Le choix retenu est d'écraser la valeur par un marqueur plutôt que de
--    laisser un numéro en clair vivre jusqu'à 90 jours de plus. La seule chose
--    qui lisait cette colonne est la fenêtre de dédup de 60 secondes : écraser
--    des lignes de plus d'une minute ne casse rien. Au pire, un message
--    strictement identique renvoyé dans la minute qui suit la migration crée un
--    doublon — une ligne de trop, contre des numéros en clair conservés.
--
--    Irréversible et voulu : ces valeurs n'auraient jamais dû être stockées ainsi.
UPDATE conversational_queries
SET from_number = '<purged-by-migration>'
WHERE from_number NOT LIKE 'hmac256:%';

COMMENT ON COLUMN conversational_queries.from_number IS
    'HMAC-SHA256 poivré de l''expéditeur (préfixe hmac256:), jamais le numéro. '
    'Pseudonymisation au sens du considérant 26, pas anonymisation. '
    'Story 7.5 / HOS-115.';

COMMENT ON COLUMN conversational_queries.body IS
    'Texte libre saisi par un manager — non contraint, peut porter une donnée '
    'sensible. Conservé en clair car le service de réponse en a besoin ; purgé '
    'à 90 jours par app/workers/retention_purge.py. Ne jamais journaliser.';
