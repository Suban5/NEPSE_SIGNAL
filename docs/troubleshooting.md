# Troubleshooting

Metadata:
Owner: suban
Last Reviewed: 2026-04-05
Source of Truth: cli/commands.py, api/app.py, nepse_api/data_fetcher.py
Validation Method: Code + Tests

## Health Check Fails

Run:

```bash
python main.py health-check --symbol NABIL
```

Common causes:

- upstream API returned empty snapshot
- historical rows unavailable for requested symbol/date
- network or TLS verification issues

## API Timeout on Floor Sheet

Use higher timeout_seconds:

```text
GET /trading/floor-sheet?show_progress=false&timeout_seconds=120
```

## Upstream 401/403/5xx Behavior

The API maps upstream errors to structured error payloads and preserves status when available.

## TLS Issues

- keep NEPSE_TLS_VERIFY=true in secure environments
- use false only for controlled local debugging

## Increase Logging

```bash
export LOG_LEVEL=DEBUG
python main.py health-check --symbol NABIL
```
