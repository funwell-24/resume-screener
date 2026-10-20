"""
UI package. The presentation layer.

Public API:
    from ui.styles import inject_custom_css
    from ui.components import (...)
"""

from .styles import inject_custom_css

__all__ = ["inject_custom_css"]