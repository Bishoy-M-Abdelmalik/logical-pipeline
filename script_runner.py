"""
script_runner.py

Handles the dynamic importing and execution of target Python scripts located 
outside the engine's directory hierarchy. Enforces strict exit code mapping 
for interoperability with external schedulers.
"""
import os
import sys
import importlib.util
import logging
from typing import List, Any

logger = logging.getLogger("pipeline_debug")

def import_and_run(
    script_name: str,
    args: List[Any],
    environment_root: str
) -> int:
    """
    Locates, compiles, and executes a target Python script dynamically.

    Args:
        script_name (str): The name of the target script and its parent directory.
        args (List[Any]): Arguments to pass to the script's entry function.
        environment_root (str): The absolute path to the environment directory.

    Returns:
        int: Standardized exit code (0 for success, >0 for errors, <0 for warnings).
    """
    logger.info("=== STARTING EXECUTION: %s ===", script_name)

    # 1. Path and script Resolution
    script_folder = os.path.join(environment_root, script_name)
    script_path = os.path.join(script_folder, f"{script_name}.py")

    if not os.path.isdir(script_folder):
        logger.error("Script folder not found at: %s", script_folder)
        return 7

    if not os.path.isfile(script_path):
        logger.error("Script file not found at: %s", script_path)
        return 7

    # 2. Contextual Execution
    # Injecting the target script's directory into the front of sys.path
    # so its internal sub-module imports resolve correctly.
    sys.path.insert(0, script_folder)

    try:
        # Module Compilation
        spec = importlib.util.spec_from_file_location(script_name, script_path)
        if spec is None or spec.loader is None:
            raise ImportError("importlib failed to create a module specification.")

        module = importlib.util.module_from_spec(spec)
        sys.modules[script_name] = module
        spec.loader.exec_module(module)
    except Exception as exc:
        logger.error("Failed to compile script '%s': %s", script_name, exc)
        return 4

    # 3. Entry Point Execution
    try:
        # Assumes the entry point function matches the script name
        if not hasattr(module, script_name):
            logger.error("Execution failed: Function '%s()' not found in module.", script_name)
            return 4

        entry_func = getattr(module, script_name)

        if args:
            logger.info("Executing with arguments: %s", args)

        # Execute the target payload
        entry_func(args)

        logger.info("=== FINISHED EXECUTION: %s ===", script_name)
        return 0

    except Warning as wrn:
        logger.warning("Warning encountered in '%s': %s", script_name, wrn)
        return -1

    except Exception as exc:
        logger.error("Runtime crash in '%s': %s", script_name, exc)
        return 5

    finally:
        # Guarantee strict environment isolation is restored,
        # even if the payload script crashes.
        if script_folder in sys.path:
            sys.path.remove(script_folder)
