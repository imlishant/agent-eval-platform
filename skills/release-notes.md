# House format for release notes (RELEASE_NOTES.md files)

Release notes in this company use this exact format, nothing else:

    >>> RELEASE v<version> | <YYYY-MM-DD>
    [ADD] <one line per new feature>
    [FIX] <one line per bug fix>
    <<< END

Rules:
- The header line starts with `>>> RELEASE v`, then the version, then ` | ` and the date.
- Every change is one line starting with `[ADD]` or `[FIX]` (uppercase, in square brackets).
- List all [ADD] lines before [FIX] lines.
- The block ends with the line `<<< END`.
- No markdown headings, no bullets.
