"""
Routes Package

This package contains Flask blueprints for organizing application routes.
Each blueprint handles a specific domain of functionality.

Available Blueprints:
- settings_bp: Settings, License, and Configuration management
- (more blueprints to be added)
"""

from .settings import settings_api_bp as settings_bp  # Legacy name for backward compat

__all__ = ['settings_bp']
