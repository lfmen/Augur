import requests as _requests
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import logging

logger = logging.getLogger(__name__)

@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_requests.RequestException),
    before_sleep=lambda retry_state: logger.warning(f"Reintentando conexion (intento {retry_state.attempt_number}/4)...")
)
def get(*args, **kwargs):
    return _requests.get(*args, **kwargs)

@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(_requests.RequestException),
    before_sleep=lambda retry_state: logger.warning(f"Reintentando conexion POST (intento {retry_state.attempt_number}/4)...")
)
def post(*args, **kwargs):
    return _requests.post(*args, **kwargs)

# Re-export exceptions so callers can use requests_retry.HTTPError etc.
RequestException = _requests.RequestException
ConnectionError = _requests.ConnectionError
Timeout = _requests.Timeout
HTTPError = _requests.HTTPError
