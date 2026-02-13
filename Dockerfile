FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY config ./config
COPY contracts ./contracts

RUN pip install --no-cache-dir .

EXPOSE 8000

CMD ["uvicorn", "sentinel_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
