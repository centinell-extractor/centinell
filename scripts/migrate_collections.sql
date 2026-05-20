-- ============================================================
-- Migración: Colecciones (batch processing)
-- Ejecutar en Supabase SQL Editor (o psql)
-- ============================================================

-- 1. Nueva tabla collections
CREATE TABLE IF NOT EXISTS collections (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(200) NOT NULL,
    config_id   UUID NOT NULL REFERENCES prompt_configs(id),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_collection_config  ON collections(config_id);
CREATE INDEX IF NOT EXISTS idx_collection_created ON collections(created_at);

-- 2. Nueva columna en extractions
ALTER TABLE extractions
    ADD COLUMN IF NOT EXISTS collection_id UUID REFERENCES collections(id);

CREATE INDEX IF NOT EXISTS idx_extraction_collection ON extractions(collection_id);
