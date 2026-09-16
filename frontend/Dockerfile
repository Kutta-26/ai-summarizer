# ============================================================
# Stage 1: Build static React / Vite frontend assets
# ============================================================
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency manifests first for build caching
COPY package.json package-lock.json ./
RUN npm ci

# Accept backend API URL at build time (preserving existing VITE_API_BASE_URL mechanism)
ARG VITE_API_BASE_URL="http://localhost:8000"
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL

# Copy frontend source files
COPY . .

# Build production bundle
RUN npm run build

# ============================================================
# Stage 2: Serve optimized static bundle using Nginx
# ============================================================
FROM nginx:alpine

# Remove default Nginx website
RUN rm -rf /usr/share/nginx/html/*

# Copy built static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration with SPA fallback and security headers
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD wget --quiet --tries=1 --spider http://localhost:80/ || exit 1

# Run Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
