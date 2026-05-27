#!/bin/bash
set -e

minio server /data --console-address ":9001" &
MINIO_PID=$!

wait_for_minio() {
    echo "Waiting for MinIO to be ready..."
    for i in {1..30}; do
        if curl -f http://localhost:9000/minio/health/live >/dev/null 2>&1; then
            echo "MinIO is ready!"
            return 0
        fi
        echo "MinIO not ready yet, waiting... ($i/30)"
        sleep 2
    done
    echo "MinIO failed to start properly"
    return 1
}

if ! wait_for_minio; then
    echo "Error: MinIO failed to start"
    exit 1
fi

mc alias set local http://localhost:9000 minioadmin minioadmin

for bucket_dir in /staging/*/; do
    bucket=$(basename "$bucket_dir")
    mc mb "local/$bucket" --ignore-existing
    mc anonymous set public "local/$bucket"
    mc mirror "$bucket_dir" "local/$bucket/"
done

echo "Setup completed successfully!"
touch /tmp/setup_complete

wait $MINIO_PID
