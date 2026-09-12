-- 002_marketing_source_fields.sql
-- Поля, необходимые для честного хранения реконструированного marketing_posts.csv.
-- Миграция безопасна для повторного запуска.

BEGIN;

ALTER TABLE marketing_activities
    ADD COLUMN IF NOT EXISTS source_activity_key TEXT,
    ADD COLUMN IF NOT EXISTS course_target_text TEXT,
    ADD COLUMN IF NOT EXISTS linked_spike TEXT,
    ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN;

CREATE UNIQUE INDEX IF NOT EXISTS ux_marketing_activities_source_activity_key
    ON marketing_activities(source_activity_key)
    WHERE source_activity_key IS NOT NULL;

COMMENT ON COLUMN marketing_activities.source_activity_key IS
'Стабильный технический ключ исходной маркетинговой публикации для идемпотентной загрузки. Не является tracking_code.';

COMMENT ON COLUMN marketing_activities.course_target_text IS
'Исходная маркетинговая цель из источника, например СТАРТ, ПРО или Аналитика вне SQL. Хранится отдельно, если её нельзя честно сопоставить конкретному courses.course_id.';

COMMENT ON COLUMN marketing_activities.linked_spike IS
'Исходная пометка linked_spike из реконструированного marketing_posts.csv. Не является доказательством причинности.';

COMMENT ON COLUMN marketing_activities.is_deleted IS
'Признак того, что публикация была удалена по данным реконструированного источника.';

COMMIT;
