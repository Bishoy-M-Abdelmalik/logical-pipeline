"""
logging_setup.py

Configures standardized file logging and console output for the pipeline engine.
"""
import os
import sys
import logging

def setup_logger(log_directory: str, file_name: str = "pipeline.log") -> logging.Logger:
    """
    Configures and returns the primary logger for the pipeline engine.

    Args:
        log_directory (str): The absolute path where log files should be stored.
        file_name (str): The name of the log file.

    Returns:
        logging.Logger: The configured pipeline logger instance.
    """
    logger = logging.getLogger("pipeline_debug")

    if logger.hasHandlers():
        return logger

    logger.setLevel(logging.DEBUG) 

    folder_path = os.path.join(log_directory, "logs")
    os.makedirs(folder_path, exist_ok=True)

    log_path = os.path.join(folder_path, file_name)

    # Standard Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | [%(module)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. File Handler
    file_handler = logging.FileHandler(filename=log_path, mode = 'a', encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # 2. Console Handler: Pipes strictly to sys.stderr for external schedulers
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.WARNING)    # (WARNING and above)
    stderr_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stderr_handler)

    return logger
