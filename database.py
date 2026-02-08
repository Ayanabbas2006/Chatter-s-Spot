import mysql.connector
from argon2 import PasswordHasher
def get_db():
    return mysql.connector.connect(
        user='chatter_user',
        host='localhost',
        password='MyPassword@256',
        database='Chatter',
        charset="utf8mb4",
        collation="utf8mb4_unicode_ci"
    )
