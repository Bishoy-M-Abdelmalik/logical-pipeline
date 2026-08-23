"""
pipeline_engine Module

Main entry point for the logical pipeline engine.
Triggered by an external scheduler. Parses logical expressions, verifies script
integrity, and coordinates isolated script execution.
"""
import os
import sys
from typing import Any, List

# Localized imports
from logging_setup import setup_logger
from db_connector import load_config, get_script_hashes_from_db
from directory_hash import verify_pipeline_hashes
from script_runner import import_and_run
from expression_ast.syntax_compiler import parse_logical_expression, collect_script_names_from_tree

# Establish absolute paths to the Environment Root
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
ENVIRONMENT_ROOT = os.path.dirname(ENGINE_DIR)


def pipeline_engine() -> None:
    """
    Main Pipeline Execution Entry Point.

    Validates arguments, establishes telemetry, verifies script integrity,
    and executes the logical AST pipeline. Exits with standardized status codes.
    """
    # 1. Parse CLI Arguments from external scheduler
    if len(sys.argv) != 4:
        sys.stderr.write(
            "Usage: python pipeline_engine.py <SessionID> <WorkingDirectory> <LogicalExpression>")
        sys.exit(1)

    session_id: str = sys.argv[1]
    working_directory: str = sys.argv[2]
    expression_string: str = sys.argv[3]

    # 2. Setup Telemetry
    # Use the working directory provided as the destination for the log files
    logger = setup_logger(log_directory=working_directory)
    logger.info("=== PIPELINE STARTED | SessionID: %s ===", session_id)
    logger.debug("Working Directory: %s", working_directory)
    logger.debug("Execution Tree: %s", expression_string)

    # 3. Load Configurations & Hashes
    config_path = os.path.join(ENGINE_DIR, "config.yaml")
    config = load_config(config_path)
    expected_hashes = get_script_hashes_from_db(config)

    # 4. Parse the Logical Expression into an AST
    expression_tree = parse_logical_expression(expression_string)
    logger.debug("Compiled AST Structure: %s", expression_tree)
    if expression_tree is None:
        # Error is already logged and written to sys.stderr by the syntax_compiler
        sys.exit(2)

    # 5. Extract Unique Scripts and Run Pre-flight Security Check
    target_scripts = collect_script_names_from_tree(expression_tree)
    logger.info("Identified %d unique scripts for execution.", len(target_scripts))

    if not verify_pipeline_hashes(target_scripts, expected_hashes, ENVIRONMENT_ROOT):
        logger.error("=== PRE-FLIGHT INTEGRITY CHECK FAILED | ABORTING EXECUTION ===")
        sys.exit(3)

    # 6. Define the Execution Interceptor
    def executor_wrapper(script_name: str, parsed_args: List[Any]) -> int:
        """
        Intercepts the AST node execution to inject SessionID and WorkingDirectory.
        Target scripts MUST have the signature:
        def my_script(args: List[Any])
        where args[0] is session_id, args[1] is working_directory, followed by any expression args.
        """
        # [arg1, arg2, ...] -> [session_id, working_directory, arg1, arg2, ...]
        injected_args = [session_id, working_directory]
        injected_args.extend(parsed_args)
        return import_and_run(script_name, injected_args, ENVIRONMENT_ROOT)

    # 7. Execute the Pipeline
    logger.info("Initiating recursive logical evaluation...")
    try:
        # Evaluate traverses the tree and calls executor_wrapper for every ScriptNode
        logical_result: int = expression_tree.evaluate(executor_func=executor_wrapper)

        # Map Results to standardized Exit Codes
        if logical_result > 0:
            logger.error("=== PIPELINE FINISHED WITH FAILURES ===")
            sys.exit(logical_result)
        else:
            logger.info("=== PIPELINE COMPLETED SUCCESSFULLY ===")
            sys.exit(logical_result)

    except Exception as exc:
        logger.critical("Unexpected Pipeline Crash: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    pipeline_engine()
