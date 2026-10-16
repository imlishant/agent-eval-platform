def slugify(text: str) -> str:
    """Turn text into a URL slug.

    - lowercase everything
    - every run of characters that are not a-z or 0-9 becomes a single "-"
    - no "-" at the start or end
    Example: "Hello, World!" -> "hello-world"
    """
    raise NotImplementedError
