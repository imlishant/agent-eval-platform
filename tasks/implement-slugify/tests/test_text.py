import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from text import slugify

def test_examples():
    assert slugify("Hello, World!") == "hello-world"
    assert slugify("  Multiple   spaces  ") == "multiple-spaces"
    assert slugify("Already-a-slug") == "already-a-slug"
    assert slugify("a__b..c") == "a-b-c"
    assert slugify("--Edge--") == "edge"
    assert slugify("Version 2.0 Release") == "version-2-0-release"
