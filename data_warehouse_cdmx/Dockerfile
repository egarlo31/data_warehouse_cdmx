FROM postgres:17

RUN mkdir -p /docker-entrypoint-initdb.d/data

COPY data/*.csv /docker-entrypoint-initdb.d/data/
COPY ddl/*.sql /docker-entrypoint-initdb.d/
COPY etl/*.sql /docker-entrypoint-initdb.d/
COPY scripts/consulta.sql /docker-entrypoint-initdb.d/consulta.sql