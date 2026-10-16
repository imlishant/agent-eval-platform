from users import get_usr


def greeting(user_id):
    name = get_usr(user_id)
    return f"Hello, {name}!" if name else "Hello, stranger!"
