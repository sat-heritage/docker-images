import hashlib
import importlib.util
import json
import stat
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "tools" / "archive_competition_solvers.py"
SPEC = importlib.util.spec_from_file_location("archive_competition_solvers", SCRIPT)
assert SPEC and SPEC.loader
archiver = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(archiver)


class CompetitionArchiveTests(unittest.TestCase):
    def make_zip(self, directory: Path) -> Path:
        path = directory / "competition.zip"
        with zipfile.ZipFile(path, "w") as archive:
            executable = zipfile.ZipInfo("Solver-A/bin/solve")
            executable.external_attr = (stat.S_IFREG | 0o755) << 16
            archive.writestr(executable, b"#!/bin/sh\n")
            archive.writestr("Solver-A/README", b"solver A\n")
            archive.writestr("Solver-B/main.c", b"int main(void) { return 0; }\n")
            archive.writestr("README.txt", b"competition metadata\n")
        return path

    def test_discovers_only_top_level_solver_directories(self):
        with tempfile.TemporaryDirectory() as directory:
            archive = archiver.SolverArchive(self.make_zip(Path(directory)))
            self.assertEqual(archive.roots(), ["Solver-A", "Solver-B"])

    def test_packages_selected_solver_and_preserves_executable_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_zip(root)
            output = root / "output"
            assets, manifest = archiver.mirror(
                "2022", [str(source)], output, {"Solver-A"}, {}
            )
            self.assertEqual([path.name for path in assets], ["Solver-A.zip"])
            self.assertEqual(manifest["assets"][0]["solver"], "Solver-A")
            self.assertEqual(manifest["assets"][0]["archive_format"], "zip")
            with zipfile.ZipFile(assets[0]) as archive:
                names = archive.namelist()
                self.assertEqual(
                    names, ["Solver-A/", "Solver-A/README", "Solver-A/bin/solve"]
                )
                mode = archive.getinfo("Solver-A/bin/solve").external_attr >> 16
                self.assertEqual(stat.S_IMODE(mode), 0o755)

    def test_explicit_tar_xz_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_zip(root)
            assets, manifest = archiver.mirror(
                "2022", [str(source)], root / "output", {"Solver-B"}, {}, "tar.xz"
            )
            self.assertEqual(assets[0].name, "Solver-B.tar.xz")
            self.assertEqual(manifest["assets"][0]["archive_format"], "tar.xz")
            with tarfile.open(assets[0], "r:xz") as archive:
                self.assertIn("Solver-B/main.c", archive.getnames())

    def test_output_is_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.make_zip(root)
            first, _ = archiver.mirror("2022", [str(source)], root / "one", set(), {})
            second, _ = archiver.mirror("2022", [str(source)], root / "two", set(), {})
            first_hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in first]
            second_hashes = [hashlib.sha256(path.read_bytes()).hexdigest() for path in second]
            self.assertEqual(first_hashes, second_hashes)

    def test_rejects_unknown_solver(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(archiver.ArchiveError, "unknown solver"):
                archiver.mirror(
                    "2022", [str(self.make_zip(root))], root / "output", {"Missing"}, {}
                )

    def test_dry_run_writes_manifest_without_uploading(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output = root / "output"
            status = archiver.main(
                [
                    "2022",
                    "--archive",
                    str(self.make_zip(root)),
                    "--solver",
                    "Solver-B",
                    "--output-dir",
                    str(output),
                ]
            )
            self.assertEqual(status, 0)
            data = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(data["assets"][0]["asset"], "Solver-B.zip")


if __name__ == "__main__":
    unittest.main()
