"""
ast_nodes.py

Provides the Abstract Base Class for Abstract Syntax Tree (AST) nodes 
and their concrete implementations (AND, OR, NOT, Script).
"""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional, Any

class Node(ABC):
    """
    Abstract base class for all syntax tree nodes.
    Enforces the implementation of the evaluation contract for logical 
    and operational routing.
    """

    def __init__(self) -> None:
        self.result: Optional[int] = None

    @abstractmethod
    def evaluate(self, executor_func: Callable[..., int]) -> int:
        """
        Evaluates the current node logic.

        Args:
            executor_func (Callable): Function responsible for script execution. 
                Must return an exit code (int).

        Returns:
            int: The standardized exit code (0 for success, >0 for failures, and <0 for warnings).
        """

class ScriptNode(Node):
    """Node representing a single target script execution."""

    def __init__(self, name: str, args: Optional[List[Any]] = None) -> None:
        super().__init__()
        self.name: str = name
        self.args: List[Any] = args or []

    def evaluate(self, executor_func: Callable[..., int]) -> int:
        self.result = executor_func(self.name, self.args)
        return self.result

    def __str__(self) -> str:
        if self.args:
            return f"({self.name}:{','.join(str(arg) for arg in self.args)})"
        return f"({self.name})"

class NotNode(Node):
    """Node representing a logical NOT inversion operator."""

    def __init__(self, child: Optional[Node] = None) -> None:
        super().__init__()
        self.child: Optional[Node] = child

    def evaluate(self, executor_func: Callable[..., int]) -> int:
        if not self.child:
            self.result = 2  # Treat an empty NOT block as a generic logic failure
            return self.result

        child_result = self.child.evaluate(executor_func)
        # If child succeeded (0), flip to logic failure (2)
        # If child failed (!= 0), flip to success (0)
        self.result = 2 if child_result <= 0 else 0
        return self.result

    def __str__(self) -> str:
        return f"!{self.child}"

class LogicalOperatorNode(Node, ABC):
    """Abstract collector node for multi-child logical operators (AND/OR)."""

    def __init__(self, operator_symbol: str, children: Optional[List[Node]] = None) -> None:
        super().__init__()
        self.operator_symbol: str = operator_symbol
        self.children: List[Node] = children or []

    def add_child(self, child: Node) -> None:
        """Appends a child node to the evaluation sequence."""
        self.children.append(child)

    def __str__(self) -> str:
        children_str = ", ".join(str(child) for child in self.children)
        return f"{self.operator_symbol} [ {children_str} ]"

class AndNode(LogicalOperatorNode):
    """Node representing a short-circuit or non-short-circuit AND operation."""

    def __init__(self, children: Optional[List[Node]] = None, short_circuit: bool = True) -> None:
        symbol = "&&" if short_circuit else "&"
        super().__init__(symbol, children)
        self.short_circuit: bool = short_circuit

    def evaluate(self, executor_func: Callable[..., int]) -> int:
        # Default to logic failure if empty
        if not self.children:
            self.result = 2
            return self.result

        accumulated_result = 0
        for child in self.children:
            child_result = child.evaluate(executor_func)
            if child_result != 0:
                accumulated_result = child_result
                if self.short_circuit:
                    break

        self.result = accumulated_result
        return self.result

class OrNode(LogicalOperatorNode):
    """Node representing a short-circuit or non-short-circuit OR operation."""

    def __init__(self, children: Optional[List[Node]] = None, short_circuit: bool = True) -> None:
        symbol = "||" if short_circuit else "|"
        super().__init__(symbol, children)
        self.short_circuit: bool = short_circuit

    def evaluate(self, executor_func: Callable[..., int]) -> int:
        # Default to logic failure if empty
        if not self.children:
            self.result = 2
            return self.result

        accumulated_result = 2
        for child in self.children:
            child_result = child.evaluate(executor_func)
            if child_result == 0:
                accumulated_result = 0
                if self.short_circuit:
                    break
            elif child_result > 0:
                accumulated_result = child_result if accumulated_result != 0 else accumulated_result

        self.result = accumulated_result
        return self.result
