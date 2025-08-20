"""
Sentry configuration and initialization
"""

import os

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration


def init_sentry(test_mode: bool = False) -> bool:
    """
    Initialize Sentry for error tracking and performance monitoring

    Returns:
        bool: True if Sentry was initialized, False otherwise
    """
    if test_mode:
        print("Sentry disabled in test mode")
        return False

    dsn = os.environ.get(
        "SENTRY_DSN",
        "https://6a4ff9b3cfcb25b639b4ba43d1990e9f@o1.ingest.us.sentry.io/4509874488410112",
    )

    if not dsn:
        print("Sentry DSN not configured")
        return False

    environment = os.environ.get("ENVIRONMENT", "production")
    release = os.environ.get("RELEASE", "autobattler-server@1.0.0")

    # Sample rates for performance monitoring
    traces_sample_rate = float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1"))
    profiles_sample_rate = float(os.environ.get("SENTRY_PROFILES_SAMPLE_RATE", "0.1"))

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FastApiIntegration(
                transaction_style="endpoint",
                failed_request_status_codes=[
                    400,
                    401,
                    403,
                    404,
                    405,
                    500,
                    501,
                    502,
                    503,
                    504,
                ],
            ),
            StarletteIntegration(transaction_style="endpoint"),
            SqlalchemyIntegration(),
        ],
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        environment=environment,
        release=release,
        send_default_pii=False,  # Don't send personally identifiable information
        attach_stacktrace=True,
        before_send=filter_sensitive_data,
        # Additional options
        max_breadcrumbs=50,
        debug=False,
        shutdown_timeout=2,
        # Ignore certain errors
        ignore_errors=[
            KeyboardInterrupt,
            SystemExit,
        ],
    )

    print(f"Sentry initialized for {environment} environment")
    print(f"- Traces sample rate: {traces_sample_rate * 100}%")
    print(f"- Profiles sample rate: {profiles_sample_rate * 100}%")
    return True


def filter_sensitive_data(event, hint=None):
    """
    Filter out sensitive data from Sentry events

    Args:
        event: The Sentry event dictionary
        hint: Optional hint dictionary with additional context

    Returns:
        Modified event dictionary or None to drop the event
    """
    # Remove authentication headers
    if "request" in event and "headers" in event["request"]:
        headers = event["request"]["headers"]
        sensitive_headers = ["authorization", "cookie", "x-api-key", "api-key"]
        for header in sensitive_headers:
            if header in headers:
                headers[header] = "[FILTERED]"

    # Remove passwords and tokens from request data
    if "request" in event and "data" in event["request"]:
        data = event["request"]["data"]
        if isinstance(data, dict):
            sensitive_fields = [
                "password",
                "password_hash",
                "token",
                "secret",
                "api_key",
                "access_token",
                "refresh_token",
            ]
            for field in sensitive_fields:
                if field in data:
                    data[field] = "[FILTERED]"

    # Remove JWT tokens from error messages
    if "exception" in event and "values" in event["exception"]:
        for exception in event["exception"]["values"]:
            if "value" in exception:
                value_lower = exception["value"].lower()
                if any(term in value_lower for term in ["jwt", "token", "bearer"]):
                    # Redact potential tokens in the error message
                    import re

                    exception["value"] = re.sub(
                        r"[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+",
                        "[JWT_TOKEN_FILTERED]",
                        exception["value"],
                    )

    # Remove sensitive user data
    if "user" in event and isinstance(event["user"], dict):
        if "email" in event["user"]:
            # Keep domain but hide local part
            email = event["user"]["email"]
            if "@" in email:
                local, domain = email.split("@", 1)
                event["user"]["email"] = f"***@{domain}"

    return event


def capture_message(message: str, level: str = "info", **kwargs):
    """
    Wrapper for capturing messages to Sentry

    Args:
        message: The message to capture
        level: Log level (debug, info, warning, error, fatal)
        **kwargs: Additional context to attach
    """
    if os.environ.get("TEST_MODE", "false").lower() == "true":
        return

    with sentry_sdk.push_scope() as scope:
        for key, value in kwargs.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_message(message, level=level)


def capture_exception(exception: Exception, **kwargs):
    """
    Wrapper for capturing exceptions to Sentry

    Args:
        exception: The exception to capture
        **kwargs: Additional context to attach
    """
    if os.environ.get("TEST_MODE", "false").lower() == "true":
        return

    with sentry_sdk.push_scope() as scope:
        for key, value in kwargs.items():
            scope.set_extra(key, value)
        sentry_sdk.capture_exception(exception)


class SentryContextManager:
    """
    Context manager for adding Sentry context to a block of code
    """

    def __init__(self, transaction_name: str, op: str = "task", **tags):
        self.transaction_name = transaction_name
        self.op = op
        self.tags = tags
        self.transaction = None

    def __enter__(self):
        if os.environ.get("TEST_MODE", "false").lower() != "true":
            self.transaction = sentry_sdk.start_transaction(
                op=self.op, name=self.transaction_name
            )
            for key, value in self.tags.items():
                self.transaction.set_tag(key, value)
        return self.transaction

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.transaction:
            if exc_val:
                self.transaction.set_status("internal_error")
                sentry_sdk.capture_exception(exc_val)
            else:
                self.transaction.set_status("ok")
            self.transaction.finish()
