# PowerShell script to initialize SQL Server on Windows

# Wait for SQL Server to be ready
$maxAttempts = 120
$attempt = 0
$serverReady = $false

Write-Host "Waiting for SQL Server to accept connections..."
while ($attempt -lt $maxAttempts -and -not $serverReady) {
    try {
        $connectionString = "Server=localhost;User Id=sa;Password=$env:SA_PASSWORD;"
        $sqlConnection = New-Object System.Data.SqlClient.SqlConnection($connectionString)
        $sqlConnection.Open()
        $sqlConnection.Close()
        $serverReady = $true
        Write-Host "SQL Server is ready!"
    }
    catch {
        $attempt++
        Start-Sleep -Seconds 1
        if ($attempt % 10 -eq 0) {
            Write-Host "Still waiting... attempt $attempt/$maxAttempts"
        }
    }
}

if (-not $serverReady) {
    Write-Error "SQL Server failed to start after $maxAttempts seconds"
    exit 1
}

# Create database if missing
Write-Host "Creating database [Static Dimensions] if missing..."
$sqlCmd = @"
IF DB_ID(N'Static Dimensions') IS NULL 
    CREATE DATABASE [Static Dimensions];
GO
"@

Invoke-SqlCmd -ServerInstance "localhost" -Username "sa" -Password "$env:SA_PASSWORD" -Query $sqlCmd -EncryptionOption Optional

# Wait for database to be online
Write-Host "Waiting for [Static Dimensions] to be ONLINE..."
$dbReady = $false
$attempt = 0
while ($attempt -lt 120 -and -not $dbReady) {
    try {
        $stateQuery = "SELECT state_desc FROM sys.databases WHERE name = N'Static Dimensions'"
        $result = Invoke-SqlCmd -ServerInstance "localhost" -Username "sa" -Password "$env:SA_PASSWORD" -Query $stateQuery -EncryptionOption Optional
        if ($result.state_desc -eq "ONLINE") {
            $dbReady = $true
            Write-Host "Database is ONLINE!"
        }
    }
    catch {
        $attempt++
        Start-Sleep -Seconds 1
    }
}

Write-Host "Waiting additional time for database to be fully accessible..."
Start-Sleep -Seconds 2

# Run schema script
Write-Host "Running schema script against [Static Dimensions]..."
$schemaScript = Get-Content "C:\usr\src\app\sql\01_schema.sql" -Raw
Invoke-SqlCmd -ServerInstance "localhost" -Username "sa" -Password "$env:SA_PASSWORD" -Database "Static Dimensions" -Query $schemaScript -EncryptionOption Optional

Write-Host "Waiting for schema initialization to complete..."
Start-Sleep -Seconds 2

# Run remaining scripts
Write-Host "Running seed data script..."
$seedScript = Get-Content "C:\usr\src\app\sql\02_seed_data.sql" -Raw
Invoke-SqlCmd -ServerInstance "localhost" -Username "sa" -Password "$env:SA_PASSWORD" -Database "Static Dimensions" -Query $seedScript -EncryptionOption Optional

Write-Host "Initialization complete. SQL Server will continue running."
