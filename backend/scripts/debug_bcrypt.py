import bcrypt
import sys
sys.path.insert(0, ".")

print(f"bcrypt version: {bcrypt.__version__}")

# Test basic bcrypt
b = "TestPass".encode()
h = bcrypt.hashpw(b, bcrypt.gensalt())
print(f"Hash generated: {h}")
print(f"Correct check: {bcrypt.checkpw(b, h)}")
print(f"Wrong password: {bcrypt.checkpw(b'wrong', h)}")

# Test with the hardcoded dummy hash from auth.py
dummy_hash = "$2b$12$LJ3m4ys3Lg3lE9Q8pBkSp.ZxOXSCmRCVHaLCQ5FhCjXxVx5m5sZ6C"
try:
    result = bcrypt.checkpw("dummy_password".encode(), dummy_hash.encode())
    print(f"Dummy hash check: {result}")
except Exception as e:
    print(f"Dummy hash ERROR: {type(e).__name__}: {e}")

# Test with the actual verify_password function
from app.core.security import verify_password, get_password_hash

# Test verify_password with a freshly hashed password
fresh_hash = get_password_hash("CorrectPass!99")
print(f"\nFresh hash: {fresh_hash[:20]}...")
try:
    r1 = verify_password("CorrectPass!99", fresh_hash)
    print(f"verify_password correct: {r1}")
    r2 = verify_password("WrongPass!99", fresh_hash)
    print(f"verify_password wrong: {r2}")
except Exception as e:
    print(f"verify_password ERROR: {type(e).__name__}: {e}")
