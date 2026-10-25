"""Hash e verificacao de senhas (argon2id)."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

MIN_PASSWORD_LENGTH = 10

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"a senha precisa ter pelo menos {MIN_PASSWORD_LENGTH} caracteres")
    return _hasher.hash(password)


# Hash valido de uma senha descartada: usado para gastar o mesmo tempo quando o usuario nao existe.
DUMMY_HASH = _hasher.hash("senha-descartavel-so-para-igualar-o-tempo")


def verify_password(password_hash: str, password: str) -> bool:
    """Nunca levanta: hash invalido ou senha errada devolvem False."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False
