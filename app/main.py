from datetime import datetime
from fastapi import FastAPI, responses
import requests
from .routers import twitter, bsky, debug, linkedin
from .vars import get_notion_envs

app = FastAPI()
app.include_router(twitter.router)
app.include_router(bsky.router)
app.include_router(debug.router)
app.include_router(linkedin.router)

@app.get("/")
async def root(status="Idea"):
    NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_API_VERSION = get_notion_envs()
    url = f'https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query'
    r = requests.post(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_API_VERSION
        })
    result_dict = r.json()
    return responses.JSONResponse([{item["properties"]["Title"]["title"][0]["plain_text"]: item["id"]} for item in result_dict["results"] if item["properties"]["Status"]["status"]["name"] == status])
    
