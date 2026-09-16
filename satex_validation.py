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
                try:
                    literal = int(token)
                except ValueError:
                    break   # some solvers append a comment to their model line
                if literal:
                    model.append(literal)

    # a wrapper script and its solver may both print the same status line
    if len(set(statuses)) != 1:
        raise ValidationError(
            f"expected exactly one result status, found {len(statuses)}"
            + (f" ({', '.join(sorted(set(statuses)))})" if statuses else "")
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
    model = validate_solver_result(expected_status, returncode, output)
    if expected_status == SATISFIABLE:
        variables, clauses = read_dimacs(cnf_path)
        validate_model(variables, clauses, model)


def validate_solver_result(
    expected_status: str, returncode: int, output: str
) -> list[int]:
    """Validate the exit code and textual status, then return model literals."""
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
    return model


def _text_proof_steps(data: bytes) -> Iterator[tuple[bool, tuple[int, ...]]]:
    try:
        text = data.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValidationError("proof is neither text DRUP nor binary DRAT") from exc
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("c") or line.startswith("o "):
            continue   # comments, and the "o proof DRAT" header written by riss
        deletion = line.startswith("d ")
        fields = line[1:].split() if deletion else line.split()
        try:
            literals = [int(token) for token in fields]
        except ValueError as exc:
            raise ValidationError(f"invalid proof line {line_number}: {line[:60]!r}") from exc
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
    if value >= 1 << 31:
        # Some solvers (IsaSAT) write the literal code as a signed 32-bit
        # integer; decode it the way drat-trim does with its int arithmetic.
        value -= 1 << 32
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
    return _propagate(clauses, assumptions)[0]


def _propagate(
    clauses: Iterable[tuple[int, ...]], assumptions: Iterable[int]
) -> tuple[bool, dict[int, bool]]:
    """Unit propagation; return (conflict, assignment)."""
    assignment: dict[int, bool] = {}
    for literal in assumptions:
        variable = abs(literal)
        value = literal > 0
        if variable in assignment and assignment[variable] != value:
            return True, assignment
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
                return True, assignment
            if len(unresolved) == 1:
                literal = unresolved[0]
                variable = abs(literal)
                value = literal > 0
                if variable in assignment:
                    if assignment[variable] != value:
                        return True, assignment
                else:
                    assignment[variable] = value
                    changed = True
    return False, assignment


def _is_rat(
    clauses: list[tuple[int, ...]], clause: tuple[int, ...]
) -> bool:
    """Resolution asymmetric tautology check on the first literal (DRAT)."""
    if not clause:
        return False
    pivot = clause[0]
    for other in clauses:
        if -pivot not in other:
            continue
        resolvent = clause + tuple(l for l in other if l != -pivot)
        if not _unit_conflict(clauses, (-literal for literal in resolvent)):
            return False
    return True


def _is_reason_clause(
    clauses: list[tuple[int, ...]], clause: tuple[int, ...]
) -> bool:
    """True when the clause is unit under top-level propagation.

    Solvers commonly delete clauses that are the reason of a top-level unit;
    like drat-trim, such deletions are ignored to keep the proof checkable.
    """
    _, assignment = _propagate(clauses, ())
    not_false = [l for l in clause if assignment.get(abs(l)) != (l < 0)]
    return len(not_false) == 1


def validate_drup_proof(cnf_path: str | Path, proof_path: str | Path) -> None:
    """Validate a text DRUP or binary DRAT proof.

    Each added clause must be RUP or RAT (on its first literal) with respect to
    the current clause set.  Deletions of clauses that are the reason of a
    top-level unit are ignored, as drat-trim does.  This checker is meant for
    the small repository smoke instances only.
    """
    _, original_clauses = read_dimacs(cnf_path)
    proof_data = Path(proof_path).read_bytes()
    if not proof_data:
        raise ValidationError("proof file is empty")

    # binary DRAT starts with an 'a' or 'd' marker byte followed by a varint, never by a space or digit
    binary = len(proof_data) > 1 and proof_data[0] in (0x61, 0x64) and proof_data[1] not in b" \t\r\n0123456789-"
    steps = (
        _binary_proof_steps(proof_data)
        if binary
        else _text_proof_steps(proof_data)
    )
    clauses = list(original_clauses)
    derived_empty = False
    step_count = 0
    for deletion, clause in steps:
        step_count += 1
        if deletion:
            if _is_reason_clause(clauses, clause):
                continue
            try:
                clauses.remove(clause)
            except ValueError:
                pass
            continue
        if not _unit_conflict(clauses, (-literal for literal in clause)):
            if not _is_rat(clauses, clause):
                raise ValidationError(
                    f"proof step {step_count} is neither RUP nor RAT"
                )
        clauses.append(clause)
        if not clause:
            derived_empty = True
            break

    if not derived_empty and not _unit_conflict(clauses, ()):
        # Like drat-trim, accept a proof whose final clause set is refuted by
        # unit propagation even if the empty clause is not written explicitly.
        raise ValidationError("proof does not derive the empty clause")
