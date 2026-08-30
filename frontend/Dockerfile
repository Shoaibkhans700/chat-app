# syntax=docker/dockerfile:1

# ---------- Stage 1: build the static React app ----------
FROM node:20-alpine AS build

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
RUN npm run build   # outputs to /app/dist

# ---------- Stage 2: serve the build with Nginx ----------
FROM nginx:1.27-alpine

# Template is rendered into /etc/nginx/conf.d/default.conf at container
# start by the base image's built-in docker-entrypoint.d scripts.
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Default points at the docker-compose service name; Kubernetes overrides
# this via the frontend Deployment's env (see k8s/frontend-deployment.yaml).
ENV BACKEND_URL=http://backend:8000

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget -qO- http://localhost:8080/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
