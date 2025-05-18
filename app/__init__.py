"""
Main application package.
"""

__version__ = '0.1.0'

# Import commonly used components
from .models import *
from .services import *
from .utils import *
from .models.models import Show, Episode
from .services.database import DatabaseService

__all__ = [
    'models',
    'services',
    'utils',
    'Show',
    'Episode',
    'DatabaseService',
]
