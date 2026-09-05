import hashlib
import string

# Base62 is chosen (0-9, a-z, A-Z) over Base64 to avoid URL-unsafe characters
# and to keep the short codes compact.
BASE62_ALPHABET = string.digits + string.ascii_lowercase + string.ascii_uppercase
BASE = len(BASE62_ALPHABET)


# This performs repeated division by 62 to compress large numbers into compact
# text representations.
def encode_base62(num: int) -> str:
    if not isinstance(num, int):
        raise TypeError("Input must be an integer.")
    if num < 0:
        raise ValueError("Cannot encode negative integers.")
    if num == 0:
        return BASE62_ALPHABET[0]

    chars = []
    current = num
    while current > 0:
        remainder = current % BASE
        chars.append(BASE62_ALPHABET[remainder])
        current //= BASE

    return "".join(reversed(chars))


def decode_base62(token: str) -> int:
    if not isinstance(token, str):
        raise TypeError("Input must be a string.")
    if not token:
        raise ValueError("Token cannot be empty.")

    num = 0
    for char in token:
        idx = BASE62_ALPHABET.find(char)
        if idx == -1:
            raise ValueError(f"Invalid Base62 character: {char}")
        num = num * BASE + idx

    return num


# Adding a salt counter to the hash input allows for multiple attempts to
# generate an entirely different hash output for the same URL, if a collision
# occurs.
def generate_short_code(url: str, salt: str = "", length: int = 7) -> str:
    if not isinstance(url, str) or not url.strip():
        raise ValueError("URL must be a non-empty string.")

    payload = (url + salt).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    hex_slice = digest[:12]
    numeric_val = int(hex_slice, 16)
    encoded = encode_base62(numeric_val)

    return encoded[:length].rjust(length, BASE62_ALPHABET[0])


if __name__ == "__main__":
    test_id = 125388
    encoded = encode_base62(test_id)
    decoded = decode_base62(encoded)
    assert test_id == decoded

    url = "https://example.com/very/long/path"
    code1 = generate_short_code(url)
    code2 = generate_short_code(url)
    assert code1 == code2

    salted = generate_short_code(url, salt="1")
    assert code1 != salted

    print("Step 2 tests passed cleanly.")
