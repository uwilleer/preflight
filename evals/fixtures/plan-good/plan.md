# Plan: User Preferences API

## Goal

Allow users to save and retrieve their UI preferences (theme, language, notification settings). Preferences are per-user, private.

## Stack

- Python + FastAPI
- PostgreSQL
- Redis for caching (already in stack)

## Data model

```sql
CREATE TABLE user_preferences (
  user_id    INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
  theme      TEXT NOT NULL DEFAULT 'light' CHECK (theme IN ('light', 'dark', 'system')),
  language   TEXT NOT NULL DEFAULT 'en' CHECK (language ~ '^[a-z]{2}(-[A-Z]{2})?$'),
  notif_email BOOLEAN NOT NULL DEFAULT TRUE,
  notif_push  BOOLEAN NOT NULL DEFAULT FALSE,
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

## Endpoints

### GET /me/preferences

```python
@app.get("/me/preferences", response_model=PreferencesOut)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis)
):
    cached = await cache.get(f"prefs:{current_user.id}")
    if cached:
        return PreferencesOut.parse_raw(cached)

    prefs = db.query(UserPreferences).filter_by(user_id=current_user.id).first()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)
        db.commit()

    result = PreferencesOut.from_orm(prefs)
    await cache.setex(f"prefs:{current_user.id}", 300, result.json())
    return result
```

### PATCH /me/preferences

```python
class PreferencesPatch(BaseModel):
    theme: Optional[Literal['light', 'dark', 'system']] = None
    language: Optional[str] = Field(None, pattern=r'^[a-z]{2}(-[A-Z]{2})?$')
    notif_email: Optional[bool] = None
    notif_push: Optional[bool] = None

@app.patch("/me/preferences", response_model=PreferencesOut)
async def update_preferences(
    body: PreferencesPatch,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    cache: Redis = Depends(get_redis)
):
    prefs = db.query(UserPreferences).filter_by(user_id=current_user.id).first()
    if not prefs:
        prefs = UserPreferences(user_id=current_user.id)
        db.add(prefs)

    for field, value in body.dict(exclude_none=True).items():
        setattr(prefs, field, value)
    prefs.updated_at = datetime.now(timezone.utc)
    db.commit()

    await cache.delete(f"prefs:{current_user.id}")
    return PreferencesOut.from_orm(prefs)
```

## Auth

Both endpoints use `get_current_user` dependency (Bearer token, already implemented). Users can only read/write their own preferences — `user_id` comes from the token, never from the request body.

## Testing plan

- Happy path: GET returns defaults for new user, PATCH updates and invalidates cache
- Auth: unauthenticated → 401, wrong token → 401
- Validation: invalid theme → 422, invalid language code → 422
- Cache: second GET hits cache (mock Redis), PATCH invalidates it
- Concurrent PATCH: two simultaneous updates — last write wins (acceptable for preferences)

## What we're NOT doing

- Preference history/audit log
- Admin endpoint to view other users' preferences

## Success criteria

Users can read and update their preferences. Changes reflected immediately. Cache TTL 5 minutes.
