# Deployment Playbook - LETATEC

## 1. Local Run
*   **Backend**:
    ```bash
    cd rag-backend
    uv run python main.py
    ```
*   **Frontend**:
    ```bash
    cd frontend
    npm run dev
    ```

## 2. Environment Configurations
| Parameter | Default | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017/leta` | Primary database URI |
| `REDIS_URL` | `redis://localhost:6379/0` | Cache tier URL |
| `SECRET_KEY` | `dev-only-insecure-key` | JWT signature seed |

## 3. Docker build
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "main.py"]
```
