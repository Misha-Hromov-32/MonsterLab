FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build
# заранее сжатые копии для gzip_static: nginx не тратит процессор на сжатие при каждом запросе
RUN find dist -type f \( -name '*.js' -o -name '*.css' -o -name '*.svg' -o -name '*.html' \) \
    -exec sh -c 'gzip -9 -c "$1" > "$1.gz"' _ {} \;

FROM nginx:alpine
# шаблон превращается в /etc/nginx/conf.d/default.conf при старте (envsubst в образе nginx)
ENV REAL_IP_FROM=127.0.0.1
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
