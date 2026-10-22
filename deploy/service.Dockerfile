# Образ одного сервиса FishStock. Контекст сборки — корень репозитория.
#   docker build -f deploy/service.Dockerfile --build-arg SERVICE=users .
FROM python:3.12-slim

ARG SERVICE
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FISH_DATA_DIR=/data \
    PIP_NO_CACHE_DIR=1

WORKDIR /srv
# компилятор C++ нужен PyTensor (PyMC) для быстрой байесовской модели — только сервисам алгоритмов
RUN if [ "$SERVICE" = "algo_admin" ] || [ "$SERVICE" = "algo_model" ]; then \
      apt-get update && apt-get install -y --no-install-recommends g++ && rm -rf /var/lib/apt/lists/*; \
    fi
COPY libs/fishcommon /srv/libs/fishcommon
RUN pip install /srv/libs/fishcommon
COPY services/${SERVICE}/requirements.txt /srv/requirements.txt
RUN pip install -r /srv/requirements.txt
# алгоритмы (эталонные пакеты) нужны сервисам моделирования и администрирования алгоритмов
COPY algorithms /srv/algorithms
COPY services/${SERVICE}/app /srv/app

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
