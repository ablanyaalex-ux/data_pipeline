FROM mcr.microsoft.com/mssql/server:2019-latest

# Switch to root to copy files
USER root

# Create directory for init scripts
RUN mkdir -p /usr/src/app/sql

# Copy SQL files
COPY data/*.sql /usr/src/app/sql/
COPY init-db.sh /usr/src/app/init-db.sh

# Make script executable
RUN chmod +x /usr/src/app/init-db.sh

# Expose SQL Server port
EXPOSE 1433

# Start SQL Server and run init script
CMD /bin/bash /usr/src/app/init-db.sh
