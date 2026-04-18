FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY frm_forge ./frm_forge

RUN pip install --no-cache-dir .

RUN mkdir -p /app/data

EXPOSE 8088

CMD ["python", "-m", "frm_forge.app"]
