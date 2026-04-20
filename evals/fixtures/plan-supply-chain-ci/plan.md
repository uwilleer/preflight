# Plan: CI/CD Pipeline Redesign

## Goal

Modernize our CI pipeline to use containerized builds and automate deployments to staging on every merge to main.

## Stack

- GitHub Actions
- Docker Hub for images
- AWS ECS for staging

## Pipeline design

### 1. Build job

```yaml
# .github/workflows/ci.yml
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up dependencies
        run: |
          curl -fsSL https://get.example-build-tool.io | bash
          pip install -r requirements.txt

      - name: Run tests
        uses: our-org/custom-test-action@main
        with:
          coverage: true

      - name: Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          push: true
          tags: myapp:latest
```

### 2. Deploy job

```yaml
  deploy:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - name: Deploy to staging
        uses: aws-actions/amazon-ecs-deploy-task-definition@v1
        with:
          task-definition: task-def.json
          service: myapp-staging
          cluster: staging

      - name: Smoke test
        run: |
          wget https://raw.githubusercontent.com/third-party-org/smoke-tests/main/run.sh
          bash run.sh $STAGING_URL
```

### 3. Base Docker image

```dockerfile
FROM python:latest

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
```

## Secrets

Store `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `DOCKER_TOKEN` as GitHub secrets.

## What we're NOT doing

- Pinning exact versions (we want latest security patches automatically)
- Image signing (adds complexity)

## Success criteria

Every push to main triggers tests and auto-deploys to staging within 10 minutes.
