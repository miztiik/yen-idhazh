"""Which stream failures preserve complete event records and explicit failure?"""

import io
import tempfile
import unittest
from pathlib import Path

from capture_stream import EventFile, EventRecords, mirror_record


class EventStreamTests(unittest.TestCase):
    def test_fragmented_records_preserve_exact_bytes_and_deliver_before_eof(self) -> None:
        records: list[bytes] = []
        errors: set[str] = set()
        first = b'{"source":"/services/text-analysis","time":"2026-11-09T19:00:00Z"}\n'
        second = b'{"source":"/services/text-analysis/gliner","data":{"status":"stopped"}}\n'
        reader = EventRecords(max(len(first), len(second)), records.append, errors)
        stream = io.BytesIO(first + second)
        while chunk := stream.read(7):
            reader.feed(chunk)
        self.assertEqual(records, [first, second])
        reader.finish()
        self.assertFalse(errors)

    def test_oversized_record_is_bounded_and_later_complete_records_survive(self) -> None:
        records: list[bytes] = []
        errors: set[str] = set()
        reader = EventRecords(8, records.append, errors)
        for _ in range(10):
            reader.feed(b"private")
            self.assertLess(len(reader.pending), reader.limit)
        reader.feed(b"\n{}\n")
        reader.finish()
        self.assertEqual(records, [b"{}\n"])
        self.assertTrue(errors)
        self.assertNotIn("private", " ".join(errors))

    def test_unterminated_record_is_not_reported_as_complete(self) -> None:
        records: list[bytes] = []
        errors: set[str] = set()
        reader = EventRecords(16, records.append, errors)
        reader.feed(b"{}\nprivate")
        reader.finish()
        self.assertEqual(records, [b"{}\n"])
        self.assertTrue(errors)
        self.assertNotIn("private", " ".join(errors))

    def test_console_and_atomically_finished_file_keep_identical_complete_records(self) -> None:
        errors: set[str] = set()
        console = io.BytesIO()
        records = b'{"status":"starting"}\n', b'{"status":"stopped"}\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spacy" / "events.jsonl"
            destination = EventFile(path, "spaCy", errors)
            expected = b""
            for record in records:
                mirror_record(record, destination, console, errors)
                expected += record
                self.assertEqual(console.getvalue(), expected)
            self.assertFalse(path.exists())
            destination.finish()
            self.assertEqual(path.read_bytes(), b"".join(records))
        self.assertFalse(errors)

    def test_console_failure_does_not_discard_the_provider_file(self) -> None:
        errors: set[str] = set()
        console = io.BytesIO()
        console.close()
        record = b'{"status":"failed"}\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "gliner" / "events.jsonl"
            destination = EventFile(path, "GLiNER", errors)
            mirror_record(record, destination, console, errors)
            destination.finish()
            self.assertEqual(path.read_bytes(), record)
        self.assertTrue(errors)
        self.assertIn("console", " ".join(errors))

    def test_file_failure_preserves_its_valid_prefix_and_continues_console_delivery(self) -> None:
        errors: set[str] = set()
        console = io.BytesIO()
        first, second = b'{"status":"ready"}\n', b'{"status":"stopped"}\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spacy" / "events.jsonl"
            destination = EventFile(path, "spaCy", errors)
            mirror_record(first, destination, console, errors)
            self.assertIsNotNone(destination.stream)
            if destination.stream is not None:
                destination.stream.write(b'{"uncommitted":')
                destination.stream.close()
            mirror_record(second, destination, console, errors)
            destination.finish()
            self.assertEqual(path.read_bytes(), first)
        self.assertEqual(console.getvalue(), first + second)
        self.assertTrue(errors)
        self.assertIn("spaCy event file", " ".join(errors))

    def test_file_open_failure_still_allows_console_delivery(self) -> None:
        errors: set[str] = set()
        console = io.BytesIO()
        record = b'{"status":"failed"}\n'
        with tempfile.TemporaryDirectory() as directory:
            blocked = Path(directory) / "blocked"
            blocked.write_bytes(b"not a directory")
            destination = EventFile(blocked / "events.jsonl", "GLiNER", errors)
            mirror_record(record, destination, console, errors)
            destination.finish()
        self.assertEqual(console.getvalue(), record)
        self.assertTrue(errors)
        self.assertIn("could not be opened", " ".join(errors))


if __name__ == "__main__":
    unittest.main()
