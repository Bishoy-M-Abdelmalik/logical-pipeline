```markdown
# logical-pipeline

A lightweight, isolated Python execution engine that evaluates logical expressions (AND / OR / NOT) against a set of payload scripts. It verifies script integrity via SHA-256 directory hashes stored in a database, then runs the selected scripts in an isolated environment and returns standardized integer exit codes.

## Features

- Custom recursive-descent parser for nested logical expressions
- Pre-flight cryptographic integrity checks (deterministic SHA-256 of entire script directories)
- Dynamic import and isolated execution of payload scripts
- Context-manager based database connections with automatic rollback
- Rotating / structured logging to both file and stderr
- POSIX-style integer exit codes for easy integration with external schedulers

## Prerequisites

- Python 3.9+
- Microsoft ODBC Driver 17 for SQL Server (or compatible)
- Python packages: `pyodbc`, `tenacity`, `PyYAML`

Install dependencies:

```bash
pip install pyodbc tenacity PyYAML
```

## Quick Start

1. Edit `config.yaml` with your database connection details (see schema below).
2. Place payload scripts in sibling directories under the environment root (one folder + matching `.py` file per script).
3. Run:

```bash
python pipeline_engine.py <SessionID> <WorkingDirectory> "<LogicalExpression>"
```

Example:

```bash
python pipeline_engine.py "SESSION_001" "/tmp/logs/session001" "&& [ (DataExtractor:['daily']), (SFTPUpload:['/path/example']) ]"
```

## Logical Expression Syntax

### Target Scripts

Scripts are enclosed in parentheses. Optional arguments follow a colon and must be valid Python literals:

- Basic: `(MyScript)`
- With arguments: `(MyScript:['dev_mode', 10, 'str_arg'])`

### Operators

| Operator | Meaning                          | Syntax example                          |
|----------|----------------------------------|-----------------------------------------|
| `&&`     | Short-circuit AND                | `&& [ (ScriptA), (ScriptB) ]`           |
| `&`      | Non-short-circuit AND            | `& [ (ScriptA), (ScriptB) ]`            |
| `\|\|`   | Short-circuit OR (fallback)      | `\|\| [ (Primary), (Backup) ]`          |
| `\|`     | Non-short-circuit OR             | `\| [ (Primary), (Backup) ]`            |
| `!`      | Logical NOT                      | `! (MyScript)`                          |

Complex nesting is supported:

```
&& [ (ExtractData:['row_data']), || [ (UploadSFTP), (TriggerAlert) ] ]
```

## Configuration

`config.yaml` must contain a `db_connect` block:

```yaml
db_connect:
  host: "localhost"
  database: "script_registry"
  driver: "ODBC Driver 17 for SQL Server"
  sql_statement: "SELECT script_name, hash_value FROM script_hashes"
```

The SQL statement must return columns named `script_name` and `hash_value`.

## Project Layout

```
Environment_Root/
├── logical-pipeline/           # This engine
│   ├── pipeline_engine.py      # CLI entry point
│   ├── config.yaml             # DB connection settings
│   ├── script_runner.py        # Dynamic import & execution
│   ├── directory_hash.py       # SHA-256 integrity verification
│   ├── db_connector.py         # Config loading & DB access
│   ├── logging_setup.py        # Logging configuration
│   └── expression_ast/         # AST nodes & parser
│       ├── ast_nodes.py
│       └── syntax_compiler.py
│
├── Payload_Script_A/           # Example payload
│   └── Payload_Script_A.py
└── Payload_Script_B/
    └── Payload_Script_B.py
```

Payload scripts must expose a top-level function whose name matches the script (and folder) name. The function receives a single list argument containing:

1. `session_id` (str)
2. `working_directory` (str)
3. any additional arguments supplied in the logical expression

## Exit Codes

| Code | Meaning                        |
|------|--------------------------------|
| 0    | Success                        |
| -1   | Warning (non-fatal)            |
| 1    | Unexpected engine crash        |
| 2    | Logic / syntax fault           |
| 3    | Integrity check failure         |
| 4    | Script compilation failure     |
| 5    | Runtime exception in script    |
| 6    | Database / configuration fault |
| 7    | Path resolution failure        |

## Security Notes

- Argument deserialization uses `ast.literal_eval` only (no `eval`).
- Directory hashes include both file contents and relative path structure, making unauthorized modifications detectable.
- `sys.path` is temporarily extended for each payload and restored afterwards to avoid namespace leakage.

## License

MIT License

Copyright (c) 2026

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```