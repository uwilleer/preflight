# Plan: Nightly report generator

## Goal

Generate a PDF report per customer every night at 02:00 UTC, upload to S3, email the signed URL.

## Stack

- Python + APScheduler (runs inside the main API pod)
- `reportlab` for PDF
- Boto3 for S3
- SendGrid for email

## Implementation

### 1. Scheduled job

```python
scheduler = AsyncIOScheduler()

@scheduler.scheduled_job("cron", hour=2, minute=0)
async def generate_reports():
    customers = db.query(Customer).filter_by(active=True).all()
    for customer in customers:
        pdf = build_pdf(customer)
        url = upload_to_s3(pdf, f"reports/{customer.id}/{today()}.pdf")
        send_email(customer.email, url)

scheduler.start()
```

### 2. PDF build

```python
def build_pdf(customer):
    data = aggregate_metrics(customer.id)  # runs ~30 SQL queries
    return render_template("report.pdf.j2", data=data)
```

### 3. Success path

On success, each customer receives an email with a signed URL valid for 7 days. No status is persisted — if the same job runs twice, customers get two emails. That's acceptable.

## What we're NOT doing

- Per-customer job status tracking (no DB table for job runs)
- Retry on failure (next night will regenerate anyway)
- Idempotency (double-emails are acceptable)

## Success criteria

At 02:00 UTC each night, every active customer receives their report by email.
