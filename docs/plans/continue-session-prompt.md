# Промпт для проверочной сессии v0.7.0

Скопируй этот текст в новую сессию Claude Code:

---

## Задача: Ручная проверка superpowers-интеграции v0.7.0

В предыдущей сессии мы реализовали интеграцию паттернов из superpowers plugin в codegen-bridge (v0.6.0 → v0.7.0). Нужно проверить всё детально.

### Что было сделано

**4 новых skills:**
- `skills/using-codegen-bridge/SKILL.md` — мета-skill, инъектируется при SessionStart
- `skills/debugging-failed-runs/SKILL.md` — 4-фазная отладка failed runs
- `skills/prompt-crafting/SKILL.md` — гайд по промптам для агентов
- `skills/reviewing-agent-output/SKILL.md` — двухэтапное ревью (spec + quality)

**Prompt templates:**
- `skills/codegen-delegation/templates/task-prompt-template.md`
- `skills/codegen-delegation/templates/multi-step-prompt-template.md`

**Инфраструктура:**
- `hooks/scripts/session-start.sh` — SessionStart hook с детекцией superpowers
- `hooks/run-hook.cmd` — cross-platform polyglot wrapper
- `hooks/hooks.json` — добавлен SessionStart event

**Усиленные skills:**
- `skills/executing-via-codegen/SKILL.md` — добавлен two-stage review gate
- `skills/agent-monitoring/SKILL.md` — добавлены verification gates
- `skills/codegen-delegation/SKILL.md` — prompt quality checklist + template refs

**Обновлённая документация:**
- `.claude-plugin/plugin.json` → v0.7.0
- `CLAUDE.md` — обновлено описание
- `.claude/rules/plugin.md` — полная таблица skills/hooks/templates
- `docs/plans/2026-03-20-superpowers-integration.md` — дизайн-документ

### Что проверить

1. **SessionStart hook:**
   - Запустить `CLAUDE_PLUGIN_ROOT=$(pwd) bash hooks/scripts/session-start.sh` — должен вывести валидный JSON с `additionalContext`
   - Проверить что скрипт детектирует superpowers (у нас установлен)
   - Проверить что без superpowers тоже работает (убрать путь из проверки)
   - Проверить JSON-escaping спецсимволов (кавычки, переносы строк)
   - Проверить через `| python3 -m json.tool` для валидации JSON

2. **Cross-platform hook wrapper (`run-hook.cmd`):**
   - На macOS/Linux: `CLAUDE_PLUGIN_ROOT=$(pwd) bash hooks/run-hook.cmd session-start`
   - Проверить что вызывает правильный скрипт
   - Проверить что `chmod +x` установлен на оба файла

3. **Новые skills — качество контента:**
   - Прочитать каждый SKILL.md и проверить:
     - Frontmatter (name, description, user-invocable) корректен
     - Нет орфографических ошибок
     - Markdown форматирование валидно
     - Нет ссылок на несуществующие инструменты/skills
     - Decision trees и таблицы логичны
   - Проверить что `debugging-failed-runs` покрывает все типы ошибок из Codegen API
   - Проверить что `prompt-crafting` шаблоны соответствуют API формату `codegen_create_run`
   - Проверить что `reviewing-agent-output` стадии работают с реальными log форматами

4. **Усиленные skills — consistency:**
   - `executing-via-codegen`: two-stage review gate не ломает существующий flow
   - `agent-monitoring`: verification gates добавлены в правильном месте
   - `codegen-delegation`: template references указывают на существующие файлы

5. **Prompt templates:**
   - Структура соответствует Codegen API (prompt field)
   - Размер укладывается в рекомендованные 4000 chars
   - Нет placeholder'ов которые забыли заполнить

6. **hooks.json:**
   - Валидный JSON: `cat hooks/hooks.json | python3 -m json.tool`
   - SessionStart matcher `startup|clear|compact` корректен
   - Команда использует `run-hook.cmd` путь
   - Timeout адекватный (10 сек)

7. **Документация consistency:**
   - `plugin.json` version (0.7.0) совпадает с CLAUDE.md и plugin.md
   - Таблица skills в plugin.md совпадает с реальными файлами на диске
   - Keywords актуальны

8. **Тесты и линтинг:**
   - `uv run pytest -v` — все проходят
   - `uv run ruff check .` — без ошибок
   - `uv run mypy bridge/` — без ошибок

9. **Интеграционная проверка (ручная):**
   - Перезапустить Claude Code сессию с плагином
   - Убедиться что SessionStart hook инъектирует мета-skill
   - Попробовать вызвать `/codegen` — skill должен подхватиться
   - Попробовать `/cg-status` — verification gates должны работать

### Дизайн-документ

Прочитай `docs/plans/2026-03-20-superpowers-integration.md` для полного контекста решений.

### Справка по superpowers-источнику

Репозиторий-источник: https://github.com/obra/superpowers (v5.0.5)
Из него взяты: структурные паттерны (SessionStart injection, meta-skill, prompt templates, verification gates, two-stage review).
НЕ взяты: процессные skills (TDD, brainstorming, planning, debugging, code review) — они уже есть через superpowers plugin.
