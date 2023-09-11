import os
import sys
import requests
import tweepy
import tempfile
from fastapi import APIRouter 
from ..vars import get_notion_envs, get_twitter_envs
from ..dependencies import notion_blocks_to_post_chunks, PostTooLongException, TweetNoQuoteAndMediaException
from .debug import update_notion_metadata


NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_API_VERSION = get_notion_envs()
CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET = get_twitter_envs()


router = APIRouter(
    prefix="/twitter",
    tags=["twitter"],
)

def authenticate_twitter():
    # the client posts our tweets
    client = tweepy.Client(
    consumer_key=CONSUMER_KEY, consumer_secret=CONSUMER_SECRET,
    access_token=ACCESS_TOKEN, access_token_secret=ACCESS_TOKEN_SECRET
    )

    # we need the api connection to upload images
    auth = tweepy.OAuth1UserHandler(CONSUMER_KEY, CONSUMER_SECRET, ACCESS_TOKEN, ACCESS_TOKEN_SECRET)
    api = tweepy.API(auth)

    return client, api


@router.get("/{page_id}")
async def transform_notion_to_posts(page_id, post_length=280):
        url = f'https://api.notion.com/v1/blocks/{page_id}/children'
        headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_API_VERSION,
        }
        r = requests.get(url, headers=headers)
        print(r.status_code)
        
        data = r.json()
        blocks = data["results"]

        
        while data.get('has_more', False):
            # we are limited to 100 blocks per notion api request, if has_more is present, 
            # there is more data and we need to request again with the
            # correct cursor present
            next_cursor = data['next_cursor']

            response = requests.get(f"{url}?start_cursor={next_cursor}", headers=headers)
            data = response.json()
            blocks += data["results"]
        
        # we separate the blocks by divider and group them together in raw pretweet format
        chunks = notion_blocks_to_post_chunks(blocks)

        posts = []
        for i in range(0,len(chunks)):
            post = {}
            post["tweet"] = r""
            post["media"] = []
            post["quote"] = ""
            # TODO: parse bullet list blocks / numbered list blocks correctly
            
            # find paragraph blocks and publish
            paragraph_blocks = [block["paragraph"]["rich_text"] for block in chunks[i] if block["type"] == "paragraph"]
            for block in paragraph_blocks:
                if block:
                     # if our block starts with {{ it is a quote_tweet
                    #if block[0]['plain_text'].strip().startswith("{{"):
                        # if it contains the word "FIRST_POST" then it should quote the first tweet
                        #if block[0]['plain_text'].strip().startswith("{{FIRST_"):
                        #    post["quote"] = posts[0].split("/")[-1][:-2]
                        #else:
                            # otherwise we take the id from the url provided between the {{}}
                        #    post["quote"] = block[0]['plain_text'].split("/")[-1][:-2]
                            
                    #else:
                        post["tweet"] += f"{block[0]['plain_text'].rstrip()}\n"
                else:
                    post["tweet"] += "\n\n"
            
            media_blocks = [block["image"] for block in chunks[i] if block["type"] == "image"]
            for block in media_blocks:
                if block:
                    try:
                        post["media"].append({"fileUrl": block["file"]["url"]})
                    except KeyError:
                        post["media"].append({"fileUrl": block["external"]["url"]})
            
            try:
                post["char_count"] = len(post["tweet"])
                if post["char_count"] > post_length:
                    raise PostTooLongException() 
            except PostTooLongException:
                print(f'TOO LONG: {post["tweet"]}')
            
            try:
                if post["media"] and post["quote"]:
                # since media and quote tweets are mutually exclusive we need to stop here
                    raise TweetNoQuoteAndMediaException()
            except TweetNoQuoteAndMediaException:
                print(f"Quote Tweets cannot contain media - {post['tweet']}")

            posts.append(post)

        return posts

@router.get("/publish/{page_id}")
async def publish_tweets(page_id):
    # import tempfile so that we can create temporary files
    client, api = authenticate_twitter()
    

    raw_tweets = await transform_notion_to_posts(page_id)
    tweets = []
    
    # loop through all the tweets and add corresponding images/video to it
    for i, item in enumerate(raw_tweets):
        
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
                    media_file = api.simple_upload(filename=temp_file_path)
                    media.append(media_file)


        if(i==0):
            # this is the first tweet
            if item["quote"] and not media:
                response = client.create_tweet(text=item["tweet"], quote_tweet_id=item["quote"])
            elif not item["quote"] and not media:
                response = client.create_tweet(text=item["tweet"])
                
            else:
                response = client.create_tweet(text=item["tweet"], media_ids=[medium.media_id for medium in media])
                
        
        else:
            # this is a thread and we need to reply to the previous tweet
            if item["quote"] and not media:
                response = client.create_tweet(text=item["tweet"], in_reply_to_tweet_id=tweets[-1], quote_tweet_id=item["quote"])
            elif not item["quote"] and not media:
                response = client.create_tweet(text=item["tweet"], in_reply_to_tweet_id=tweets[-1])
            else:
                response = client.create_tweet(text=item["tweet"], in_reply_to_tweet_id=tweets[-1], media_ids=[medium.media_id for medium in media])
        
        tweets.append(response.data['id'])


    posted_tweets = [f"https://twitter.com/user/status/{tweet_id}" for tweet_id in tweets]
    tweet_url = posted_tweets[0]
    update_notion_properties = update_notion_metadata(page_id, "twitter", tweet_url)

    return (tweet_url, update_notion_properties)