from datetime import datetime
import fastapi
from models import Status, Tweet, TweetThread
import requests
import uuid 
import tweepy
import tempfile
from dotenv.main import load_dotenv
import os
import uuid 

load_dotenv()


NOTION_TOKEN=os.environ["NOTION_API_TOKEN"]

NOTION_DATABASE_ID=os.environ["NOTION_DATABASE_ID"]
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
    #return result_dict
    return [item["properties"] for item in result_dict["results"]]
    
@app.get("/schedule")
async def schedule():
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
            "tweet": item["properties"]["Title"]["title"][0]["text"]["content"], 
            "publish_time": item["properties"]["publish_time"]["date"]["start"], 
            "time_zone": item["properties"]["publish_time"]["date"]["time_zone"],
            "status": item["properties"]["Status"]["status"]["name"]}
        for item in result_dict["results"]
            if item["properties"]["publish_time"]["date"] is not None]
    
    only_non_published = [item for item in only_scheduled_tweets if item["status"] != "Published"]
    only_future_tweets = [tweet for tweet in only_non_published if datetime.fromisoformat(tweet["publish_time"]).date() >= datetime.today().date()]
    
    # sort the results by the publish time (ascending)
    return sorted(only_future_tweets, key=lambda x: x['publish_time'])


@app.get("/tweets/{page_id}")
async def transform_notion_to_tweet(page_id):
        url = f'https://api.notion.com/v1/blocks/{page_id}/children'
        r = requests.get(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": f"{NOTION_VERSION}",
        
        })
        blocks = r.json()["results"]
        
        tweet = {}
        
        tweet["tweet"] = ''
        tweet["media"] = []
        

        
        paragraph_blocks = [block["paragraph"]["rich_text"] for block in blocks if block["type"] == "paragraph"]
        for block in paragraph_blocks:
            if block:
                tweet["tweet"] += f"{block[0]['plain_text'].rstrip()}\n"
            else:
                tweet["tweet"] += "\n\n"
        
        media_blocks = [block["image"] for block in blocks if block["type"] == "image"]
        for i, block in enumerate(media_blocks):
            if block:
                tweet["media"].append({"fileUrl": block["file"]["url"], "mimeType": "image/png"})
                

        return tweet

@app.get("/publish/{page_id}")
async def publish_tweet(page_id):
    content = await transform_notion_to_tweet(page_id)

    CONSUMER_KEY = os.environ["TWITTER_CONSUMER_KEY"]
    CONSUMER_SECRET = os.environ["TWITTER_CONSUMER_SECRET"]
    ACCESS_TOKEN = os.environ["TWITTER_ACCESS_TOKEN"]
    ACCESS_TOKEN_SECRET = os.environ["TWITTER_TOKEN_SECRET"]

    client = tweepy.Client(
    consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET
    )
    auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)

    media = []
    for image in content["media"]:
        if image:

            
            with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp_file:
            
                import shutil
                response = requests.get(image["fileUrl"], stream=True)
                # Write data to the temporary file    
                shutil.copyfileobj(response.raw, temp_file)
                del response
                
                # Get the path of the temporary file
                temp_file_path = temp_file.name
                img = api.simple_upload(filename=temp_file_path)
                media.append(img)


    if not media:
        response = client.create_tweet(text=content["tweet"])
    else:
        print(media)
        response = client.create_tweet(text=content["tweet"], media_ids=[medium.media_id for medium in media])
    print(f"https://twitter.com/user/status/{response.data['id']}")



@app.get("/update")
# write data to notion?/database / sync current likes/retweets etc 
async def update_notion_db():
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
    
