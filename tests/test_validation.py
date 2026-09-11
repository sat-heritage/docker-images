import io
import tarfile
import tempfile
import unittest
from pathlib import Path

import satex
from satex_validation import (
    SATISFIABLE,
    UNSATISFIABLE,
    ValidationError,
    validate_drup_proof,
    validate_solver_run,
)

TESTS = Path(__file__).parent


class SolverResultTests(unittest.TestCase):
    def test_valid_sat_model(self):
        output = "s SATISFIABLE\nv -1 2 3 -4 5 6 7 8 9 -10 -11 12 13 -14 -15 16 0\n"
        validate_solver_run(TESTS / "quinn.cnf", SATISFIABLE, 10, output)

    def test_invalid_sat_model_is_rejected(self):
        output = "s SATISFIABLE\nv -1 -2 -3 0\n"
        with self.assertRaisesRegex(ValidationError, "does not satisfy clause"):
            validate_solver_run(TESTS / "quinn.cnf", SATISFIABLE, 10, output)

    def test_wrong_exit_code_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "return code"):
            validate_solver_run(
                TESTS / "simple-unsat.cnf",
                UNSATISFIABLE,
                11,
                "s UNSATISFIABLE\n",
            )

    def test_timeout_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "timed out"):
            validate_solver_run(
                TESTS / "simple-unsat.cnf",
                UNSATISFIABLE,
                124,
                "s UNSATISFIABLE\n",
            )

    def test_status_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "expected status"):
            validate_solver_run(
                TESTS / "simple-unsat.cnf",
                UNSATISFIABLE,
                20,
                "s SATISFIABLE\nv 1 0\n",
            )


class ProofTests(unittest.TestCase):
    def _proof(self, data):
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            self.addCleanup(Path(tmp.name).unlink, missing_ok=True)
            tmp.write(data)
            return tmp.name

    def test_text_drup_proof(self):
        validate_drup_proof(TESTS / "simple-unsat.cnf", self._proof(b"0\n"))

    def test_binary_drat_proof(self):
        validate_drup_proof(TESTS / "simple-unsat.cnf", self._proof(b"a\x00"))

    def test_glucose_hybrid_binary_proof(self):
        proof = b"a\x00d\x03\x000\n"
        validate_drup_proof(TESTS / "simple-unsat.cnf", self._proof(proof))

    def test_proof_without_empty_clause_is_rejected(self):
        with self.assertRaisesRegex(ValidationError, "empty clause"):
            validate_drup_proof(TESTS / "simple-unsat.cnf", self._proof(b"1 0\n"))


class SafetyTests(unittest.TestCase):
    def test_image_name_must_match_entire_string(self):
        self.assertTrue(satex.valid_name("cadical:2019"))
        self.assertFalse(satex.valid_name("cadical:2019/escape"))
        self.assertFalse(satex.valid_name("UPPERCASE:2019"))

    def test_check_cmd_observes_return_code(self):
        self.assertTrue(satex.check_cmd(["sh", "-c", "exit 0"]))
        self.assertFalse(satex.check_cmd(["sh", "-c", "exit 42"]))

    def test_tar_path_traversal_is_rejected(self):
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode="w") as archive:
            member = tarfile.TarInfo("../escape")
            member.size = 1
            archive.addfile(member, io.BytesIO(b"x"))
        data.seek(0)
        with (
            tempfile.TemporaryDirectory() as output_dir,
            tarfile.open(fileobj=data, mode="r") as archive,
            self.assertRaises(tarfile.FilterError),
        ):
            list(satex.safe_tar_members(archive, output_dir))


if __name__ == "__main__":
    unittest.main()
