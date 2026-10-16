import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from users import get_user
from report import greeting

def test_renamed():
    assert get_user(1) == "ana"
    assert greeting(2) == "Hello, bo!"
    assert greeting(9) == "Hello, stranger!"
