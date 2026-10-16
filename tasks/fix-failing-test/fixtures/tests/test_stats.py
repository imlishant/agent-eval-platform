import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stats import mean, median

def test_mean():
    assert mean([2, 4, 6]) == 4
    assert mean([5]) == 5

def test_median():
    assert median([3, 1, 2]) == 2
    assert median([4, 1, 3, 2]) == 2.5
