# Multi-source Product Agent (strict)

Усиленная версия агента поиска по источникам.

## Что улучшено
- `matched=true` выставляется только после детерминированной валидации.
- Landing / login / unavailable / registration страницы отбрасываются.
- LLM не решает, найден товар или нет — она только кратко пересказывает уже подтверждённый фрагмент.
- Результат содержит тип совпадения, вид суммы, валюту, поставщика/заказчика, номер реестра и доказательство.
- Часть слабых источников отключена по умолчанию в `app/data/sources.json`.

## Быстрый запуск
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium
ollama pull qwen2.5:3b
uvicorn app.main:app --reload
```

Swagger: http://127.0.0.1:8000/docs

## Запрос
```json
{
  "product_name": "ручка шариковая",
  "max_results_per_source": 3,
  "include_disabled": false
}
```

## Что такое хороший ответ
- `matched=true` только если товар реально найден в тексте/выгрузке/карточке.
- Если источник — реестр без цены, вернётся `amount_kind=registry_only`.
- Если источник — тендер, сумма будет классифицирована как `contract_amount`.
