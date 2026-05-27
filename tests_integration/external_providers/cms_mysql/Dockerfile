FROM mysql:8.0

# Copy SQL files into the container
# MySQL will automatically execute these on first startup in alphabetical order
COPY data/*.sql /docker-entrypoint-initdb.d/

# Expose MySQL port
EXPOSE 3306
