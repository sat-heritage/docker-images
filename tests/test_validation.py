import io
import json
import tarfile
import tempfile
import unittest
from types import SimpleNamespace
from urllib.error import HTTPError
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

    def test_host_timeout_stops_legacy_image_run(self):
        run_args = {
            "stdout": satex.subprocess.PIPE,
            "stderr": satex.subprocess.STDOUT,
            "text": True,
        }
        result = satex.run_docker_process(
            ["sh", "-c", "printf started; sleep 1"],
            run_args,
            0.05,
            ["true"],
            "test-container",
        )
        self.assertEqual(result.returncode, 124)
        self.assertEqual(result.stdout, "started")

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


class BuildDiagnosticTests(unittest.TestCase):
    def test_source_url_brace_expansion(self):
        self.assertEqual(
            satex.brace_expand("https://example.test/{one,two}.tar.gz"),
            [
                "https://example.test/one.tar.gz",
                "https://example.test/two.tar.gz",
            ],
        )

    def test_dockerfile_base_images_ignore_named_stages(self):
        with tempfile.TemporaryDirectory() as directory:
            dockerfile = Path(directory) / "Dockerfile"
            dockerfile.write_text(
                "FROM debian:stretch AS source\n"
                "FROM source AS builder\n"
                "FROM ${BASE} AS runtime\n"
                "FROM runtime AS image\n",
                encoding="utf-8",
            )
            self.assertEqual(
                satex.dockerfile_base_images(directory),
                ["debian:stretch"],
            )

    def test_build_reporter_writes_json_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            status_file = Path(directory) / "status.jsonl"
            reporter = satex.BuildReporter(
                SimpleNamespace(terse=False, status_file=str(status_file))
            )
            reporter.report("fail", "glucose:2011", "source-download", "HTTP 404")
            event = json.loads(status_file.read_text(encoding="utf-8"))
            self.assertEqual(event["stage"], "source-download")
            self.assertEqual(event["detail"], "HTTP 404")

    def test_http_error_has_stable_diagnostic(self):
        error = HTTPError("https://example.test/missing", 404, "", {}, None)
        try:
            self.assertEqual(satex.source_error_detail(error), "HTTP 404")
        finally:
            error.close()

    def test_historical_digest_base_has_safe_cache_tag(self):
        base = (
            "debian:bullseye-20220711-slim@sha256:"
            "f576b8067b77ff85c70725c976b7b6cde960898e2f19b9abab3fb148407614e2"
        )
        tag = satex.base_cache_tag("v1", base, "20220711T000000Z")
        self.assertEqual(
            tag,
            "v1-debian-bullseye-20220711-slim-f576b8067b77-snapshot-20220711",
        )
        self.assertNotIn("@", tag)
        self.assertLessEqual(len(tag), 128)


if __name__ == "__main__":
    unittest.main()
