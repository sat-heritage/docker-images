"""Validation helpers for SAT solver smoke tests.

This module deliberately uses only the Python standard library so that the
``satex`` command remains usable on every supported Python version.
"""

from __future__ import annotations

import gzip
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

SATISFIABLE = "SATISFIABLE"
UNSATISFIABLE = "UNSATISFIABLE"
_STATUS_RE = re.compile(r"^s\s+(SATISFIABLE|UNSATISFIABLE|UNKNOWN)\s*$")


class ValidationError(ValueError):
    """Raised when a solver result or proof cannot be validated."""


def read_dimacs(path: str | Path) -> tuple[int, list[tuple[int, ...]]]:
    """Read a (possibly gzip-compressed) DIMACS CNF file."""
    path = Path(path)
    opener = gzip.open if path.suffix == ".gz" else open
    variables = None
    expected_clauses = None
    clauses: list[tuple[int, ...]] = []
    current: list[int] = []

    with opener(path, "rt", encoding="ascii", errors="strict") as stream:
        for line_number, raw_line in enumerate(stream, 1):
            line = raw_line.strip()
            if not line or line.startswith("c"):
                continue
            if line.startswith("p"):
                fields = line.split()
                if len(fields) != 4 or fields[1] != "cnf":
                    raise ValidationError(
                        f"invalid DIMACS header at line {line_number}"
                    )
                variables, expected_clauses = int(fields[2]), int(fields[3])
                continue
            if variables is None:
                raise ValidationError("DIMACS clauses appear before the header")
            for token in line.split():
                literal = int(token)
                if literal == 0:
                    clauses.append(tuple(current))
                    current = []
                else:
                    if abs(literal) > variables:
                        raise ValidationError(
                            f"literal {literal} exceeds declared variable count"
                        )
                    current.append(literal)

    if variables is None or expected_clauses is None:
        raise ValidationError("missing DIMACS header")
    if current:
        raise ValidationError("unterminated DIMACS clause")
    if len(clauses) != expected_clauses:
        raise ValidationError(
            f"DIMACS declares {expected_clauses} clauses but contains {len(clauses)}"
        )
    return variables, clauses


def parse_solver_output(output: str) -> tuple[str, list[int]]:
    """Return the unique competition status and the model literals."""
    statuses: list[str] = []
    model: list[int] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        match = _STATUS_RE.fullmatch(line)
        if match:
            statuses.append(match.group(1))
            continue
        if line.startswith("v ") or line == "v":
            for token in line[1:].split():
                literal = int(token)
                if literal:
                    model.append(literal)

    if len(statuses) != 1:
        raise ValidationError(
            f"expected exactly one result status, found {len(statuses)}"
        )
    return statuses[0], model


def validate_model(
    variables: int, clauses: Iterable[tuple[int, ...]], model: Iterable[int]
) -> None:
    """Check that a SAT model consistently satisfies every clause."""
    assignment: dict[int, bool] = {}
    for literal in model:
        variable = abs(literal)
        if variable == 0 or variable > variables:
            raise ValidationError(f"model literal {literal} is out of range")
        value = literal > 0
        if variable in assignment and assignment[variable] != value:
            raise ValidationError(f"model assigns variable {variable} twice")
        assignment[variable] = value

    for index, clause in enumerate(clauses, 1):
        if not any(assignment.get(abs(lit)) == (lit > 0) for lit in clause):
            raise ValidationError(f"model does not satisfy clause {index}")


def validate_solver_run(
    cnf_path: str | Path, expected_status: str, returncode: int, output: str
) -> None:
    """Validate exit code, textual status and, for SAT, the printed model."""
    if expected_status not in {SATISFIABLE, UNSATISFIABLE}:
        raise ValueError(f"unsupported expected status: {expected_status}")

    expected_code = 10 if expected_status == SATISFIABLE else 20
    if returncode == 124:
        raise ValidationError("solver timed out")
    if returncode not in {0, expected_code}:
        raise ValidationError(
            f"expected return code {expected_code} (or wrapper code 0), got {returncode}"
        )

    status, model = parse_solver_output(output)
    if status != expected_status:
        raise ValidationError(
            f"expected status {expected_status}, solver reported {status}"
        )
    if expected_status == SATISFIABLE:
        variables, clauses = read_dimacs(cnf_path)
        validate_model(variables, clauses, model)


def _text_proof_steps(data: bytes) -> Iterator[tuple[bool, tuple[int, ...]]]:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValidationError("proof is neither text DRUP nor binary DRAT") from exc
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("c"):
            continue
        deletion = line.startswith("d ")
        fields = line[1:].split() if deletion else line.split()
        try:
            literals = [int(token) for token in fields]
        except ValueError as exc:
            raise ValidationError(f"invalid proof line {line_number}") from exc
        if not literals or literals[-1] != 0:
            raise ValidationError(f"unterminated proof clause at line {line_number}")
        yield deletion, tuple(literals[:-1])


def _binary_literal(data: bytes, offset: int) -> tuple[int, int]:
    value = 0
    shift = 0
    while True:
        if offset >= len(data):
            raise ValidationError("truncated binary proof literal")
        byte = data[offset]
        offset += 1
        value |= (byte & 0x7F) << shift
        if not byte & 0x80:
            break
        shift += 7
        if shift > 63:
            raise ValidationError("oversized binary proof literal")
    if value == 0:
        return 0, offset
    variable = value >> 1
    return (-variable if value & 1 else variable), offset


def _binary_proof_steps(data: bytes) -> Iterator[tuple[bool, tuple[int, ...]]]:
    offset = 0
    while offset < len(data):
        marker = data[offset]
        if marker == ord("0") and data[offset:].strip() == b"0":
            # Glucose's vbyte writer appends its final empty clause as text.
            yield False, ()
            return
        offset += 1
        if marker not in (ord("a"), ord("d")):
            raise ValidationError(f"invalid binary proof marker 0x{marker:02x}")
        clause: list[int] = []
        while True:
            literal, offset = _binary_literal(data, offset)
            if literal == 0:
                break
            clause.append(literal)
        yield marker == ord("d"), tuple(clause)


def _unit_conflict(
    clauses: Iterable[tuple[int, ...]], assumptions: Iterable[int]
) -> bool:
    assignment: dict[int, bool] = {}
    for literal in assumptions:
        variable = abs(literal)
        value = literal > 0
        if variable in assignment and assignment[variable] != value:
            return True
        assignment[variable] = value

    changed = True
    clause_list = list(clauses)
    while changed:
        changed = False
        for clause in clause_list:
            unresolved: list[int] = []
            satisfied = False
            for literal in clause:
                value = assignment.get(abs(literal))
                if value is None:
                    unresolved.append(literal)
                elif value == (literal > 0):
                    satisfied = True
                    break
            if satisfied:
                continue
            if not unresolved:
                return True
            if len(unresolved) == 1:
                literal = unresolved[0]
                variable = abs(literal)
                value = literal > 0
                if variable in assignment:
                    if assignment[variable] != value:
                        return True
                else:
                    assignment[variable] = value
                    changed = True
    return False


def validate_drup_proof(cnf_path: str | Path, proof_path: str | Path) -> None:
    """Validate a text DRUP or binary DRAT proof using reverse unit propagation.

    DRAT additions that require the asymmetric-tautology rule are rejected.  The
    repository smoke test uses a tiny contradiction, for which all conforming
    proof-producing solvers can emit a short RUP proof.
    """
    _, original_clauses = read_dimacs(cnf_path)
    proof_data = Path(proof_path).read_bytes()
    if not proof_data:
        raise ValidationError("proof file is empty")

    steps = (
        _binary_proof_steps(proof_data)
        if b"\x00" in proof_data
        else _text_proof_steps(proof_data)
    )
    clauses = list(original_clauses)
    derived_empty = False
    step_count = 0
    for deletion, clause in steps:
        step_count += 1
        if deletion:
            try:
                clauses.remove(clause)
            except ValueError:
                pass
            continue
        if not _unit_conflict(clauses, (-literal for literal in clause)):
            raise ValidationError(f"proof step {step_count} is not RUP")
        clauses.append(clause)
        if not clause:
            derived_empty = True
            break

    if not derived_empty:
        raise ValidationError("proof does not derive the empty clause")
