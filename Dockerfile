# Build stage
FROM node:18-alpine AS builder

WORKDIR /app

# Install build dependencies including Python
RUN apk add --no-cache python3 make g++ sqlite rsync

# Copy package files
COPY package.json package-lock.json* ./

# Install all dependencies (including dev for build)
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Test stage
FROM node:18-alpine AS tester

WORKDIR /app

# Install test dependencies
RUN apk add --no-cache python3 make g++ sqlite

# Copy package files
COPY package.json package-lock.json* ./

# Install all dependencies
RUN npm ci

# Copy source code and built assets
COPY . .
COPY --from=builder /app/dist ./dist

# Run tests
RUN npm test

# Production stage
FROM node:18-alpine

WORKDIR /app

# Install runtime dependencies and dumb-init
RUN apk add --no-cache python3 sqlite dumb-init

# Copy package files
COPY package.json package-lock.json* ./

# Install production dependencies only
RUN npm ci --omit=dev

# Copy built application from builder
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/bin ./bin
COPY --from=builder /app/node_modules ./node_modules

# Create directory for SQLite database and logs
RUN mkdir -p /app/data/.minions /app/logs && \
    chmod 755 /app/data /app/logs

# Set environment variables
ENV NODE_ENV=production
ENV HOME=/app/data

# Expose port
EXPOSE 6969

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
  CMD node -e "require('http').get('http://localhost:6969', (r) => {if (r.statusCode !== 200) throw new Error(r.statusCode)})" || exit 1

# Use dumb-init to handle signals properly
ENTRYPOINT ["/usr/sbin/dumb-init", "--"]

# Start the application
CMD ["npm", "start"]
