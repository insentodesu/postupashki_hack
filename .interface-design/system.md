# Поступашки Measurement Desk UI System

## Direction

Инструментальная панель для маркетолога, который проверяет путь от placement до выручки. Визуальный язык спокойный и точный: холодное поле, белые рабочие листы, один cobalt-акцент и семантические цвета только для состояния.

## Dials

- `DESIGN_VARIANCE`: 5/10. Небольшая асимметрия в колонках и навигации без декоративного хаоса.
- `MOTION_INTENSITY`: 3/10. Быстрые hover/focus/press состояния, без бесконечных анимаций.
- `VISUAL_DENSITY`: 6/10. Плотность рабочего инструмента, но с отдельными зонами воздуха вокруг ключевых метрик.

## Tokens and depth

- База 4/8 px.
- Один радиусный масштаб: 8 px для controls, 12 px для sheets, 14 px для raised surfaces.
- В светлой теме используются мягкие слои и тонкая граница. В тёмной теме глубина держится на границе, а не на тяжёлой тени.
- Акцент: cobalt `#315efb` в светлой теме и его светлый вариант в тёмной.

## Reusable patterns

- Sidebar: 232 px, active item marked by a 3 px accent inset.
- Metric strip: four-column grid with tabular numeric values.
- Flow rail: Placement -> Touch -> Lead -> Revenue, with the arrows communicating progression.
- Operational action dock: tab list on the left, labelled forms on the right, one primary submit action.
- Status language: `real`, `synthetic`, `demo`, `deterministic`, `unknown`.

## Accessibility

- System dark mode is supported with the same hierarchy.
- Visible focus rings use the cobalt focus token.
- Labels stay above fields, placeholders are supporting text only.
- Reduced motion disables transitions and animation duration.
