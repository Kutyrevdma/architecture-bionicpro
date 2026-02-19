CREATE DATABASE IF NOT EXISTS bionicpro;

-- 1. Kafka Queue Table
CREATE TABLE IF NOT EXISTS bionicpro.crm_users_queue (
    before String,
    after String,
    op String
) ENGINE = Kafka('kafka:29092', 'crmserver.public.crm_users', 'clickhouse_group', 'JSONEachRow');

-- 2. Storage Table (ReplacingMergeTree to handle updates)
CREATE TABLE IF NOT EXISTS bionicpro.crm_users_replicated (
    id String,
    name String,
    email String,
    contract_date Date,
    model String,
    _version UInt64
) ENGINE = ReplacingMergeTree(_version)
ORDER BY id;

-- 3. Materialized View (Parse JSON)
-- We use 'visitParamExtract' to extract fields from the 'after' JSON object provided by Debezium
CREATE MATERIALIZED VIEW IF NOT EXISTS bionicpro.crm_users_mv TO bionicpro.crm_users_replicated AS
SELECT
    visitParamExtractString(after, 'id') as id,
    visitParamExtractString(after, 'name') as name,
    visitParamExtractString(after, 'email') as email,
    toDate(visitParamExtractInt(after, 'contract_date')) as contract_date, -- Debezium sends date as days since epoch often, need check.
    -- Actually Debezium default for DATE is days since epoch (int). toDate accepts int days or string 'YYYY-MM-DD'.
    -- If it sends string, extractString. If int, extractInt.
    -- Assuming default config: io.debezium.time.Date -> int32 (days)
    visitParamExtractString(after, 'model') as model,
    toUInt64(visitParamExtractInt(after, 'ts_ms')) as _version -- Use timestamp as version
FROM bionicpro.crm_users_queue
WHERE op != 'd'; -- Ignore deletes for now or handle them via separate logic (IsDeleted flag)

-- 4. Telemetry Raw Table (Log Engine or MergeTree)
CREATE TABLE IF NOT EXISTS bionicpro.telemetry_raw (
    user_id String,
    log_date Date,
    avg_signal Float32,
    min_battery Int32,
    total_actions Int32
) ENGINE = MergeTree()
ORDER BY (user_id, log_date);

-- 5. Reporting View (The "Showcase")
CREATE VIEW IF NOT EXISTS bionicpro.user_daily_reports_view AS
SELECT
    t.log_date as report_date,
    t.user_id,
    c.name as user_name,
    c.model as prosthesis_model,
    t.avg_signal,
    t.min_battery,
    t.total_actions
FROM bionicpro.telemetry_raw t
LEFT JOIN bionicpro.crm_users_replicated c ON t.user_id = c.id;
