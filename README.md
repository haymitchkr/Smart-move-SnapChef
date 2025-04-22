# ... существующий текст ...

## Как запустить PostgreSQL

1. Установить PostgreSQL (например, через Docker):
   ```
   docker run --name snapchef-postgres -e POSTGRES_USER=snapchef -e POSTGRES_PASSWORD=123456 -e POSTGRES_DB=snapchef_db -p 5432:5432 -d postgres:15
   ```
2. В .env добавить строку:
   ```
   DATABASE_URL=postgresql+asyncpg://snapchef:123456@localhost:5432/snapchef_db
   ```
3. Для миграций Alembic в alembic.ini используйте sync-драйвер:
   ```
   sqlalchemy.url = postgresql+psycopg2://snapchef:123456@localhost:5432/snapchef_db
   ```

## Пример DATABASE_URL
```
DATABASE_URL=postgresql+asyncpg://snapchef:123456@localhost:5432/snapchef_db
```

## Как пользоваться меню

Вместо команд бот использует главное меню с кнопками:

- 📋 Главное — возвращает на главный экран
- ❓ Помощь — показывает подсказки по использованию бота
- 💾 Сохранённые — ваши сохранённые рецепты
- ⚙️ Настройки — настройки профиля

Пример главного меню:

```
👨‍🍳 Добро пожаловать в SnapChef!
Я помогу подобрать рецепт по фото или списку продуктов.
Выберите действие из меню ниже.

[📋 Главное] [❓ Помощь]
[💾 Сохранённые] [⚙️ Настройки]
```

Вы всегда можете вернуться в главное меню, нажав кнопку "📋 Главное". 