-- ============================================================
-- Миграция 003: Создание таблицы communication_log
-- ============================================================

CREATE TABLE IF NOT EXISTS communication_log (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE SET NULL,
    greeting_id INTEGER REFERENCES greetings(id) ON DELETE SET NULL,
    event_id INTEGER REFERENCES events(id) ON DELETE SET NULL,
    channel VARCHAR(20) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    error_message TEXT,
    metadata JSONB DEFAULT '{}'::jsonb,
    sent_at TIMESTAMP WITH TIME ZONE,
    delivered_at TIMESTAMP WITH TIME ZONE,
    opened_at TIMESTAMP WITH TIME ZONE,
    clicked_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Индексы
CREATE INDEX IF NOT EXISTS idx_comm_log_client_id ON communication_log(client_id);
CREATE INDEX IF NOT EXISTS idx_comm_log_greeting_id ON communication_log(greeting_id);
CREATE INDEX IF NOT EXISTS idx_comm_log_event_id ON communication_log(event_id);
CREATE INDEX IF NOT EXISTS idx_comm_log_status ON communication_log(status);
CREATE INDEX IF NOT EXISTS idx_comm_log_channel ON communication_log(channel);
CREATE INDEX IF NOT EXISTS idx_comm_log_sent_at ON communication_log(sent_at);
CREATE INDEX IF NOT EXISTS idx_comm_log_created_at ON communication_log(created_at);

-- Композитные индексы
CREATE INDEX IF NOT EXISTS idx_comm_log_client_status ON communication_log(client_id, status);
CREATE INDEX IF NOT EXISTS idx_comm_log_date_channel ON communication_log(sent_at, channel);

-- GIN индекс для metadata
CREATE INDEX IF NOT EXISTS idx_comm_log_metadata ON communication_log USING GIN (metadata);

-- Триггер для обновления updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_communication_log_updated_at
    BEFORE UPDATE ON communication_log
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Комментарии к таблице и колонкам
COMMENT ON TABLE communication_log IS 'Лог всех коммуникаций с клиентами';
COMMENT ON COLUMN communication_log.channel IS 'Канал отправки: email, sms, push, messenger';
COMMENT ON COLUMN communication_log.status IS 'Статус: pending, sent, delivered, opened, clicked, failed';
COMMENT ON COLUMN communication_log.metadata IS 'Дополнительные метаданные (IP, user-agent, и т.д.)';