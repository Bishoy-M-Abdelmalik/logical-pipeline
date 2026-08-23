"""
directory_hash.py

Calculates and verifies deterministic SHA-256 hashes of directory structures.
Ensures code integrity by detecting unauthorized modifications to payload scripts
before the pipeline engine executes them.
"""
import os
import hashlib
import logging
from typing import List, Dict, Optional

logger = logging.getLogger("pipeline_debug")

def calculate_directory_hash(
    directory_path: str,
    exclude_dirs: Optional[List[str]] = None
) -> Optional[str]:
    """
    Calculates a deterministic hash of an entire directory structure.

    Sensitive to file contents and folder hierarchy, but insensitive to 
    metadata like file access times or OS-level sorting.

    Args:
        directory_path (str): Absolute path to the directory to hash.
        exclude_dirs (Optional[List[str]]): List of directory names to skip.

    Returns:
        Optional[str]: SHA-256 hash as a hex string, or None if the directory is empty/missing.
    """
    if not os.path.exists(directory_path):
        logger.error("Directory not found for hashing: %s", directory_path)
        return None

    if exclude_dirs is None:
        exclude_dirs = ['__pycache__']

    logger.debug("Calculating hash for directory: %s", directory_path)
    directory_entries: List[str] = []

    for root, dirs, files in os.walk(directory_path):
        # Safely modify dirs in-place to prevent os.walk from entering excluded folders
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        dirs.sort()    # Sort directories for consistent traversal

        # Include directory structure in the hash
        rel_dir_path = os.path.relpath(root, directory_path)
        if rel_dir_path != '.':    # Skip the root directory itself
            directory_entries.append(f"DIR:{rel_dir_path}")

        for filename in sorted(files):
            file_path = os.path.join(root, filename)

            if not os.access(file_path, os.R_OK):
                logger.warning("Skipping unreadable file: %s", file_path)
                continue

            rel_path = os.path.relpath(file_path, directory_path)

            try:
                with open(file_path, 'rb') as f:
                    content_hash = hashlib.sha256(f.read()).hexdigest()
                directory_entries.append(f"FILE:{rel_path}:{content_hash}")
            except Exception as exc:
                logger.warning("Error hashing file %s: %s", rel_path, exc)

    if not directory_entries:
        return None

    # Sort one final time to guarantee deterministic order
    directory_entries.sort()

    combined_hash = hashlib.sha256()
    for entry in directory_entries:
        combined_hash.update(entry.encode('utf-8'))

    return combined_hash.hexdigest()

def verify_directory_hash(
    directory_path: str,
    expected_hash: str,
    exclude_dirs: Optional[List[str]] = None
) -> bool:
    """
    Verifies that a directory's current hash matches the expected database hash.

    **note**: Exluding '__pycache__' by default if exclude_dirs is None

    Args:
        directory_path (str): Path to the directory to verify.
        expected_hash (str): The approved hash value fetched from the database.
        exclude_dirs (Optional[List[str]]): List of directory names to skip.

    Returns:
        bool: True if the hashes match perfectly, False otherwise.
    """
    if not expected_hash:
        logger.warning("No expected hash provided for %s.", directory_path)
        return False

    current_hash = calculate_directory_hash(directory_path, exclude_dirs)

    if current_hash == expected_hash:
        logger.info("Verification PASSED for: %s", directory_path)
        return True

    logger.error("Verification FAILED for %s.\nActual Hash: %s", directory_path, current_hash)
    return False

def verify_pipeline_hashes(
    script_names: List[str],
    expected_hashes: Dict[str, str],
    environment_root: str
) -> bool:
    """
    Pre-flight security check. Verifies the integrity of all target scripts 
    in the pipeline before the engine initiates execution.

    Args:
        script_names (List[str]): Unique list of scripts extracted from the AST.
        expected_hashes (Dict[str, str]): Dictionary mapping script names to valid hashes.
        environment_root (str): The absolute path to the environment directory.

    Returns:
        bool: True if all scripts pass verification, False if any script fails.
    """
    logger.info("Initiating pre-flight integrity check for %d scripts...", len(script_names))

    for script in script_names:
        expected_hash = expected_hashes.get(script)
        if not expected_hash:
            logger.error("No expected hash found in database for '%s'.", script)
            return False

        script_folder = os.path.join(environment_root, script)
        if not os.path.isdir(script_folder):
            logger.error("Target script folder missing at '%s'.", script_folder)
            return False

        is_valid = verify_directory_hash(script_folder, expected_hash)
        if not is_valid:
            logger.error("Integrity compromise (unmatched hash) detected in '%s'.", script)
            return False

    logger.info("Pre-flight integrity check PASSED for all scripts.")
    return True

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        # Pass the first argument as a string, not the slice list
        final_hash = calculate_directory_hash(sys.argv[1])
        print(f"Final computed hash for '{sys.argv[1]}': {final_hash}")
    else:
        print("Usage: python directory_hash.py <directory_path>")
