# Trust Score

Behavioral trust scoring for users based on security events.

## What is it?

Score range: 0-1000 (start at 500)

The algorithm makes it:
- hard to max out (diminishing returns)
- painful to fall from high scores
- easy to recover from low scores

## Algorithm

```
positive: s = s + alpha * (1000 - s)
negative: s = s * (1 - alpha)
```

Weight `w` means apply the step `w` times. Default alpha = 0.25.

### Example

User at 900 gets hit with weight-2 negative:
```
900 -> 675 -> 506
```

User at 300 gets weight-2 positive:
```
300 -> 475 -> 606
```

## Event types

| Subtype | Type | Weight |
|---------|------|--------|
| PATCH_ON_TIME | + | 1 |
| PATCH_LATE | - | 1 |
| PATCH_OVERDUE | - | 2 |
| IR_ON_TIME | + | 2 |
| IR_LATE | - | 2 |
| IR_IGNORED | - | 3 |
| TRAINING_ON_TIME | + | 1 |
| TRAINING_LATE | - | 1 |
| TRAINING_NOT_DONE | - | 2 |
| PHISH_REPORTED_VALID | + | 2 |
| PHISH_NOT_REPORTED_AND_CLICKED | - | 2 |
| PHISH_REPORTED_FALSE_ALARM | 0 | 0 |

## Guardrails

- Dedup by `(user_id, category, object_id)` - one event per object
- Freq caps on phishing reports (2/week max)
- Deadline tracking to prevent double-counting

## Setup

```bash
# docker
docker-compose up -d

# or local
pip install -r requirements.txt
PYTHONPATH=. uvicorn src.api.main:app --reload
```

API docs at http://localhost:8000/docs

## Project layout

```
src/
  api/       - REST endpoints (FastAPI)
  pylibs/    - core logic
  db/        - SQLAlchemy models
  cronjob/   - scheduled tasks
```

## API

```bash
# submit event
curl -X POST localhost:8000/events \
  -H "Content-Type: application/json" \
  -d '{"user_id":"jsmith","category":"PATCHING","type":"POSITIVE","context":{"object_id":"srv01-jan"}}'

# get user
curl localhost:8000/users/jsmith

# simulate
curl -X POST localhost:8000/simulate \
  -H "Content-Type: application/json" \
  -d '{"current_score":500,"event_type":"NEGATIVE","weight":2}'
```

## Config

| Param | Default | Notes |
|-------|---------|-------|
| initial score | 500 | neutral |
| alpha | 0.25 | change rate |
| DATABASE_URL | postgres://...localhost/trust_score | |

## Scheduled tasks

- `overdue` - check missed deadlines (hourly)
- `validation` - sanity check scores (daily)
- `cleanup` - remove old events >90d (weekly)
- `report` - generate stats (daily)
