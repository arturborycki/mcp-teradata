from __future__ import annotations

from typing import Optional, TYPE_CHECKING
import teradatasql
from urllib.parse import urlparse
import logging
import re

if TYPE_CHECKING:
    from teradata_mcp.settings import Settings

logger = logging.getLogger(__name__)

def obfuscate_password(text: str | None) -> str | None:
    """
    Obfuscate password in any text containing connection information.
    Works on connection URLs, error messages, and other strings.
    """
    if text is None:
        return None

    if not text:
        return text

    # Try first as a proper URL
    try:
        parsed = urlparse(text)
        if parsed.scheme and parsed.netloc and parsed.password:
            netloc = parsed.netloc.replace(parsed.password, "****")
            return parsed._replace(netloc=netloc).geturl()
    except Exception:
        pass

    url_pattern = re.compile(r"(teradata(?:ql)?:\/\/[^:]+:)([^@]+)(@[^\/\s]+)")
    text = re.sub(url_pattern, r"\1****\3", text)

    param_pattern = re.compile(r'(password=)([^\s&;"\']+)', re.IGNORECASE)
    text = re.sub(param_pattern, r"\1****", text)

    dsn_single_quote = re.compile(r"(password\s*=\s*')([^']+)(')", re.IGNORECASE)
    text = re.sub(dsn_single_quote, r"\1****\3", text)

    dsn_double_quote = re.compile(r'(password\s*=\s*")([^"]+)(")', re.IGNORECASE)
    text = re.sub(dsn_double_quote, r"\1****\3", text)

    return text

class TDConn:

    def __init__(self, connection_url: Optional[str] = None, settings: Optional[Settings] = None):
        self.conn = None
        self.connection_url = ""
        if connection_url is None:
            return

        parsed_url = urlparse(connection_url)
        user = parsed_url.username
        password = parsed_url.password
        host = parsed_url.hostname
        database = parsed_url.path.lstrip('/')
        self.connection_url = connection_url

        connect_params = dict(
            host=host,
            user=user,
            password=password,
            database=database,
        )

        # LOGMECH support (LDAP, KRB5, JWT, TDNEGO, etc.)
        if settings and settings.logmech and settings.logmech.upper() != "TD2":
            connect_params["logmech"] = settings.logmech
        if settings and settings.logdata:
            connect_params["logdata"] = settings.logdata
        if settings and settings.encrypt_data:
            connect_params["encryptdata"] = settings.encrypt_data
        if settings and settings.ssl_mode:
            connect_params["sslmode"] = settings.ssl_mode

        try:
            self.conn = teradatasql.connect(**connect_params)
        except Exception as e:
            logger.error(f"Error connecting to database: {obfuscate_password(str(e))}")
            self.conn = None

    def cursor(self):
        if self.conn is None:
            raise Exception("No connection to database")
        return self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()