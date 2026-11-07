# Bauen (im Repo-Hauptordner):  docker build -f deploy/Dockerfile -t leistungsabgleich:0.9.0b1 .
# Starten: docker run -v /srv/abgleich:/daten -p 127.0.0.1:8080:8080 leistungsabgleich:0.9.0b1
#   /srv/abgleich muss behoerden.json enthalten; dort liegen auch Datenbank und Sicherungen.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN useradd --system --uid 10001 --home /daten abgleich && mkdir /daten && chown abgleich /daten
WORKDIR /app
COPY leistungsabgleich ./leistungsabgleich
USER abgleich
VOLUME /daten
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/status', timeout=4)"
ENTRYPOINT ["python", "-m", "leistungsabgleich"]
CMD ["serve", "--host", "0.0.0.0", "--db", "/daten/abgleich.db", "--konfig", "/daten/behoerden.json"]
