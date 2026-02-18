# Архитектура CDC для CRM (Debezium + ClickHouse)

## Проблема
Рост базы CRM приводит к замедлению OLTP операций во время выгрузки данных для аналитики (ETL).

## Решение
Внедрение Change Data Capture (CDC) для асинхронной репликации изменений из CRM в аналитическую БД (ClickHouse).

### Компоненты

1.  **PostgreSQL (Source DB)**:
    *   Включен `wal_level = logical`.
    *   Генерирует поток изменений (WAL).

2.  **Debezium (Kafka Connect)**:
    *   Читает WAL Postgres.
    *   Преобразует изменения (INSERT, UPDATE, DELETE) в JSON-события.
    *   Публикует события в топик Kafka (например, `crmserver.public.crm_users`).

3.  **Kafka**:
    *   Буфер сообщений.
    *   Обеспечивает развязку производителей (CRM) и потребителей (OLAP).

4.  **ClickHouse (OLAP)**:
    *   **Kafka Engine Table (`crm_users_queue`)**: Читает сырые сообщения из Kafka.
    *   **Materialized View (`crm_users_mv`)**: Парсит JSON, извлекает `after` состояние.
    *   **Storage Table (`crm_users_replicated`)**: Хранит актуальное состояние пользователей (ReplacingMergeTree).
    *   **Telemetry Table (`telemetry_raw`)**: Хранит данные телеметрии (загружается Airflow).
    *   **Reporting View (`user_daily_reports_view`)**: Объединяет (JOIN) телеметрию и данные пользователей для API.

### Потоки данных

1.  **CRM Flow**:
    `CRM (Write)` -> `WAL` -> `Debezium` -> `Kafka` -> `ClickHouse (Queue)` -> `ClickHouse (MV)` -> `ClickHouse (Table)`.
    *   Результат: В ClickHouse всегда (почти real-time) актуальная копия таблицы пользователей.
    *   Нагрузка на Postgres: Минимальная (только чтение WAL), нет SELECT запросов для выгрузки.

2.  **Telemetry Flow**:
    `Sensors` -> `Postgres (Telemetry)` -> `Airflow (ETL)` -> `ClickHouse (Table)`.
    *   Остается пакетным (Batch), так как данных много и они неизменяемы (logs).

3.  **Reporting Flow**:
    `Reports Service` -> `ClickHouse View` (Join `CRM` + `Telemetry`) -> `S3/CDN`.
