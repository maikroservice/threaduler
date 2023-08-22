import requests
import os


def async upload_file(pds_url="https://bsky.social", access_token, filename, img_bytes) -> Dict:
    suffix = filename.split(".")[-1].lower()
    mimetype = "application/octet-stream"
    if suffix in ["png"]:
        mimetype = "image/png"
    elif suffix in ["jpeg", "jpg"]:
        mimetype = "image/jpeg"
    elif suffix in ["webp"]:
        mimetype = "image/webp"

    #TODO: figure out if notion removes EXIF data by default 

    resp = requests.post(
        pds_url + "/xrpc/com.atproto.repo.uploadBlob",
        headers={
            "Content-Type": mimetype,
            "Authorization": "Bearer " + access_token,
        },
        data=img_bytes,
    )
    resp.raise_for_status()
    return await {
        "$type": "app.bsky.embed.images",
        "image":resp.json()["blob"]
    }

@app.get("/publish_bksy/{page_id}")
async def publish_bsky(page_id):
    # setup twitter auth
    BSKY_USERNAME = os.environ["BSKY_USERNAME"]
    BSKY_PASS = os.environ["BSKY_PASSWORD"]
    BSKY_SESSION_URL = 'https://bsky.social/xrpc/com.atproto.server.createSession'
    r = requests.post(BSKY_SESSION_URL, json={"identifier": BSKY_USERNAME, "password": BSKY_PASS})
    r.raise_for_status()
    session = r.json()
    access_token = session.accessJwt

    
    raw_posts = await transform_notion_to_posts(page_id)
    posts = []
    
    # loop through all the tweets and add corresponding images/video to it
    for i, item in enumerate(raw_posts):
        
        media = []
        for image in item["media"]:
            if image:
                with tempfile.NamedTemporaryFile(mode='wb') as temp_file:
                
                    import shutil
                    # we first need to download the image from the s3 bucket that notion places them in
                    response = requests.get(image["fileUrl"], stream=True)
                    # Write data to the temporary file
                    # we do it this way because we need to figure out the file mime type and shutil does that for us
                    # + the raw response needs to be stored and this was the easiest solution stackoverflow had 😅
                    shutil.copyfileobj(response.raw, temp_file)
                    del response
                    
                    # Get the path of the temporary file
                    temp_file_path = temp_file.name

                    # this size limit specified in the app.bsky.embed.images lexicon
                    if len(temp_file) > 1000000:
                        raise Exception(
                            f"image file size too large. 1000000 bytes maximum, got: {len(temp_file)}"
                        )
                    # upload the medium to bsky
                    img = upload_file(access_token=access_token, filename=temp_file_path, temp_file)
                    media.append(img)

        if len(tweets) <= 1:
            # there is only a single post
            if not media:
                # if no media we can directly post it
                response = client.create_tweet(text=item["tweet"], quote_tweet_id=item["quote"])
                tweets.append(response.data['id'])
                break

                
            else:
                response = client.create_tweet(text=item["tweet"], media_ids=[medium.media_id for medium in media])
                tweets.append(response.data['id'])
                break
        
        elif(i==0):
            # this is the first tweet of many
            if not media:
                response = client.create_tweet(text=item["tweet"], quote_tweet_id=item["quote"])
                tweets.append(response.data['id'])
                continue
            else:
                response = client.create_tweet(text=item["tweet"], media_ids=[medium.media_id for medium in media])
                tweets.append(response.data['id'])
                continue
        
        else:
            # this is a thread and we need to reply to the previous tweet
            if not media:
                response = client.create_tweet(text=item["tweet"], in_reply_to_tweet_id=tweets[-1], quote_tweet_id=item["quote"])
                tweets.append(response.data['id'])
                continue
            else:
                response = client.create_tweet(text=item["tweet"], in_reply_to_tweet_id=tweets[-1], media_ids=[medium.media_id for medium in media])
                tweets.append(response.data['id'])
                continue

    posted_tweets = [f"https://twitter.com/user/status/{tweet_id}" for tweet_id in tweets]
    tweet_url = posted_tweets[0]
    update_notion_properties = await update_notion_db(page_id, tweet_url)

    return (tweet_url, update_notion_properties)