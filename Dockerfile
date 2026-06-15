FROM nginx:alpine

ARG BUILD_VERSION=dev
ARG BUILD_TS=dev

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY index.html groups.html bracket.html sitemap.xml styles.css /usr/share/nginx/html/
COPY manifest.json sw.js favicon.ico /usr/share/nginx/html/
COPY icons/ /usr/share/nginx/html/icons/
COPY data.json /usr/share/nginx/html/

RUN sed -i "s/vBUILD/v${BUILD_VERSION}/" /usr/share/nginx/html/index.html \
 && sed -i "s/wc2026-BUILD_TS/wc2026-${BUILD_TS}/" /usr/share/nginx/html/sw.js

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ || exit 1
