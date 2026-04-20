# Plan: User Authentication Service

## Goal

Implement a JWT-based authentication service for our web app. Users log in with email/password, get a token, and use it for subsequent requests.

## Stack

- Python + FastAPI
- PostgreSQL for user storage
- PyJWT for token signing

## Implementation Plan

### 1. Database schema

```sql
CREATE TABLE users (
  id       SERIAL PRIMARY KEY,
  email    TEXT UNIQUE,
  password TEXT,
  role     TEXT DEFAULT 'user'
);
```

Passwords stored as-is (we'll add hashing later).

### 2. Login endpoint

```python
@app.post("/login")
async def login(email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user or user.password != password:
        raise HTTPException(status_code=401)
    token = jwt.encode(
        {"sub": user.id, "role": user.role, "exp": datetime.utcnow() + timedelta(days=30)},
        SECRET_KEY,
        algorithm="HS256"
    )
    return {"token": token}
```

### 3. Protected endpoint

```python
@app.get("/admin/users")
async def list_users(token: str = Header(...), db: Session = Depends(get_db)):
    payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    users = db.query(User).all()
    return users
```

### 4. User registration

```python
@app.post("/register")
async def register(email: str, password: str, role: str = "user", db: Session = Depends(get_db)):
    user = User(email=email, password=password, role=role)
    db.add(user)
    db.commit()
    return {"id": user.id}
```

### 5. Secret key

We'll put `SECRET_KEY = "supersecret123"` in `config.py` and commit to git.

## What we're NOT doing in v1

- Rate limiting (will add later)
- Token refresh (out of scope)
- Email verification (out of scope)

## Success criteria

Users can log in and access protected endpoints. Admins can list all users.
