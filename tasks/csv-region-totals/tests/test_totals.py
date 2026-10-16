import csv
from pathlib import Path

def test_totals():
    rows = list(csv.reader(Path("totals.csv").read_text().strip().splitlines()))
    assert rows[0] == ["region", "total"]
    assert [(r, int(t)) for r, t in rows[1:]] == [('central', 3211), ('east', 7723), ('north', 6468), ('south', 7883), ('west', 1886)]
