"""wordcount.py - count lines, words and characters in a text file.

usage: python wordcount.py [-l] [-w] [-c] FILE
  -l  print only the line count
  -w  print only the word count
  -c  print only the character count
With no flag, prints all three: lines words chars.
"""
import sys

flags = [a for a in sys.argv[1:] if a.startswith("-")]
path = [a for a in sys.argv[1:] if not a.startswith("-")][0]
text = open(path, encoding="utf-8").read()
counts = {"-l": text.count("\n"), "-w": len(text.split()), "-c": len(text)}
print(" ".join(str(counts[f]) for f in (flags or ["-l", "-w", "-c"])))
