from datetime import datetime
import fastapi
from models import Status, Tweet, TweetThread
import requests
import uuid 

NOTION_TOKEN="secret_fv2dLcfGzqYNKXmXsRIaXaDw0KWOkn1FilunNVo1C4Y"
# old database
#NOTION_DATABASE_ID="b38f425a0f7c4f23ac6c821f7a5b6075"

# thread database
#NOTION_DATABASE_ID="b4f76b8a213d42eb8366bc759e3e1cfd"
NOTION_DATABASE_ID="c57dc46a884c49bf97bdb333b4d117a8"
NOTION_VERSION = "2022-06-28"

app = fastapi.FastAPI()

@app.get("/")
async def root():
    url = f'https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query'
    r = requests.post(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
        })
    result_dict = r.json()
    return result_dict
    #return [item["properties"] for item in result_dict["results"]]
    
@app.get("/schedule")
async def root():
    url = f'https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query'
    r = requests.post(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
        })
    result_dict = r.json()
    
    only_scheduled_tweets = [
        {
            "url": item["url"],
            "page_id": item["id"],
            "tweet": item["properties"]["tweet"]["title"][0]["text"]["content"], 
            "publish_time": item["properties"]["publish_time"]["date"]["start"], 
            "time_zone": item["properties"]["publish_time"]["date"]["time_zone"],
            "status": item["properties"]["status"]["select"]["name"]}
        for item in result_dict["results"]
        if item["properties"]["publish_time"]["date"]["start"] is not None ]
    
    only_non_published = [item for item in only_scheduled_tweets if item["status"] != "Published"]
    only_future_tweets = [tweet for tweet in only_scheduled_tweets if datetime.fromisoformat(tweet["publish_time"]).date() >= datetime.today().date()]
    
    # sort the results by the publish time (ascending)
    return sorted(only_future_tweets, key=lambda x: x['publish_time'])

@app.get("/add")
async def root():
    url = f'https://api.notion.com/v1/pages/'
    r = requests.post(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": f"{NOTION_VERSION}",
        
        }, 
        json={
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "id": {
                    "title": [{
                        "text": {
                            "content": str(uuid.uuid4())
                        }
                    }]
                },
        "scheduled_datetime": {
            "date": {
                "start": "2024-11-05T12:00:00Z"
            }
        },
        
        "status": {
        "status": {
            "name": "Done"
        }
        },
        
        "platform": {
            "select": {
                "name": "pinterest"
            }
        },
    
        "content-text": {
            "rich_text": [{
                "text": {
                    "content": "Tuscan Kale"
                }
            }]
        },
    }
        }

        ) 
    return r.json
    
