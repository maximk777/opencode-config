# Карта домена demo

Таблицы между маркерами `map:` генерирует `python3 tools/generate.py` из `map/*.md`; всё остальное пишется вручную.

## Экраны
<!-- map:screens:begin -->
| key | route | kind | section | parent | access | label | wave | story |
|---|---|---|---|---|---|---|---|---|
| screen:demo/card | /cards/:id | place | Карточки | screen:demo/list | open question | Карточка | 1 |  |
| screen:demo/list | /cards | place | Карточки |  | getCards | Список карточек | 1 | story:demo/list |
<!-- map:screens:end -->

## Переходы
<!-- map:переходы:begin -->
| Откуда | Действие | Цель |
|---|---|---|
| screen:demo/card | Назад к списку | screen:demo/list |
| screen:demo/list | Открыть карточку | screen:demo/card |
<!-- map:переходы:end -->

## Навигация
Нет в исходной карте.

## Трасса legacy
| Группа legacy | Пункт legacy | Маршрут legacy | Цель |
|---|---|---|---|

## Решения
[adr:0001](../../docs/adr/0001-cards.md): список и карточка становятся двумя экранами.

## Открытые вопросы
- screen:demo/card: `access: open question`, у экрана нет стори, поэтому раздел «Права» в `front.md` не называет операцию (domains/demo/docs/SITEMAP.md, строка 13).
