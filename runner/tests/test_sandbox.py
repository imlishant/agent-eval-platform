from evalrunner.sandbox import trial_dirs
from evalrunner.schema import Task
from test_pipeline import TASK


def test_each_trial_gets_fresh_dirs_and_cleans_up():
    task = Task.load(TASK)
    with trial_dirs(task) as (sb1, home1):
        (sb1 / "leak.txt").write_text("x")
        (home1 / "memory.md").write_text("x")
        assert (sb1 / "data.csv").exists()          # fixtures copied
    with trial_dirs(task) as (sb2, home2):
        assert sb2 != sb1
        assert not (sb2 / "leak.txt").exists()       # nothing leaks
        assert not (home2 / "memory.md").exists()
    assert not sb1.exists()                          # cleaned up
