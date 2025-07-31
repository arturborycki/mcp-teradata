from typing import Optional
import teradatasql
from urllib.parse import urlparse
import argparse
import asyncio
import logging
import os
import signal
import re
import requests

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.DEBUG,  # or logging.INFO
    format="%(asctime)s %(levelname)s %(name)s %(message)s"
)

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

## Teradata Connection Class with URL Parsing and Obfuscation
class TDConn:
    conn = None
    connection_url = str
    keycloak_url = Optional[str]
    keycloak_client_id = Optional[str]

    def __init__(self, connection_url: Optional[str] = None, keycloak_url: Optional[str] = None, keycloak_client_id: Optional[str] = None):
        """
        Initializes a connection to a Teradata database, optionally using Keycloak for JWT-based authentication.
        Args:
            connection_url (Optional[str]): The connection URL in the format expected by Teradata, including username, password, host, and database.
            keycloak_url (Optional[str]): The URL to the Keycloak server for obtaining JWT tokens. If not provided, standard user/password authentication is used.
            keycloak_client_id (Optional[str]): The client ID to use when authenticating with Keycloak.
        Raises:
            ValueError: If Keycloak authentication is requested but no JWT token is received.
            Exception: If any error occurs during the connection process, it is logged and the connection is set to None.
        Notes:
            - If `connection_url` is None, no connection is established.
            - If `keycloak_url` is provided, attempts to authenticate using Keycloak and connect to Teradata with a JWT token.
            - If `keycloak_url` is not provided, connects to Teradata using the provided user credentials.
            - Connection errors are logged and do not raise exceptions directly.
        """
        if connection_url is None:
            self.conn = None
        else:
            parsed_url = urlparse(connection_url)
            user = parsed_url.username
            password = parsed_url.password
            host = parsed_url.hostname
            database = parsed_url.path.lstrip('/') 
            self.connection_url = connection_url
            logger.debug(f"Parsed connection URL: {self.connection_url}")
            logger.debug(f"Connecting to Teradata at {host} with database {database}")
            logger.debug(f"Using Keycloak URL: {keycloak_url} and Client ID: {keycloak_client_id}" if keycloak_url and keycloak_client_id else "No Keycloak authentication configured")
            try:
                if keycloak_url and keycloak_client_id:
                    # Request JWT Token from Keycloak
                    # Get token endpoint from Keycloak using client_id
                    token_info = requests.get(keycloak_url, verify=False)
                    token_url = token_info.json().get("token_endpoint")
                    logger.info(f"Keycloak token endpoint: {token_url}")

                    response = requests.post(
                        token_url,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        data={
                            "grant_type": "password",
                            "client_id": keycloak_client_id,
                            "username": user,
                            "password": password
                        },
                        verify=False
                    )
                    response.raise_for_status()
                    logger.debug(f"Keycloak response: {response.json()}")
                    JWT_TOKEN = response.json().get("access_token")
                    if not JWT_TOKEN:
                        logger.error("No JWT token received from Keycloak")
                        raise ValueError("No JWT token received from Keycloak")
                    logger.info("Successfully obtained JWT token from Keycloak")

                    # JWT Token based connection
                    self.conn = teradatasql.connect(
                        host=host,
                        logmech="JWT",
                        logdata=f"token={JWT_TOKEN}"
                    )
                    logger.info("Connected to Teradata using JWT token")

                else:
                    # Regular connection with User Credentials
                    self.conn = teradatasql.connect (
                        host=host,
                        user=user,
                        password=password,
                        database=database,
                    )
                    logger.info("Connected to Teradata using user credentials")

            except Exception as e:
                logger.error(f"Error connecting to database: {e}")
                self.conn = None
    
    def cursor(self):
        if self.conn is None:
            raise Exception("No connection to database")
        return self.conn.cursor()

    def close(self):
        self.conn.close()