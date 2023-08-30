import os
from dotenv.main import load_dotenv

load_dotenv()

def get_notion_envs():
    # setup notion   
    NOTION_TOKEN=os.environ["NOTION_API_TOKEN"]
    NOTION_DATABASE_ID=os.environ["NOTION_DATABASE_ID"]
    NOTION_API_VERSION = os.environ["NOTION_API_VERSION"]
    return NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_API_VERSION


def get_twitter_envs():
    # setup twitter auth
    CONSUMER_KEY = os.environ["TWITTER_CONSUMER_KEY"]
    CONSUMER_SECRET = os.environ["TWITTER_CONSUMER_SECRET"]
    ACCESS_TOKEN = os.environ["TWITTER_ACCESS_TOKEN"]
    ACCESS_TOKEN_SECRET = os.environ["TWITTER_TOKEN_SECRET"]
    return CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET

# setup bsky 
def get_bsky_envs():
    BSKY_USERNAME = os.environ["BSKY_USERNAME"]
    BSKY_PASS = os.environ["BSKY_PASSWORD"]
    BSKY_BASEURL = os.environ["BSKY_BASEURL"]
    return BSKY_USERNAME, BSKY_PASS, BSKY_BASEURL