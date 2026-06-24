import bcrypt
import re


def hash_password(password: str):
    pwd_bytes = password.encode('utf-8')[:72]
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode('utf-8')[:72]
    hashed_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hashed_bytes)


def normalize_phone_number(phone: str, default_country_code: str = "+91") -> str:
    cleaned = re.sub(r'[\s\-\(\)\.\+]', '', phone)
    # Re-detect leading + which was stripped above
    has_plus = phone.strip().startswith('+')
    if has_plus:
        return '+' + cleaned
    if cleaned.startswith('91') and len(cleaned) > 10:
        return '+' + cleaned
    return default_country_code + cleaned
