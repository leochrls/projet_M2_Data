import os
from pymongo import MongoClient
from fastapi import FastAPI
from fastapi.responses import JSONResponse

app = FastAPI()

MONGO_USER = os.getenv("MONGO_USER")
MONGO_PASS = os.getenv("MONGO_PASS")
MONGO_HOST = os.getenv("MONGO_HOST")
MONGO_PORT = os.getenv("MONGO_PORT")
MONGO_DB = os.getenv("MONGO_DB")
MONGO_COLLECTION = os.getenv("MONGO_COLLECTION")

uri = f"mongodb://{MONGO_USER}:{MONGO_PASS}@{MONGO_HOST}:{MONGO_PORT}"
client = MongoClient(uri)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]

@app.get("/query")
async def get_data():
    data = list(collection.find({}, {"_id": 0}))
    return JSONResponse(content=data)