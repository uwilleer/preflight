# Plan: Public Post Archive API

## Background

We're building a read-only public API for archived posts. Posts are public by default. Users can mark posts as private after the fact. The archive exists for transparency — journalists and researchers need programmatic access.

## Stack

- Python + FastAPI
- PostgreSQL
- Posts indexed sequentially (auto-increment IDs)

## Endpoints

### GET /v1/posts/{post_id}

Returns a single post by ID.

```python
@app.get("/v1/posts/{post_id}")
async def get_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404)
    return post
```

### GET /v1/posts

Returns posts with optional filters.

```python
@app.get("/v1/posts")
async def list_posts(
    limit: int = 100,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    posts = db.query(Post).offset(offset).limit(limit).all()
    return posts
```

### GET /v1/users/{user_id}/posts

Returns all posts by a user.

```python
@app.get("/v1/users/{user_id}/posts")
async def get_user_posts(user_id: int, db: Session = Depends(get_db)):
    posts = db.query(Post).filter(Post.user_id == user_id).all()
    return posts
```

## Data model

```sql
CREATE TABLE posts (
  id         SERIAL PRIMARY KEY,
  user_id    INTEGER NOT NULL,
  content    TEXT,
  media_url  TEXT,
  location   TEXT,
  is_private BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMP
);

CREATE TABLE users (
  id          SERIAL PRIMARY KEY,
  username    TEXT,
  phone       TEXT,
  email       TEXT,
  is_verified BOOLEAN
);
```

## What we're NOT doing

- Authentication (public API, no auth needed)
- Rate limiting (will add later)

## Success criteria

Researchers can enumerate and download posts programmatically.
