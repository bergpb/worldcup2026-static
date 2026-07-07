FROM python:3.12-alpine AS builder

WORKDIR /src
COPY . .
RUN python3 scripts/build.py

FROM nginx:alpine

ARG BUILD_VERSION=dev

COPY nginx/prod.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /src/dist/ /usr/share/nginx/html/

RUN find /usr/share/nginx/html -name "*.html" -exec sed -i "s/vBUILD/v${BUILD_VERSION}/g" {} +

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ || exit 1
