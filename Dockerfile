FROM python:3.12-slim
WORKDIR /app
COPY requirements-linux.lock .
RUN pip install --no-cache-dir -r requirements-linux.lock
COPY backend ./backend
COPY ml ./ml
COPY scripts ./scripts
COPY contracts ./contracts
COPY docs ./docs
COPY data ./data
CMD ["uvicorn","backend.app:app","--host","0.0.0.0","--port","8000","--no-access-log"]
