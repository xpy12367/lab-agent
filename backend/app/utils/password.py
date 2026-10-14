import bcrypt


def hash_password(password: str) -> str:
    """对密码加密"""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    # password.encode("utf-8")：把 Python 字符串转成字节，因为 bcrypt 的哈希函数接收字节，而不是字符串。
    # bcrypt.gensalt()：生成一个随机的盐值，用于增加密码的复杂度。
    # bcrypt.hashpw()：对密码进行哈希处理，返回一个字节串。
    # decode("utf-8")：把字节串转成字符串，方便存储和比较。


def verify_password(password: str, hashed_password: str) -> bool:
    """验证密码的有效性"""
    """  "123" -> "xxsdasdasdasfa"  """
    return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
    # password.encode("utf-8")：把 Python 字符串转成字节，因为 bcrypt 的哈希函数接收字节，而不是字符串。
    # bcrypt.checkpw()：检查密码是否匹配哈希后的密码。
    # 返回值是一个布尔值，表示密码是否匹配。
