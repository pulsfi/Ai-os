"""Application services (use cases).

Services orchestrate modules and infrastructure to fulfill one business
capability each. They are constructed by DI providers (`core.dependencies`)
and receive everything they need — they never reach out for globals.
"""
