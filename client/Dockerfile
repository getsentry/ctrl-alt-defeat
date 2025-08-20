# Multi-stage build for Godot web export and hosting
# Stage 1: Build the Godot web export
FROM barichello/godot-ci:4.3 as builder

# Set working directory
WORKDIR /app

# Copy the entire Godot project
COPY . .

# Update the API URL in the export settings (if using environment variable)
ARG API_URL="https://ctrl-alt-defeat-backend.sentry.gg"
ENV API_URL=${API_URL}

# Create export directory
RUN mkdir -p /app/web-build

# Export the project for web (headless)
# Note: export_presets.cfg must exist with a preset named "Web"
RUN godot --headless --export-release "Web" /app/web-build/index.html || \
    godot --headless --export-release "HTML5" /app/web-build/index.html || \
    (echo "Export failed - checking available presets:" && \
     godot --headless --export-list && \
     exit 1)

# Stage 2: Serve with Nginx
FROM nginx:alpine

# Install gettext for envsubst (environment variable substitution)
RUN apk add --no-cache gettext

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the exported web build from builder stage
COPY --from=builder /app/web-build /usr/share/nginx/html

# Add a simple health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost || exit 1

# Expose port 80
EXPOSE 80

# Start nginx
CMD ["nginx", "-g", "daemon off;"]
