# Multi-stage build for Godot web export and hosting
# Stage 1: Build the Godot web export
# The editor has to be the project's own version: an older one exports a 4.4
# project as far as an error message and no further.
FROM barichello/godot-ci:4.4.1 as builder

# Set working directory
WORKDIR /app

# Copy the entire Godot project
COPY . .

# Update the API URL in the export settings (if using environment variable)
ARG API_URL="https://ctrl-alt-defeat-backend.sentry.gg"
ENV API_URL=${API_URL}

# Point the client at the deployed server. A page cannot be handed an
# environment variable the way a desktop build can, so the URL is written into
# the source before the export.
#
# Found by what the line says rather than by which file says it. This named a
# file, that file was renamed, and the build has been failing ever since --
# quietly, because a failed build leaves the last good image being served and
# nothing on the site says how old it is. Whatever holds the line is patched,
# and a substitution that does not take stops the build here.
RUN set -eux; \
    holds="$(grep -rl 'var BASE_URL = "http://localhost:8000"' /app/scripts)"; \
    test -n "$holds"; \
    sed -i "s|var BASE_URL = \"http://localhost:8000\"|var BASE_URL = \"${API_URL}\"|g" $holds; \
    grep -q "var BASE_URL = \"${API_URL}\"" $holds; \
    echo "Pointed $holds at ${API_URL}"

# Create export directory
RUN mkdir -p /app/web-build

# Export the project for web (headless)
# Note: export_presets.cfg must exist with a preset named "Web"
RUN godot --headless --export-release "Web" /app/web-build/index.html || \
    godot --headless --export-release "HTML5" /app/web-build/index.html || \
    (echo "Export failed - checking available presets:" && \
     godot --headless --export-list && \
     exit 1)

# Verify export created files
RUN echo "Files created by export:" && \
    ls -la /app/web-build/

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
