# Plan: Post View Counter

## Goal

Track view counts for posts. Show accurate view counts on post pages. Increment on each page view.

## Stack

- Python + FastAPI
- PostgreSQL (posts table already exists with a `view_count INTEGER DEFAULT 0` column)
- Redis for caching hot counters

## Implementation

### 1. Increment on view

```python
@app.get("/posts/{post_id}")
async def view_post(post_id: int, db: Session = Depends(get_db)):
    post = db.query(Post).filter(Post.id == post_id).first()
    if not post:
        raise HTTPException(404)

    # Increment view count
    post.view_count += 1
    db.commit()

    return post
```

### 2. Cached hot counters

For posts getting >100 views/minute, buffer in Redis to avoid DB write pressure:

```python
async def increment_view(post_id: int, db: Session):
    key = f"views:{post_id}"
    count = await redis.incr(key)

    if count % 50 == 0:
        # Flush to DB every 50 views
        await redis.set(key, 0)
        db.execute(
            "UPDATE posts SET view_count = view_count + 50 WHERE id = :id",
            {"id": post_id}
        )
        db.commit()
```

### 3. Display

Read from DB for the post page. Redis is write buffer only, not read cache.

## What we're NOT doing

- Deduplication (same user viewing twice counts twice)
- Analytics (just total count)

## Success criteria

Post view counts are displayed and increment on each page load. DB is not overwhelmed by write traffic on viral posts.
