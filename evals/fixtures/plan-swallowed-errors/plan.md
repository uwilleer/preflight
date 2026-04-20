# Plan: Webhook delivery service

## Goal

Deliver webhooks from our platform to customer endpoints. Retry on failure. Mark as delivered.

## Stack

- Python + FastAPI
- Celery + Redis for background delivery
- PostgreSQL for `webhook_events` table

## Implementation

### 1. Enqueue webhook on event

```python
@app.post("/events")
async def on_event(event: Event, db: Session = Depends(get_db)):
    row = WebhookEvent(customer_id=event.customer_id, payload=event.dict())
    db.add(row)
    db.commit()
    deliver_webhook.delay(row.id)
    return {"ok": True}
```

### 2. Background delivery task

```python
@celery.task
def deliver_webhook(event_id: int):
    event = db.query(WebhookEvent).filter_by(id=event_id).first()
    try:
        requests.post(event.customer_url, json=event.payload)
        event.delivered = True
        db.commit()
    except Exception:
        pass  # will retry on next cron pass
```

### 3. Retry sweep (cron, every 5 min)

```python
@celery.task
def retry_undelivered():
    pending = db.query(WebhookEvent).filter_by(delivered=False).all()
    for event in pending:
        deliver_webhook.delay(event.id)
```

## What we're NOT doing

- Exponential backoff (retry sweep runs every 5 min, that's enough)
- Dead-letter queue (failing events retry forever — that's fine, customer will eventually fix their endpoint)
- Signature / HMAC on payload (customer trusts our origin)

## Success criteria

Webhooks are delivered to customer endpoints. Failed deliveries retry until success.
