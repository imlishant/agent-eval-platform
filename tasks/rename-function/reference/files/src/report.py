from users import get_user


def greeting(user_id):
    name = get_user(user_id)
    return f"Hello, {name}!" if name else "Hello, stranger!"
