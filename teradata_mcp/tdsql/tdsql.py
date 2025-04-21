from typing import Optional
import teradatasql
from urllib.parse import urlparse
import argparse
import asyncio
import logging
import os
import signal
import re

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
            return urlparse(parsed._replace(netloc=netloc))
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
    conn = None
    connection_url = str

    def __init__(self, connection_url: Optional[str] = None):
        if connection_url is None:
            self.conn = None
        else:
            parsed_url = urlparse(connection_url)
            user = parsed_url.username
            password = parsed_url.password
            host = parsed_url.hostname
            database = parsed_url.path.lstrip('/') 
            self.connection_url = connection_url
            try:
                self.conn = teradatasql.connect (
                    host=host,
                    user=user,
                    password=password,
                    database=database,
                )
            
            except Exception as e:
                logger.error(f"Error connecting to database: {e}")
                self.conn = None
    
    def cursor(self):
        if self.conn is None:
            raise Exception("No connection to database")
        return self.conn.cursor()

    def close(self):
        self.conn.close()