"""
syntax_compiler.py

Converts raw logical expression strings into an executable AST using a token scanner and a recursive
 descent parser. Safely isolates script arguments containing nested brackets, lists, or commas.
"""
import logging
from enum import Enum
from  ast import literal_eval
from typing import List, Tuple, Optional
from expression_ast.ast_nodes import Node, ScriptNode, NotNode, AndNode, OrNode

logger = logging.getLogger("pipeline_debug")

class TokenType(Enum):
    """Enumeration of valid token categories within the expression string."""
    OPERATOR = "OPERATOR"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    SCRIPT = "SCRIPT"

def tokenize_expression(expr: str) -> List[Tuple[TokenType, str]]:
    """
    Scans the expression character-by-character to generate a safe token stream.

    Ignores complex structures (like lists or quotes) when they occur inside 
    script bounds to protect downstream evaluation logic.

    Args:
        expr (str): The raw logical expression string.

    Returns:
        List[Tuple[TokenType, str]]: A list of classified tokens and their literal string values.

    Raises:
        ValueError: If an unrecognized or malformed syntax pattern is encountered.
    """
    tokens: List[Tuple[TokenType, str]] = []
    length = len(expr)
    i = 0

    while i < length:
        char = expr[i]

        if char.isspace() or char == ",":
            i += 1
            continue

        if char == "[":
            tokens.append((TokenType.LBRACKET, "["))
            i += 1
            continue

        if char == "]":
            tokens.append((TokenType.RBRACKET, "]"))
            i += 1
            continue

        # Check multi-character operators
        if expr[i:i+2] in ["&&", "||"]:
            tokens.append((TokenType.OPERATOR, expr[i:i+2]))
            i += 2
            continue

        if char in ["&", "|", "!"]:
            tokens.append((TokenType.OPERATOR, char))
            i += 1
            continue

        # Isolate Script boundaries: matching balanced parentheses
        if char == "(":
            start_pos = i
            depth = 0
            in_quotes = False
            quote_char = ""

            while i < length:
                current = expr[i]

                # Manage string literal bounds within arguments
                if current in ['"', "'"] and expr[i-1] != "\\":
                    if not in_quotes:
                        in_quotes = True
                        quote_char = current
                    elif current == quote_char:
                        in_quotes = False

                if not in_quotes:
                    if current == "(":
                        depth += 1
                    elif current == ")":
                        depth -= 1
                        if depth == 0:
                            tokens.append((TokenType.SCRIPT, expr[start_pos:i+1]))
                            i += 1
                            break
                i += 1
            continue

        # If a character matches nothing recognizable, raise validation failure
        context_start = max(0, i - 15)
        context_end = min(length, i + 15)
        snippet = expr[context_start:context_end]

        # Calculate where to point the arrow relative to the snippet
        pointer_pos = i - context_start
        pointer_line = (" " * pointer_pos) + "^"

        error_message = (
            f"Unrecognized syntax pattern at index {i}: '{char}'\n"
            f"Context:\n"
            f"  {snippet}\n"
            f"  {pointer_line}"
        )
        raise ValueError(error_message)

    return tokens

def parse_script_token(token_str: str) -> ScriptNode:
    """
    Deconstructs a valid script token string into a structured ScriptNode.
    Safely converts argument substrings into authentic Python literals.

    Args:
        token_str (str): The isolated script string (e.g., "(MyScript:['arg'])").

    Returns:
        ScriptNode: A fully instantiated ScriptNode with correctly typed arguments.

    Raises:
        ValueError: If argument deserialization fails due to malformed Python literals.
    """
    # Strip outer parentheses: "(MyScript:['arg'])" -> "MyScript:['arg']"
    content = token_str.strip()[1:-1].strip()

    if ":" not in content:
        return ScriptNode(name=content, args=[])

    colon_idx = content.find(":")
    script_name = content[:colon_idx].strip()
    args_raw = content[colon_idx+1:].strip()

    try:
        # Wrap the raw string inside an explicit tuple definition
        parsed_args = literal_eval(f"({args_raw},)")
        # Flatten singular collections to a clean python list
        return ScriptNode(name=script_name, args=list(parsed_args))
    except Exception as exc:
        raise ValueError(
            f"Failed to safely deserialize arguments for script '{script_name}': {exc}"
        ) from exc

def build_ast(tokens: List[Tuple[TokenType, str]], index: int = 0) -> Tuple[Optional[Node], int]:
    """Recursively parses a processed token stream into a nested AST hierarchy.

    Args:
        tokens (List[Tuple[TokenType, str]]): The tokenized stream.
        index (int): The current position in the token stream. Defaults to 0.

    Returns:
        Tuple[Optional[Node], int]: The constructed node and the index of the next unparsed token.

    Raises:
        SyntaxError: If an operator is missing explicit block encapsulation '[ ]',
                     or if an unknown logical operator is encountered.
    """
    if index >= len(tokens):
        return None, index

    token_type, token_val = tokens[index]

    if token_type == TokenType.SCRIPT:
        return parse_script_token(token_val), index + 1

    if token_type == TokenType.OPERATOR:
        if token_val == "!":
            child, next_idx = build_ast(tokens, index + 1)
            return NotNode(child=child), next_idx

        # Initialize explicit logical multi-branch operator nodes
        node: Node
        if token_val == "&&":
            node = AndNode(short_circuit=True)
        elif token_val == "&":
            node = AndNode(short_circuit=False)
        elif token_val == "||":
            node = OrNode(short_circuit=True)
        elif token_val == "|":
            node = OrNode(short_circuit=False)
        else:
            raise SyntaxError(f"Unknown logical operator '{token_val}'")

        next_idx = index + 1
        if next_idx >= len(tokens) or tokens[next_idx][0] != TokenType.LBRACKET:
            raise SyntaxError(
                f"Logical Operator '{token_val}' requires explicit block encapsulation '[ ]'.")

        next_idx += 1  # Skip opening structural LBRACKET
        while next_idx < len(tokens) and tokens[next_idx][0] != TokenType.RBRACKET:
            child_node, next_idx = build_ast(tokens, next_idx)
            if child_node:
                node.add_child(child_node)

        return node, next_idx + 1  # Skip closing structural RBRACKET

    return None, index

def parse_logical_expression(expression: str) -> Optional[Node]:
    """Primary execution driver to safely convert a raw configuration string into an AST.

    Args:
        expression (str): The raw pipeline input string.

    Returns:
        Optional[Node]: The root node of the parsed Abstract Syntax Tree, or None if parsing fails.
    """
    try:
        tokens = tokenize_expression(expression)
        tree, _ = build_ast(tokens, 0)
        return tree
    except Exception as exc:
        logger.error("Parsing compilation aborted: %s", exc)
        return None

def collect_script_names_from_tree(node: Optional[Node]) -> List[str]:
    """Recursively interrogates the parsed AST to build a deduplicated inventory of scripts.

    Args:
        node (Optional[Node]): The root or current node of the AST to search.

    Returns:
        List[str]: A sorted, deduplicated list of target script names required for execution.
    """
    if not node:
        return []
    if isinstance(node, ScriptNode):
        return [node.name]
    if isinstance(node, NotNode):
        return collect_script_names_from_tree(node.child)

    names: List[str] = []
    if hasattr(node, "children"):
        for child in getattr(node, "children"):
            names.extend(collect_script_names_from_tree(child))
    return sorted(list(set(names)))
