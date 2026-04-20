# Preflight — adaptive multi-expert panel skill

## Context

У пользователя (Kirill) уже есть в экосистеме навыки для параллельной работы агентов, но ни один не покрывает **«одна задача / N независимых экспертов разных профессий»**:

- `superpowers:dispatching-parallel-agents` — раздаёт **разные задачи** агентам.
- `plan-critic` — **один** contrarian-критик опуса, произвольная свобода критики.
- `requesting-code-review` — **один** reviewer после кода.
- `orchestrator` — делегирование кодовой работы для длинных сессий.

Паттерн «собрать панель экспертов под артефакт» пользователь уже применяет вручную (пример — ревью Polymarket copy-bot: Quant trader + Risk manager + Market microstructure + Data scientist). Цель — закрепить это как адаптивный навык, который **до написания кода** прогоняет план/спек/текущее обсуждение через подобранную под задачу панель независимых экспертов. Ниша: pre-write review. Артефакты: план-файл, дизайн-спека, текущий диалог.

Проект будет лежать в `~/programming/claude/preflight/`, позже выкладывается в open-source на GitHub.

## Ключевые решения (закрыты в брейнштурме)

| Решение | Значение |
|---|---|
| Имя | `preflight` |
| Принцип | **1 агент = 1 роль**, независимость (пользователь: «лучше больше агентов чем мультиагент») |
| Каталог ролей | **Гибрид**: базовый каталог + domain-specific на лету |
| Хранение ролей | **Файл на роль** `roles/*.md` (PR-friendly, markdown-промпты) |
| Workflow | **Wide-net → Prune** → human gate → parallel dispatch → synthesize |
| Human gate | **ВКЛ по умолчанию** после Pruner (пользователь видит состав, может edit/abort) |
| Context pack | **Auto-detect**: собирается только для код-задач, пропускается для чистого диалога |
| Размещение | `~/programming/claude/preflight/` → опенсорс |

## Архитектура

Три мета-агента + N экспертов + главный координатор (тот, кто вызвал `/preflight`).

```
Главный агент (шаги 1-3, 7-8, 10):
  Ingest → Brief → Context decide
    ↓
  Roster-gen (meta-agent #1)       — предлагает МАКСИМУМ релевантных ролей
    ↓
  Pruner (meta-agent #2)           — отсекает дубли/бесполезных, cap=8
    ↓
  [Human gate: ok / edit / abort]  — показ состава, пауза под подтверждение
    ↓
  Parallel dispatch (шаг 7):
    Expert #1 ─┐
    Expert #2 ─┤   каждый получает brief + context_pack + свой roles/<name>.md
    Expert #3 ─┤   возвращает ExpertReport JSON по единой схеме
    ...       ─┘
    ↓
  Synthesizer (meta-agent #3)      — дедуп + severity grouping + conflict detection
    ↓
  Report (главный агент)           — финальный markdown-отчёт пользователю
```

## Пайплайн — 10 шагов

1. **Ingest** — главный: определить `target_type` ∈ {file, chat, inline}, загрузить исходник.
2. **Brief** — главный: выжать `brief.md` = 1 абзац цели + критерии успеха.
3. **Context decide** — главный (эвристика): нужен ли context pack.
4. **Context pack** (если да) — главный или `researcher`: `context_pack.md` ≤10k токенов.
5. **Roster-gen** — мета-агент №1: читает brief + `roles/index.json`, возвращает wide roster 5-15 ролей с обоснованием.
6. **Pruner** — мета-агент №2: отсекает до 3-8, возвращает `roster_final.json` + `dropped` (прозрачность).
7. **Human gate** — пользователь видит состав, отвечает `ok` / `edit` / `abort`.
8. **Dispatch** — главный: N параллельных `Agent` вызовов в одном message.
9. **Collect + Synthesize** — мета-агент №3: дедуп, severity (MUST/SHOULD/NICE), conflicts, verdict (APPROVE/REVISE/REJECT).
10. **Report** — главный: структурированный markdown + actionable list.

## Формат данных

**ExpertReport** (единый для всех экспертов, парсит Synthesizer):
```json
{
  "role": "security",
  "verdict": "APPROVE" | "REVISE" | "REJECT",
  "must_fix":  [{"title": "...", "evidence": "...", "replacement": "..."}],
  "should_fix": [...],
  "nice_fix":   [...],
  "out_of_scope": ["производительность — не моя роль"]
}
```

**Роль в каталоге** (`skills/preflight/roles/<name>.md`):
```markdown
---
name: security
when_to_pick: "Задача касается auth, пользовательского ввода, секретов, криптографии..."
tags: [security, input-validation, crypto, secrets]
skip_when: "Чисто UI-текст, документация, локальный скрипт без ввода..."
---
# Роль: Security Engineer
Ты — security engineer. Твоя единственная задача: ...
## Что ты ищешь: injection, утечки секретов, IDOR, ...
## Что ты НЕ трогаешь: perf, UX, cost — это чужие роли
## Формат ответа: строго ExpertReport JSON
## Anti-patterns: "возможно стоит проверить", generic advice, дубли других ролей
```

## Структура репо

```
~/programming/claude/preflight/
├── README.md                          # описание, установка, примеры
├── LICENSE                            # MIT
├── .gitignore
├── CHANGELOG.md
├── skills/preflight/
│   ├── SKILL.md                       # frontmatter + тело навыка
│   ├── roles/
│   │   ├── index.json                 # авто-генерится build_index.py
│   │   ├── security.md
│   │   ├── performance.md
│   │   ├── testing.md
│   │   ├── concurrency.md
│   │   ├── api-design.md
│   │   ├── data-model.md
│   │   ├── ops-reliability.md
│   │   ├── cost-infra.md
│   │   ├── supply-chain.md
│   │   └── contrarian-strategist.md   # MVP v0: 10 ролей
│   ├── meta-agents/
│   │   ├── roster-gen.md
│   │   ├── pruner.md
│   │   └── synthesizer.md
│   ├── schemas/
│   │   ├── expert-report.json
│   │   ├── roster.json
│   │   └── synthesis.json
│   └── scripts/build_index.py         # *.md frontmatter → index.json
├── docs/
│   ├── specs/2026-04-20-preflight-design.md   # клонированный этот план
│   ├── examples/phase-b-llm-advisor/          # реальный пример прогона
│   └── CONTRIBUTING.md                # как добавить роль = один PR
└── evals/
    ├── README.md
    ├── fixtures/                      # 6-10 фикстур
    │   ├── plan-good/
    │   ├── plan-buggy-auth/
    │   ├── plan-buggy-concurrency/
    │   ├── chat-trading-bot/
    │   └── chat-solid/
    ├── grading.json                   # expected findings per fixture
    └── run_eval.py                    # прогоняет preflight vs baseline
```

## Порядок реализации (после ExitPlanMode)

### Milestone 0 — Scaffold & meta-experiment (первая сессия)
1. `mkdir -p ~/programming/claude/preflight && git init`
2. Создать `README.md` (описание + статус WIP), `LICENSE` (MIT), `.gitignore`.
3. **Клонировать этот план в `docs/specs/2026-04-20-preflight-design.md`.**
4. Initial commit: `initial design: preflight adaptive expert panel`.
5. **Мета-эксперимент**: применить `plan-critic` к `docs/specs/2026-04-20-preflight-design.md`. Получить MUST/SHOULD/NICE на наш же дизайн.
6. Итерация spec: применить значимый фидбек, закоммитить `iterate design after plan-critic pass`.

### Milestone 1 — Catalog + meta-agents (vertical slice)
7. Написать `skills/preflight/SKILL.md` с frontmatter (triggers из Section 6) и ссылками на meta-agents/roles.
8. Написать `meta-agents/roster-gen.md`, `pruner.md`, `synthesizer.md` по скелетам из спеки.
9. Создать 3 базовые роли для dog-food: `roles/security.md`, `performance.md`, `contrarian-strategist.md`.
10. Написать `scripts/build_index.py` — регенерирует `roles/index.json` из frontmatter всех `roles/*.md`.
11. Написать `schemas/*.json` (JSON-schemas для ExpertReport, roster, synthesis).

### Milestone 2 — Первый живой прогон
12. Симлинк `~/.claude/skills/preflight` → `~/programming/claude/preflight/skills/preflight`.
13. Запустить `/preflight` на искусственном простом plan-файле (auth-bug фикстура). Проверить что:
    - Roster-gen предлагает security + что-то ещё.
    - Pruner отсекает нерелевантных.
    - Human gate корректно отображается.
    - Эксперты возвращают валидный ExpertReport JSON.
    - Synthesizer дедуплицирует и даёт verdict.
14. Если что-то ломается — зафиксировать в `docs/issues-found.md` и итерировать промпты.

### Milestone 3 — Расширить каталог до MVP v0
15. Дописать недостающие 7 ролей (testing, concurrency, api-design, data-model, ops-reliability, cost-infra, supply-chain).
16. Прогнать `/preflight` на `docs/examples/phase-b-llm-advisor/` (реальный пример из Polymarket-диалога). Зафиксировать результат в `docs/examples/`.

### Milestone 4 — Evals suite
17. Собрать `evals/fixtures/` (6-10 сценариев) + `grading.json` с ожидаемыми находками.
18. Написать `evals/run_eval.py`: прогоняет каждую фикстуру через 3 baseline'а (plan-critic / preflight --auto / preflight) и собирает precision, recall, cost, latency.
19. Опубликовать первый отчёт `evals/report-2026-05-xx.md`.

### Milestone 5 — Open-source
20. Чистовой `README.md` с примерами, скриншотами, установкой.
21. `CONTRIBUTING.md`: как добавить роль (один PR = один `roles/<name>.md`).
22. Создать GitHub repo, push, LICENSE review, tag `v0.1.0`.

## Критические файлы для создания

- `~/programming/claude/preflight/skills/preflight/SKILL.md` — главный навык
- `~/programming/claude/preflight/skills/preflight/meta-agents/{roster-gen,pruner,synthesizer}.md` — мета-агенты
- `~/programming/claude/preflight/skills/preflight/roles/{security,performance,contrarian-strategist}.md` — первые 3 роли для dog-food
- `~/programming/claude/preflight/skills/preflight/schemas/expert-report.json` — контракт ответа эксперта
- `~/programming/claude/preflight/skills/preflight/scripts/build_index.py` — генератор индекса
- `~/programming/claude/preflight/docs/specs/2026-04-20-preflight-design.md` — эта спека для мета-эксперимента

## Reusable existing utilities

- **`plan-critic`** (`~/.claude/skills/plan-critic/`) — используется как baseline в evals и для мета-эксперимента на Milestone 0 шаг 5. Не дублируем логику.
- **Шаблон роли** — формат `superpowers:skill-creator/agents/*.md` (grader, comparator, analyzer) — паттерн «один файл = один focused agent». Используем как образец структуры.
- **`researcher`** (`~/.claude/skills/researcher/`) — возможный исполнитель шага 4 (Context pack). Если задача про код, главный агент делегирует сбор контекста ему.
- **`dispatching-parallel-agents`** (superpowers) — наш навык это его специализация; читать как reference по параллельному dispatch.

## Verification

Критерии «навык работает» (end-to-end):

1. **Scaffold test:** `ls ~/programming/claude/preflight/skills/preflight/roles/*.md` возвращает ≥3 файла, `python scripts/build_index.py` генерирует непустой `index.json`.

2. **Smoke run:** `/preflight <path-to-buggy-plan.md>` отрабатывает все 10 шагов без падений, показывает human gate, завершается финальным Report с verdict REVISE или REJECT.

3. **Roster quality:** на фикстуре `plan-buggy-auth/` Roster-gen предлагает роль `security` (иначе баг Roster-gen). Pruner не выкидывает её (иначе баг Pruner). Эксперт `security` находит заложенную дыру (иначе баг промпта роли).

4. **Synthesis quality:** при прогоне на фикстуре с намеренным конфликтом (security vs performance про кэширование) Synthesizer кладёт находку в секцию `disputed`, а не в одну из сторон.

5. **Meta-experiment:** `plan-critic`, применённый к `docs/specs/2026-04-20-preflight-design.md`, возвращает verdict `APPROVE` или `REVISE` (не `REJECT`) после итерации спеки. Если REJECT — дизайн нуждается в пересмотре до имплементации.

6. **Evals baseline (Milestone 4):** на multi-domain фикстуре recall панели ≥ одиночного `plan-critic` по крайней мере на 30%. Если нет — ценность навыка не подтверждена и нужно пересматривать роли или промпты.

## Известные open questions (фиксируем в spec-документе, решаем по ходу)

- Защита от prompt injection в читаемом артефакте (эксперты не должны выполнять инструкции из plan-файла).
- Retry policy если эксперт вернул невалидный JSON (retry 1 раз → skip → отметить в Report).
- Локализация: пользователь пишет по-русски, каталог ролей по-английски — смешиваем или всё на одном языке? (предварительно: каталог on English, отчёты на языке brief).
- Diff-режим: сравнение двух версий артефакта — отложено за MVP.
