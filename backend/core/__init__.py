"""Core package — application factory, logging, errors, lifespan, DI.

This is the composition root: it wires config, infrastructure, and the API
together. Domain code never imports from `core` except for exceptions.
"""
