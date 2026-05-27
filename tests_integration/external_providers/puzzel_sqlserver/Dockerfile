FROM mcr.microsoft.com/mssql/server:2019-latest

# Switch to root
USER root

# Create directory for SQL scripts
RUN mkdir -p /usr/src/app/sql

# Copy schema + seed scripts
COPY data/*.sql /usr/src/app/sql/

# Copy PowerShell init script
COPY init-db.sh /usr/src/app/init-db.sh
RUN chmod +x /usr/src/app/init-db.sh

# Expose SQL Server port
EXPOSE 1433

# Start SQL Server, run init script, keep container alive
CMD /bin/bash /usr/src/app/init-db.sh
