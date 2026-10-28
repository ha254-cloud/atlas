from app.security.hashing import (
    hash_password,
    verify_password,
)

password = "Atlas123!"

hashed = hash_password(password)

print("Password:", password)
print("Hash:", hashed)
print("Verified:", verify_password(password, hashed))
