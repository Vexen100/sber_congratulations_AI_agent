-- ============================================================
-- Миграция 001: Добавление индексов для оптимизации
-- ============================================================

-- Индексы для таблицы events
CREATE INDEX IF NOT EXISTS idx_events_event_date ON events(event_date);
CREATE INDEX IF NOT EXISTS idx_events_client_date ON events(client_id, event_date);
CREATE INDEX IF NOT EXISTS idx_events_type_date ON events(event_type, event_date);

-- Индексы для таблицы greetings
CREATE INDEX IF NOT EXISTS idx_greetings_status_date ON greetings(status, created_at);
CREATE INDEX IF NOT EXISTS idx_greetings_event_id ON greetings(event_id);
CREATE INDEX IF NOT EXISTS idx_greetings_client_id ON greetings(client_id);
CREATE INDEX IF NOT EXISTS idx_greetings_agent_run_id ON greetings(agent_run_id);

-- Индексы для таблицы clients
CREATE INDEX IF NOT EXISTS idx_clients_inn ON clients(inn);
CREATE INDEX IF NOT EXISTS idx_clients_enrichment_status ON clients(enrichment_status);
CREATE INDEX IF NOT EXISTS idx_clients_profession ON clients(profession);
CREATE INDEX IF NOT EXISTS idx_clients_birth_date ON clients(birth_date);
CREATE INDEX IF NOT EXISTS idx_clients_email ON clients(email);
CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone);

-- Примечание: проект использует SQLite для MVP/demo. Специфичные для PostgreSQL (GIN/JSONB)
-- индексы здесь не создаём, чтобы миграция была переносимой и не ссылалась на отсутствующие колонки.

-- Индексы для таблицы holidays
CREATE INDEX IF NOT EXISTS idx_holidays_date ON holidays(date);
CREATE INDEX IF NOT EXISTS idx_holidays_is_business_relevant ON holidays(is_business_relevant);

-- Индексы для таблицы deliveries
CREATE INDEX IF NOT EXISTS idx_deliveries_greeting_id ON deliveries(greeting_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_status ON deliveries(status);
CREATE INDEX IF NOT EXISTS idx_deliveries_sent_at ON deliveries(sent_at);
CREATE INDEX IF NOT EXISTS idx_deliveries_channel ON deliveries(channel);
CREATE INDEX IF NOT EXISTS idx_deliveries_idempotency_key ON deliveries(idempotency_key);

-- Индексы для таблицы feedback
CREATE INDEX IF NOT EXISTS idx_feedback_greeting_id ON feedback(greeting_id);
CREATE INDEX IF NOT EXISTS idx_feedback_score ON feedback(score);
CREATE INDEX IF NOT EXISTS idx_feedback_outcome ON feedback(outcome);
CREATE INDEX IF NOT EXISTS idx_feedback_training_verdict ON feedback(training_verdict);

-- Композитные индексы для частых запросов
CREATE INDEX IF NOT EXISTS idx_events_client_date_type ON events(client_id, event_date, event_type);
CREATE INDEX IF NOT EXISTS idx_greetings_event_status ON greetings(event_id, status);
CREATE INDEX IF NOT EXISTS idx_deliveries_greeting_status ON deliveries(greeting_id, status);

-- Частичные индексы для оптимизации
CREATE INDEX IF NOT EXISTS idx_greetings_pending ON greetings(status, created_at) 
    WHERE status IN ('generated', 'needs_approval', 'approved');