# wordcount

Counts lines, words and characters in a text file.

## Usage

    python wordcount.py [-l] [-w] [-c] FILE

- `-l` prints only the line count
- `-w` prints only the word count
- `-c` prints only the character count

With no flag it prints all three: `lines words chars`.

Example: `python wordcount.py -w notes.txt` prints the number of words in notes.txt.
