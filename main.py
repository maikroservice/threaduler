from datetime import datetime
import fastapi
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

class TooLongException(Exception):
    "Raised when the tweet character count is >280"
    pass

@app.get("/")
async def root():
    url = f'https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query'
    r = requests.post(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
        })
    result_dict = r.json()
    return [(item["id"], item["properties"]["Title"]["title"][0]["plain_text"]) for item in result_dict["results"] if item["properties"]["Status"]["status"]["name"] != "Published"] 
    

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
    
    only_non_published = [item for item in only_scheduled_tweets if item["status"] == "Ready"]
    # TODO this should just be a comparison of unix timestamps and take care of the time as well? 
    only_future_tweets = [tweet for tweet in only_non_published if datetime.fromisoformat(tweet["publish_time"]).date() >= datetime.today().date()]
    
    # sort the results by the publish time (ascending)
    return sorted(only_future_tweets, key=lambda x: x['publish_time'])


@app.get("/debug/{page_id}")
async def transform_notion_to_tweets(page_id):
        url = f'https://api.notion.com/v1/blocks/{page_id}/children'
        r = requests.get(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": f"{NOTION_VERSION}",
        
        })
        return r.json()["results"]


def notion_blocks_to_tweet_chunks(blocks):
    # split notion page content by divider and return a list of raw chunks
    chunks = {}
    counter = 0
    for block in blocks:
        if block["type"] == "divider":
            counter += 1
        else:
            try:
                chunks[counter].append(block)
            except KeyError:
                chunks[counter] = []
                chunks[counter].append(block)

    return chunks


@app.get("/tweets/{page_id}")
async def transform_notion_to_tweets(page_id):
        url = f'https://api.notion.com/v1/blocks/{page_id}/children'
        r = requests.get(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": f"{NOTION_VERSION}",
        
        })
        blocks = r.json()["results"]
        # we separate the blocks by divider and group them together in raw pretweet format
        chunks = notion_blocks_to_tweet_chunks(blocks)

        tweets = []
        
        
        for i in range(0,len(chunks)):
            tweet = {}
            tweet["tweet"] = r""
            tweet["media"] = []
            # TODO: parse bullet list blocks / numbered list blocks correctly
            
            # find paragraph blocks and publish
            paragraph_blocks = [block["paragraph"]["rich_text"] for block in chunks[i] if block["type"] == "paragraph"]
            for block in paragraph_blocks:
                if block:
                    tweet["tweet"] += f"{block[0]['plain_text'].rstrip()}\n"
                else:
                    tweet["tweet"] += "\n\n"
            
            media_blocks = [block["image"] for block in chunks[i] if block["type"] == "image"]
            for i, block in enumerate(media_blocks):
                if block:
                    tweet["media"].append({"fileUrl": block["file"]["url"]})
            
            try:
                tweet["char_count"] = len(tweet["tweet"])
                if tweet["char_count"] > 280:
                    raise TooLongException() 
            except TooLongException:
                print(f'TOO LONG: {tweet["tweet"]}')
            
            tweets.append(tweet)

        return tweets


@app.get("/publish/{page_id}")
async def publish_tweets(page_id):
    # setup twitter auth
    CONSUMER_KEY = os.environ["TWITTER_CONSUMER_KEY"]
    CONSUMER_SECRET = os.environ["TWITTER_CONSUMER_SECRET"]
    ACCESS_TOKEN = os.environ["TWITTER_ACCESS_TOKEN"]
    ACCESS_TOKEN_SECRET = os.environ["TWITTER_TOKEN_SECRET"]

    # the client posts our tweets
    client = tweepy.Client(
    consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET
    )

    # we need the api connection to upload images
    auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)

    tweets = await transform_notion_to_tweets(page_id)
    thread = []
    
    for i, item in enumerate(tweets):
        
        media = []
        
        for image in item["media"]:
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

        if len(tweets) <= 1:
            if not media:
                response = client.create_tweet(text=item["tweet"])
                return f"https://twitter.com/user/status/{response.data['id']}"
            else:
                response = client.create_tweet(text=item["tweet"], media_ids=[medium.media_id for medium in media])
                return f"https://twitter.com/user/status/{response.data['id']}"
        
        elif(i==0):
            # this is the first tweet
            if not media:
                response = client.create_tweet(text=item["tweet"])
                thread.append(response.data['id'])
                continue
            else:
                response = client.create_tweet(text=item["tweet"], media_ids=[medium.media_id for medium in media])
                thread.append(response.data['id'])
                continue
        
        else:
            # this is a thread and we need to reply to the previous tweet
            if not media:
                response = client.create_tweet(text=item["tweet"], in_reply_to_tweet_id=thread[-1])
                thread.append(response.data['id'])
                continue
            else:
                response = client.create_tweet(text=item["tweet"], in_reply_to_tweet_id=thread[-1], media_ids=[medium.media_id for medium in media])
                thread.append(response.data['id'])
                continue

        
    return [f"https://twitter.com/user/status/{tweet}" for tweet in thread]


@app.get("/update/{page_id}")
# write data to notion?/database / sync current likes/retweets etc 
# update URL property + Status Property after publishing
async def update_notion_db(page_id, tweet_url):
    url = f'https://api.notion.com/v1/pages/{page_id}'
    r = requests.patch(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": f"{NOTION_VERSION}",
        },
        json={
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "Status": {
                    "status": {
                        "name": "Published"
                    }
                },
                "URL": {
                    "url": tweet_url
                }
            }
        }
    )

    return r.json