import asyncio
from app.database import get_user_collection

def run():
    col = get_user_collection()
    if col is None:
        print("Database not connected")
        return
    users = list(col.find({}, {"password": 0}))
    print("USERS IN DATABASE:")
    for u in users:
        print(u)

if __name__ == "__main__":
    run()
