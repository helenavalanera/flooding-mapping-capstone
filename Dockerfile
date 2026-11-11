# Servidor do Flooding Mapping: dashboard, PWA e API em um único processo.
# Dados (tabela de ruas, ocorrências e site gerado) NÃO entram na imagem: ficam em um volume persistente em /dados.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app/src \
    HOST=0.0.0.0 PORT=8080 \
    FM_REDE=/dados/rede_poa.parquet FM_OCORRENCIAS=/dados/ocorrencias.jsonl FM_SITE=/dados/site

WORKDIR /app
COPY requirements-servidor.txt .
RUN pip install --no-cache-dir -r requirements-servidor.txt

COPY config ./config
COPY src ./src
COPY reports/ml/risco_trecho_auditoria.json ./reports/ml/risco_trecho_auditoria.json

# Usuário sem privilégios; /dados precisa ser gravável por ele (o volume é montado por cima).
RUN useradd --system --uid 10001 app && mkdir -p /dados && chown app /dados
USER app

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/saude', timeout=4).status == 200 else 1)"
CMD ["python", "-W", "ignore", "-m", "flooding_mapping.servidor"]
