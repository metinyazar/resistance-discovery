from pathlib import Path

_DIR = Path(__file__).parent

QUERY_PARSER = (_DIR / "query_parser.md").read_text()
SOURCE_PLANNER = (_DIR / "source_planner.md").read_text()
HARMONIZER = (_DIR / "harmonizer.md").read_text()
EVIDENCE_INTERPRETER = (_DIR / "evidence_interpreter.md").read_text()
LITERATURE = (_DIR / "literature.md").read_text()
REPORT_GENERATOR = (_DIR / "report_generator.md").read_text()
