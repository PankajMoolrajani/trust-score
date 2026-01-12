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

## Event types (including, but not limited to, the following examples)
The system uses diverse types of behavioral events to calculate trust score. Events **are not limited to the below examples**—additional types may be added as needed.

### Phishing & Social Engineering Behavior
| Subtype                                   | Type | Weight | object_id           | Idea                     |
|--------------------------------------------|------|--------|---------------------|--------------------------|
| PHISH_SIM_REPORTED                        | +    | 2      | sim_email_id        | Simulated phish reported |
| PHISH_SIM_IGNORED                         | -    | 1      | sim_email_id        | Ignored simulated phish  |
| PHISH_SIM_CLICKED                         | -    | 2      | sim_email_id        | Clicked sim phish        |
| PHISH_SIM_CREDENTIALS_SUBMITTED           | -    | 4      | sim_email_id        | Entered creds in sim phish |
| SUSPICIOUS_CALL_REPORTED                  | +    | 2      | call_case_id        | Reported suspicious call |
| SUSPICIOUS_SMS_REPORTED                   | +    | 2      | sms_id              | Reported suspicious SMS  |
| SUSPECTED_VISHING_FELL_FOR                | -    | 3      | call_case_id        | Fell for vishing attempt |

> *(You already have real-phish types—these cover simulations and vishing/smishing behavior)*

### “Responsiveness” to Security (tickets, nudges, requests)
| Subtype                                   | Type | Weight | object_id        | Idea                                 |
|--------------------------------------------|------|--------|------------------|--------------------------------------|
| SECURITY_REQUEST_ACKED_FAST                | +    | 1      | ticket_id        | Responded to security request quickly|
| SECURITY_REQUEST_ACKED_LATE                | -    | 1      | ticket_id        | Acknowledged late                    |
| SECURITY_REQUEST_IGNORED                   | -    | 2      | ticket_id        | Ignored request                      |
| SECURITY_QUESTION_ANSWERED_CLEARLY         | +    | 1      | ticket_id        | Clear/helpful answer                 |
| SECURITY_QUESTION_STALLED                  | -    | 1      | ticket_id        | Stalled on answer                    |
| SECURITY_EXCEPTION_REQUESTED_WITH_MITIGATIONS | + | 1      | exception_id     | Sought mitigation for exception      |
| SECURITY_EXCEPTION_REQUESTED_NO_MITIGATIONS   | - | 1      | exception_id     | No mitigation for exception          |

### Policy Compliance Decisions (behavior, not tooling)
| Subtype                                   | Type | Weight | object_id        | Idea                                 |
|--------------------------------------------|------|--------|------------------|--------------------------------------|
| DATA_SHARED_VIA_APPROVED_CHANNEL           | +    | 1      | share_request_id | Shared using approved channel        |
| DATA_SHARED_VIA_UNAPPROVED_CHANNEL         | -    | 2      | share_request_id | Used unapproved method               |
| FILE_SHARED_WITH_WRONG_RECIPIENT           | -    | 3      | incident_id      | Mis-shared file                      |
| CORRECTED_MISSHARE_PROMPTLY                | +    | 1      | incident_id      | Fixed mis-share quickly              |
| BYPASS_ATTEMPTED_FOR_REVIEW_PROCESS        | -    | 2      | request_id       | Tried to bypass process              |
| FOLLOWED_CHANGE_PROCESS                    | +    | 1      | change_id        | Followed prescribed change process   |
| WORKAROUND_USED_TO_SKIP_CHANGE_PROCESS     | -    | 2      | change_id        | Worked around process                |

### Credential / Auth Hygiene (purely behavior)
| Subtype                                   | Type | Weight | object_id        | Idea                                 |
|--------------------------------------------|------|--------|------------------|--------------------------------------|
| MFA_PROMPT_REPORTED_AS_SUSPICIOUS          | +    | 2      | mfa_event_id     | Reported unexpected MFA              |
| MFA_PUSH_APPROVED_UNEXPECTEDLY              | -    | 4      | mfa_event_id     | Approved unexpected MFA push         |
| PASSWORD_RESET_AFTER_SUSPICION             | +    | 1      | case_id          | Reset password after suspicion       |
| SHARED_PASSWORD_WITH_TEAMMATE              | -    | 3      | case_id          | Shared password                      |
| STORED_SECRET_IN_UNAPPROVED_PLACE          | -    | 3      | artifact_id      | Unsafe secret storage                |

> *These track security-related choices, not just whether MFA is enabled.*

### Incident Participation & Hygiene
| Subtype                                   | Type | Weight | object_id        | Idea                                 |
|--------------------------------------------|------|--------|------------------|--------------------------------------|
| REPORTED_SECURITY_INCIDENT                 | +    | 2      | incident_id      | Prompt reporting                     |
| DELAYED_REPORTING_KNOWN_INCIDENT           | -    | 2      | incident_id      | Delayed reporting                    |
| PROVIDED_REQUESTED_EVIDENCE_ON_TIME        | +    | 1      | incident_id      | Helpful participation                |
| FAILED_TO_PROVIDE_EVIDENCE                 | -    | 2      | incident_id      | Didn't provide evidence              |
| FOLLOWED_CONTAINMENT_INSTRUCTIONS          | +    | 2      | incident_id      | Followed instructions                |
| VIOLATED_CONTAINMENT_INSTRUCTIONS          | -    | 4      | incident_id      | Didn't follow instructions           |

### Training & Awareness (beyond “completed training”)
| Subtype                                   | Type | Weight | object_id          | Idea                           |
|--------------------------------------------|------|--------|--------------------|--------------------------------|
| OPTIONAL_TRAINING_COMPLETED                | +    | 1      | course_id          | Went above baseline            |
| SECURITY_BROWN_BAG_ATTENDED                | +    | 1      | session_id         | Attended extra session         |
| REPEATED_POLICY_QUIZ_FAILURE               | -    | 1      | quiz_id            | Quiz failures                  |
| SECURITY_COACHING_ACCEPTED                 | +    | 1      | coaching_case_id   | Accepted coaching              |
| SECURITY_COACHING_IGNORED                  | -    | 2      | coaching_case_id   | Ignored coaching               |

### Repeat-Offender and Improvement Signals (behavior pattern events)
Derived, window-based behaviors: these encode recurrence or sustained improvement.

| Subtype                                   | Type | Weight | object_id   | Idea                            |
|--------------------------------------------|------|--------|-------------|---------------------------------|
| REPEATED_PHISH_FAILURE_30D                 | -    | 3      | window_30d  | Repeat phish failures           |
| REPEATED_POLICY_VIOLATION_30D              | -    | 3      | window_30d  | Repeat offenses                 |
| CONSISTENT_GOOD_BEHAVIOR_30D               | +    | 2      | window_30d  | Maintained good behavior        |
| BEHAVIOR_IMPROVED_AFTER_COACHING           | +    | 2      | coaching_case_id | Measurable improvement        |

**Note:** Some events are derived (aggregated over time windows by scheduled jobs), but all represent user behavior.

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
