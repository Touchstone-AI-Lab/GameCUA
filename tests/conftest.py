"""Adds the engine-test rubrics and trials under tests/fixtures/catalog to the repository catalog."""

from pathlib import Path

from gamecua import catalog
from gamecua.specs import InputProfile, Rubric, TrialSpec

BENCHMARKS = (Path(__file__).resolve().parents[1] / "benchmarks").resolve()
FIXTURES = Path(__file__).resolve().parent / "fixtures/catalog"
_init = catalog.Catalog.__init__


def _with_fixtures(self, root):
    _init(self, root)
    if Path(root).resolve() == BENCHMARKS:
        for kind, schema in (
            ("rubrics", Rubric),
            ("trials", TrialSpec),
            ("inputs", InputProfile),
        ):
            for path in sorted((FIXTURES / kind).glob("*.json")):
                item = schema.model_validate_json(path.read_text())
                getattr(self, kind).setdefault(item.id, item)


catalog.Catalog.__init__ = _with_fixtures
