FROM nginx:alpine

ARG BUILD_VERSION=dev

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY index.html groups.html bracket.html scorers.html sitemap.xml styles.css /usr/share/nginx/html/
COPY manifest.json sw.js favicon.ico /usr/share/nginx/html/
COPY icons/ /usr/share/nginx/html/icons/
COPY data.json scorers.json /usr/share/nginx/html/

RUN find /usr/share/nginx/html -name "*.html" -exec sed -i "s/vBUILD/v${BUILD_VERSION}/g" {} +

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ || exit 1
