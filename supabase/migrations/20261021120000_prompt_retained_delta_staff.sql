-- HOS-354 / HOS-357 (Décisions #6, #38) — a staffing figure read in a WhatsApp
-- reply is quoted back to the manager before it is written.
--
-- "Je note 2 extras au lieu de 3, c'est bien ça ? Oui / Non": the figure waits
-- on the confirmation prompt and reaches staffing_recommendations
-- .retained_delta_staff (HOS-344) only when the manager answers yes, with the
-- decision 'modified'. NULL for every other prompt.
-- ORM mirror: app/db/models.py ManagerPrompt.retained_delta_staff.

ALTER TABLE manager_prompts ADD COLUMN IF NOT EXISTS retained_delta_staff INTEGER;

COMMENT ON COLUMN public.manager_prompts.retained_delta_staff IS
  'Staffing figure quoted in a decision confirmation: extra staff kept, negative = fewer. Written to the recommendation only on yes (HOS-354).';

COMMENT ON COLUMN public.staffing_recommendations.retained_delta_staff IS
  'Counter (status modified): extra staff the hotel kept instead, negative = fewer. From MCP (host agent) or a WhatsApp reply the manager confirmed (HOS-344, HOS-354). NULL otherwise.';
