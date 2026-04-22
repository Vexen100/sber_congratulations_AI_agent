-- ============================================================
-- Миграция 002: Добавление полей в таблицу clients
-- ============================================================

-- Добавление новых колонок
ALTER TABLE clients ADD COLUMN IF NOT EXISTS interests JSONB;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS tags JSONB DEFAULT '[]'::jsonb;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS custom_attributes JSONB DEFAULT '{}'::jsonb;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS preferred_channel VARCHAR(20) DEFAULT 'email';
ALTER TABLE clients ADD COLUMN IF NOT EXISTS last_activity_date DATE;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS communication_score INTEGER DEFAULT 0;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS engagement_level VARCHAR(20) DEFAULT 'medium';
ALTER TABLE clients ADD COLUMN IF NOT EXISTS ltv_score DECIMAL(10, 2) DEFAULT 0;
ALTER TABLE clients ADD COLUMN IF NOT EXISTS churn_risk VARCHAR(20) DEFAULT 'low';

-- Индексы для новых полей
CREATE INDEX IF NOT EXISTS idx_clients_preferred_channel ON clients(preferred_channel);
CREATE INDEX IF NOT EXISTS idx_clients_engagement_level ON clients(engagement_level);
CREATE INDEX IF NOT EXISTS idx_clients_churn_risk ON clients(churn_risk);
CREATE INDEX IF NOT EXISTS idx_clients_last_activity ON clients(last_activity_date);

-- GIN индексы для JSONB
CREATE INDEX IF NOT EXISTS idx_clients_interests ON clients USING GIN (interests);
CREATE INDEX IF NOT EXISTS idx_clients_tags ON clients USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_clients_custom_attributes ON clients USING GIN (custom_attributes);

-- Обновление существующих записей
UPDATE clients SET 
    preferred_channel = COALESCE(preferred_channel, 'email'),
    engagement_level = COALESCE(engagement_level, 'medium'),
    churn_risk = COALESCE(churn_risk, 'low'),
    communication_score = COALESCE(communication_score, 0),
    tags = COALESCE(tags, '[]'::jsonb),
    custom_attributes = COALESCE(custom_attributes, '{}'::jsonb);

-- NOT NULL constraints где необходимо
ALTER TABLE clients ALTER COLUMN preferred_channel SET DEFAULT 'email';
ALTER TABLE clients ALTER COLUMN engagement_level SET DEFAULT 'medium';
ALTER TABLE clients ALTER COLUMN churn_risk SET DEFAULT 'low';
ALTER TABLE clients ALTER COLUMN communication_score SET DEFAULT 0;