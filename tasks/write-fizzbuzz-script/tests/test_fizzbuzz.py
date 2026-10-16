import subprocess, sys

def expected(n):
    out = []
    for i in range(1, n + 1):
        out.append("FizzBuzz" if i % 15 == 0 else "Fizz" if i % 3 == 0 else "Buzz" if i % 5 == 0 else str(i))
    return out

def test_fizzbuzz():
    for n in (1, 15, 31):
        r = subprocess.run([sys.executable, "fizzbuzz.py", str(n)], capture_output=True, text=True, timeout=10)
        assert r.stdout.split() == expected(n)
