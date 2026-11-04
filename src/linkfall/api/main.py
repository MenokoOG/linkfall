"""The uvicorn entry point:  uvicorn linkfall.api.main:app --host 127.0.0.1 --port 8000"""

from linkfall.api.app import create_app
from linkfall.api.config import load_config
from linkfall.api.logs import configure_logging

configure_logging()
app = create_app(load_config())
