"""
Application configuration for MySQL connection.
Keep credentials in one place for easier maintenance.
"""

DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "Sruj@0",
    "database": "event_management",
}

# Flask app secret key (used for flash messages/session)
SECRET_KEY = "event-management-mini-project-secret-key"
