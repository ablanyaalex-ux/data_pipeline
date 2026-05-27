#!/bin/bash
set -e

/opt/mssql/bin/sqlservr &
SERVER_PID=$!

echo "Waiting for SQL Server to accept connections..."
for i in {1..120}; do
  /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -Q "SELECT 1" >/dev/null 2>&1 && break
  sleep 1
done

echo "Creating database [ConnectCallData_26295] if missing..."
/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -d master -Q \
"IF DB_ID(N'ConnectCallData_26295') IS NULL CREATE DATABASE [ConnectCallData_26295];"

echo "Waiting for [ConnectCallData_26295] to be ONLINE..."
/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -d master -Q \
"DECLARE @i int=0;
 WHILE (@i < 120 AND (SELECT state_desc FROM sys.databases WHERE name = N'ConnectCallData_26295') <> 'ONLINE')
 BEGIN
   WAITFOR DELAY '00:00:01';
   SET @i += 1;
 END;
 SELECT name, state_desc FROM sys.databases WHERE name = N'ConnectCallData_26295';"

echo "Waiting additional time for database to be fully accessible..."
sleep 2

echo "Running schema script..."
/opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -d master -i "/usr/src/app/sql/01_schema.sql"

echo "Waiting for schema initialization to complete..."
sleep 2

echo "Running remaining scripts..."
for file in /usr/src/app/sql/02_*.sql; do
  echo "Running $file"
  /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P "$SA_PASSWORD" -C -d master -i "$file"
done

echo "Initialization complete. SQL Server will continue running."
wait $SERVER_PID
