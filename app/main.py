from datetime import datetime
from fastapi import FastAPI, Depends, responses
import requests
import os
import json
import sys
from .routers import twitter, bsky, debug
from .vars import get_notion_envs

app = FastAPI()
app.include_router(twitter.router)
app.include_router(bsky.router)
app.include_router(debug.router)

@app.get("/")
async def root():
    NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_VERSION = get_notion_envs()
    url = f'https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query'
    r = requests.post(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
        })
    result_dict = r.json()
    return responses.JSONResponse([{item["properties"]["Title"]["title"][0]["plain_text"]: item["id"]} for item in result_dict["results"] if item["properties"]["Status"]["status"]["name"] != "Published"])
    
