FROM node:18-alpine
RUN apk add --no-cache wget curl
RUN npm install -g json-server@0.17.4
WORKDIR /data
COPY db.json /data/db.json
COPY routes.json /data/routes.json
CMD ["sh", "-c", "json-server --watch /data/db.json --host 0.0.0.0 --port 8000 --routes /data/routes.json --no-cors 2>&1 | grep -v 'HEAD '"]
