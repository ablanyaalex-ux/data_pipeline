FROM postgres:14.15

# Postgres will automatically run any *.sql / *.sh placed here on FIRST container start
COPY data/*.sql /docker-entrypoint-initdb.d/

# Default env vars (override in docker-compose if you want)
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=postgres
ENV POSTGRES_DB=cms_prod

# Expose Postgres port
EXPOSE 5432
