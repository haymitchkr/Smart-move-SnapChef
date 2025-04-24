import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

# Убедитесь, что установлен пакет psycopg2-binary:
# pip install psycopg2-binary

load_dotenv()

# Явно используем sync-драйвер psycopg2
DATABASE_URL = os.getenv('DATABASE_URL')
if DATABASE_URL and DATABASE_URL.startswith('postgresql+asyncpg'):
    DATABASE_URL = DATABASE_URL.replace('postgresql+asyncpg', 'postgresql+psycopg2')
if not DATABASE_URL:
    DATABASE_URL = 'postgresql+psycopg2://snapchef:your_password@localhost:5432/snapchef_db'

print(f"Используемая строка подключения: {DATABASE_URL}")

engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Выводим все колонки таблицы user_preferences
    print("\nСписок колонок в таблице user_preferences:")
    result = conn.execute(text("""
        SELECT column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'user_preferences';
    """))
    columns = result.fetchall()
    for col in columns:
        print(f"- {col[0]} ({col[1]})")
    # Проверяем наличие колонки healthy_profile
    exists = any(col[0] == 'healthy_profile' for col in columns)
    if exists:
        print('\nКолонка healthy_profile уже существует.')
    else:
        print('\nКолонка healthy_profile отсутствует. Добавляю...')
        conn.execute(text("""
            ALTER TABLE public.user_preferences ADD COLUMN healthy_profile BOOLEAN DEFAULT FALSE NOT NULL;
        """))
        print('Колонка healthy_profile успешно добавлена.') 