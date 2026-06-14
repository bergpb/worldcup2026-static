FROM nginx:alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY index.html groups.html bracket.html feedback.html sitemap.xml /usr/share/nginx/html/
COPY manifest.json sw.js /usr/share/nginx/html/
COPY data.json /usr/share/nginx/html/

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD wget -qO- http://127.0.0.1/ || exit 1
