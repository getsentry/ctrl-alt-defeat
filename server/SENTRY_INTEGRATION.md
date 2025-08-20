# Sentry Integration Documentation

## Overview
The Autobattler server is integrated with Sentry for error tracking, performance monitoring, and debugging in production.

## Features

### Error Tracking
- Automatic capture of unhandled exceptions
- HTTP errors (500+) are logged to Sentry
- Stack traces with source context
- User context for better debugging

### Performance Monitoring
- Transaction tracking for all API endpoints
- Custom spans for critical operations (battle simulation)
- Database query performance tracking
- 10% sample rate by default (configurable)

### Data Privacy
- Sensitive data is filtered before sending to Sentry
- Authentication headers are redacted
- Passwords and tokens are removed
- JWT tokens in error messages are filtered
- PII (Personally Identifiable Information) is not sent

## Configuration

### Environment Variables
```bash
# Required
SENTRY_DSN=https://your-dsn@sentry.io/project-id

# Optional (with defaults)
ENVIRONMENT=production              # or development, staging
RELEASE=autobattler-server@1.0.0   # version tracking
SENTRY_TRACES_SAMPLE_RATE=0.1      # 10% of transactions
SENTRY_PROFILES_SAMPLE_RATE=0.1    # 10% profiling
```

### Disabling Sentry
- Sentry is automatically disabled in TEST_MODE
- Set `SENTRY_DSN=""` to disable in production

## Usage

### Manual Error Capture
```python
import sentry_sdk

try:
    risky_operation()
except Exception as e:
    sentry_sdk.capture_exception(e)
```

### Adding Context
```python
# Set user context
sentry_sdk.set_user({
    "id": user_id,
    "username": username
})

# Add custom tags
sentry_sdk.set_tag("game.round", round_number)

# Add breadcrumbs
sentry_sdk.add_breadcrumb(
    message="Player purchased item",
    category="game",
    level="info",
    data={"item_id": item_id, "cost": cost}
)
```

### Performance Monitoring
```python
# Monitor a specific operation
with sentry_sdk.start_span(op="database.query") as span:
    span.set_data("query_type", "select")
    result = await db.execute(query)
```

## Monitored Operations

### Automatic Monitoring
- All HTTP endpoints
- Database queries (via SQLAlchemy integration)
- FastAPI middleware operations

### Custom Monitoring
- Battle simulations (`/battle/simulate`)
- Session creation (`/session/start`)
- Health checks (`/health`)

## Filtering Sensitive Data

The following data is automatically filtered:
- Authorization headers
- Cookie headers
- Password fields in requests
- JWT tokens in error messages
- API keys and secrets

## Health Check Endpoint

The `/health` endpoint provides system status including:
- Overall health status
- Database connectivity
- Environment information
- Version details

## Debugging

### View in Sentry Dashboard
1. Go to https://sentry.io
2. Select the Autobattler project
3. View issues, performance, and user feedback

### Local Testing
```bash
# Test with Sentry enabled
SENTRY_DSN=your-dsn python main.py

# Test without Sentry
TEST_MODE=true python main.py
```

## Best Practices

1. **Use transactions for complex operations**
   ```python
   with sentry_sdk.start_transaction(op="game.round", name="process_round"):
       # Your code here
   ```

2. **Add meaningful context**
   ```python
   sentry_sdk.set_context("game_state", {
       "round": round_number,
       "player_count": player_count
   })
   ```

3. **Use appropriate log levels**
   ```python
   sentry_sdk.capture_message("Important event", level="warning")
   ```

4. **Clean up PII before logging**
   ```python
   # Don't log email addresses, passwords, etc.
   safe_data = {k: v for k, v in data.items() if k not in ['email', 'password']}
   ```

## Troubleshooting

### Sentry not receiving events
1. Check SENTRY_DSN is set correctly
2. Verify TEST_MODE is false
3. Check network connectivity
4. Review Sentry rate limits

### Performance impact
- Reduce sample rates if needed:
  ```bash
  SENTRY_TRACES_SAMPLE_RATE=0.01  # 1% sampling
  ```

### Too many events
- Adjust error filtering in `filter_sensitive_data()`
- Use `ignore_errors` in Sentry config
- Implement rate limiting

## Security Considerations

1. Never log sensitive user data
2. Always use HTTPS for Sentry DSN
3. Rotate DSN if compromised
4. Review Sentry data retention policies
5. Ensure compliance with privacy regulations (GDPR, CCPA)
