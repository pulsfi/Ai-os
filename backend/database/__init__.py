"""Database package — PostgreSQL (SQLAlchemy async) and Redis providers.

Infrastructure only: no business logic, no queries beyond connectivity.
Domain code receives sessions/clients via dependency injection
(`core.dependencies`) and never imports engines directly.
"""
