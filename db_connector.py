"""
db_connector Module

Provides a centralized Data Access Layer for the pipeline engine. Establishes one-time
direct database connections, loads system configurations, and handles the retrieval 
of script integrity hashes.
"""
import sys
import logging
from types import TracebackType
from typing import Optional, Type, Dict, Any

import yaml
import pyodbc
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger("pipeline_debug")

class DBDirectService:
    """
    Context manager for single-use database connections.
    """
    def __init__(self, host: str, database: str, driver: str):
        """
        Initializes connection metadata.

        Args:
            host (str): Database server hostname or IP address.
            database (str): Target database name.
            driver (str): Name of the installed ODBC system driver.
        """
        self.conn_string = (
            f"DRIVER={{{driver}}};"
            f"SERVER={host};"
            f"DATABASE={database};"
            f"TRUSTED_CONNECTION=yes;"
        )
        self.connection: Optional[pyodbc.Connection] = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type(pyodbc.OperationalError),
        reraise=True
    )
    def __enter__(self) -> pyodbc.Connection:
        """
        Establishes the connection with exponential backoff retries.

        Returns:
            pyodbc.Connection: An open, verified database connection.

        Raises:
            Exception: If all retry attempts are exhausted.
        """
        try:
            logger.debug("Attempting one-time database connection...")
            self.connection = pyodbc.connect(self.conn_string)
            logger.debug("Direct database connection established.")
            return self.connection
        except Exception as exc:
            logger.error("Database connection failed: %s", exc)
            sys.exit(6)

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType]
    ) -> None:
        """
        Guarantees connection termination. Rolls back uncommitted data if an error occurred.
        """
        if self.connection:
            try:
                if exc_type is not None:
                    self.connection.rollback()
                    logger.warning("Rolled back uncommitted transactions due to an error.")

                self.connection.close()
                logger.debug("Direct database connection closed securely.")
            except Exception as exc:
                logger.error("Error closing the database connection: %s", exc)


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Loads and validates the YAML configuration file.

    Args:
        config_path (str): The absolute path to the configuration YAML file.

    Returns:
        (Dict[str, str]): The complete configuration dictionary.

    Raises:
        (FileNotFoundError, yaml.YAMLError, KeyError): If config parsing fails.   
    """
    try:
        with open(config_path, 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
            if not config or 'db_connect' not in config:
                raise KeyError("Missing 'db_connect' block in config.yaml.")
            return config
    except FileNotFoundError:
        sys.stderr.write(f"'{config_path}' not found.")
        sys.exit(6)
    except yaml.YAMLError as exc:
        sys.stderr.write(f"'{config_path}' has invalid syntax. Details: {exc}\n")
        sys.exit(6)
    except Exception as exc:
        sys.stderr.write(f"An unexpected error occurred while loading config: {exc}\n")
        sys.exit(6)

def get_script_hashes_from_db(config: Dict[str, Any]) -> Dict[str, str]:
    """
    Fetches the verified script hashes required for execution.

    Args:
        config (dict[str, Any]): The configuration dictionary.

    Returns:
        Dict[str, str]: A dictionary map of script names to their verified hashes.
    """
    script_hashes: Dict[str, str] = {}

    try:
        db_cfg = config['db_connect']
        sql_statement = db_cfg['sql_statement']

        with DBDirectService(
            host=db_cfg['host'],
            database=db_cfg['database'],
            driver=db_cfg.get('driver', 'ODBC Driver 17 for SQL Server')
        ) as conn:
            cursor = conn.cursor()
            cursor.execute(sql_statement)

            for row in cursor.fetchall():
                script_hashes[row.script_name] = row.hash_value

        logger.info("Successfully loaded %d script hashes from DB.", len(script_hashes))
    except KeyError as exc:
        logger.error("Required property key missing from the config file: %s", exc)
        sys.exit(6)
    except Exception as exc:
        logger.error("Failed to fetch target script hashes from database: %s", exc)
        # We do not exit here; If hashes fail to load, the runner's strict verification
        # will naturally block execution and return Exit Code 3.

    return script_hashes
