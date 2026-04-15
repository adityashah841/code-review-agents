FROM python:3.11-slim

WORKDIR /app

RUN pip install uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen

COPY . .

RUN mkdir -p workspace reports

ENTRYPOINT ["uv", "run", "python", "cli.py"]
CMD ["--help"]
