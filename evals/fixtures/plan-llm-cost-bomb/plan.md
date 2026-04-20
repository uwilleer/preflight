# Plan: AI-Powered Search with Explanations

## Goal

Enhance product search with AI-generated explanations. When a user searches, show top 10 results plus an AI-generated paragraph explaining why these results match the query.

## Stack

- Python + FastAPI
- PostgreSQL + pgvector for semantic search
- OpenAI GPT-4 for explanations
- No caching initially (explanations are personalized)

## Implementation

### 1. Search endpoint

```python
@app.get("/search")
async def search(q: str, user_id: int, db: Session = Depends(get_db)):
    # Semantic search
    embedding = await openai.embeddings.create(
        model="text-embedding-ada-002",
        input=q
    )
    results = db.execute(
        "SELECT * FROM products ORDER BY embedding <-> :vec LIMIT 10",
        {"vec": embedding.data[0].embedding}
    ).fetchall()

    # Generate explanation for each result
    explanations = []
    for result in results:
        explanation = await openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a helpful shopping assistant."},
                {"role": "user", "content": f"Why does '{result.name}' match the search '{q}'? User context: {get_user_history(user_id)}"}
            ]
        )
        explanations.append(explanation.choices[0].message.content)

    return {"results": results, "explanations": explanations}
```

### 2. User history context

```python
def get_user_history(user_id: int) -> str:
    history = db.query(UserEvent).filter_by(user_id=user_id).all()
    return "\n".join([f"{e.action}: {e.product_name}" for e in history])
```

### 3. Personalization

Pass the full user purchase/view history to GPT-4 for context so explanations are personalized.

## Scaling plan

Deploy on current infra. If search gets slow, add more API workers.

## What we're NOT doing

- Caching (explanations are personalized per user)
- Rate limiting (trusted users)
- Token limits on GPT-4 calls (we want complete explanations)

## Success criteria

Every search returns 10 results with AI explanations. Users find explanations helpful.
