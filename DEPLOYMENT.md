# Northflank Deployment Guide

## Prerequisites
- Northflank account with a project created
- Git repository connected to Northflank

## Deployment Steps

### 1. Push Code to Repository
```bash
git add .
git commit -m "Add Northflank deployment configuration"
git push origin main
```

### 2. Create PostgreSQL Database Addon (Optional - for when ready)
1. In Northflank dashboard: **Create new → Addon**
2. Select **PostgreSQL**
3. Choose version: **16** (latest stable)
4. Select plan based on your needs
5. Northflank will provide the `DATABASE_URL` automatically

### 3. Create Combined Service
1. In Northflank dashboard: **Create new → Service**
2. Select **Combined service**
3. Connect your Git repository and branch
4. Build settings:
   - **Build type**: Dockerfile
   - **Dockerfile path**: `server/Dockerfile` (or `server/Dockerfile.production` for optimized build)
   - **Build context**: `server`

### 4. Configure Environment Variables
Add these in the service's Environment Variables section:
- `TEST_MODE`: `false` (for production)
- `DATABASE_URL`: (auto-populated if using Northflank PostgreSQL addon)
- Optional:
  - `DB_HOST`: Custom database host if not using addon
  - `DB_NAME`: Custom database name if not using addon

### 5. Networking Configuration
- Port **8000** should be auto-detected from Dockerfile
- You can set a custom subdomain for your service

### 6. Deploy
Click **Create service** - Northflank will:
1. Build your Docker image
2. Deploy the container
3. Set up health checks
4. Enable CI/CD (auto-deploy on git push)

## Local Testing

### Test with Docker Compose
```bash
# Start services
docker-compose up --build

# Stop services
docker-compose down

# Clean up (including volumes)
docker-compose down -v
```

### Test production Dockerfile
```bash
cd server
docker build -f Dockerfile.production -t autobattler-prod .
docker run -p 8000:8000 -e TEST_MODE=false autobattler-prod
```

## Health Checks
The service includes health checks at:
- `/docs` - FastAPI documentation (used by health check)
- Custom endpoints can be added in `main.py`

## Monitoring
- Check logs in Northflank dashboard
- Monitor health status
- Set up alerts for failures

## Troubleshooting

### Database Connection Issues
1. Verify `DATABASE_URL` is set correctly
2. Check PostgreSQL addon is running
3. Review connection logs

### Build Failures
1. Check Dockerfile syntax
2. Verify all required files are not in `.dockerignore`
3. Check build logs in Northflank

### Runtime Errors
1. Check environment variables are set
2. Review application logs
3. Verify port 8000 is exposed

## Production Recommendations
1. Use `Dockerfile.production` for smaller image size
2. Set up staging environment first
3. Configure auto-scaling based on load
4. Set up database backups
5. Monitor application metrics
