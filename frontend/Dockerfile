# syntax=docker/dockerfile:1
# Build the static app with Node, then serve it from an unprivileged nginx.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts
COPY . .
# Public, build-time configuration only. Never pass secrets as VITE_* variables.
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build
# The Content-Security-Policy must allow exactly the API origin this build calls (connect-src).
# Only a plain http(s) origin is accepted, so nothing else can reach the nginx config.
RUN origin="$(printf '%s' "$VITE_API_BASE_URL" | sed -E 's#^(https?://[^/]+).*#\1#')" \
 && printf '%s' "$origin" | grep -Eq '^https?://[A-Za-z0-9.-]+(:[0-9]+)?$' \
 || { echo "VITE_API_BASE_URL must be an http(s) URL, got an unusable origin" >&2; exit 1; } \
 && sed "s#__API_ORIGIN__#$origin#" security-headers.conf > /app/security-headers.built.conf

FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/security-headers.built.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080
