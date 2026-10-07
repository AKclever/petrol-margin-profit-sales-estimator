FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml ./
COPY musa_nowcast ./musa_nowcast
RUN pip install --no-cache-dir '.[cloud]'
COPY data/weights.csv data/actuals.csv ./data/
ENTRYPOINT ["musa-daily-capture"]
