FROM python:3.12-slim

ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    TORCH_HOME=/opt/models/torch \
    DATA_DIR=/data

WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

# Нейросеть внимания DeepGaze IIE (CPU): скачивается ~1,5 ГБ, в работе ~1,3 ГБ памяти. Лёгкий образ без неё: --build-arg NEURAL=0.
# git нужен только здесь: DeepGaze и CLIP ставятся из репозиториев по зафиксированным коммитам.
# Веса скачиваются при сборке — контейнер потом работает без интернета.
ARG NEURAL=1
COPY requirements-neural.txt scripts/fetch_weights.py ./
RUN if [ "$NEURAL" = "1" ]; then \
      apt-get update && apt-get install -y --no-install-recommends git \
   && pip install --index-url https://download.pytorch.org/whl/cpu torch==2.5.1 torchvision==0.20.1 \
   && pip install -r requirements-neural.txt \
   && apt-get purge -y git && apt-get autoremove -y && rm -rf /var/lib/apt/lists/* \
   && python fetch_weights.py; \
    fi \
 && rm requirements-neural.txt fetch_weights.py

COPY seed ./seed
COPY app ./app

# Сервис работает от непривилегированного пользователя app (права сбрасывает entrypoint);
# /data — docker-том с настройками, примерами и паролем админки
COPY scripts/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN useradd --system --create-home app \
 && mkdir -p /data && chown app:app /data \
 && chmod +x /usr/local/bin/entrypoint.sh
VOLUME /data

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=90s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')"
ENTRYPOINT ["entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
