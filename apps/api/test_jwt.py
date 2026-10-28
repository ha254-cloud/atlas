from app.security.jwt import (
    create_access_token,
    decode_access_token,
)

token = create_access_token("1")

print("TOKEN:")
print(token)

print()

payload = decode_access_token(token)

print(payload)
