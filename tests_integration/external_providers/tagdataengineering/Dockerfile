FROM minio/minio:latest

RUN curl -fL https://dl.min.io/client/mc/release/linux-amd64/mc -o /usr/local/bin/mc && chmod +x /usr/local/bin/mc

COPY /ingest-data/ /staging/ingest-data/
COPY /cascadereportuploads/ /staging/cascadereportuploads/
COPY setup_bucket.sh /setup_bucket.sh

RUN chmod +x /setup_bucket.sh

EXPOSE 9000 9001

ENTRYPOINT ["/setup_bucket.sh"]
