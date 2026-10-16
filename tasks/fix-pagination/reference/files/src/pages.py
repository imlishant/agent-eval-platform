def paginate(items, page, size):
    """Return the items on `page` (pages start at 1), `size` items per page."""
    start = (page - 1) * size
    return items[start:start + size]
