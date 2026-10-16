import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from pages import paginate

def test_pages():
    items = [1, 2, 3, 4, 5]
    assert paginate(items, 1, 2) == [1, 2]
    assert paginate(items, 2, 2) == [3, 4]
    assert paginate(items, 3, 2) == [5]
    assert paginate(items, 4, 2) == []
