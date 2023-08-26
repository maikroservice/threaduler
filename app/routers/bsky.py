import requests
import os
from fastapi import APIRouter, Depends
from typing import Dict, List
from ..vars import get_notion_envs, get_bsky_envs
from ..dependencies import notion_blocks_to_post_chunks, PostTooLongException
from .debug import update_notion_metadata
from datetime import datetime, timezone
import sys 
import json
import re

NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_VERSION = get_notion_envs()
BSKY_USERNAME, BSKY_PASS = get_bsky_envs()

router = APIRouter(
    prefix="/bsky",
    tags=["bsky"],
    responses={404: {"description": "Not found"}},
)
# bsky functions from: https://github.com/bluesky-social/atproto-website/blob/main/examples/create_bsky_post.py
async def upload_file(access_token, filename, img_bytes, base_url="https://bsky.social") -> Dict:
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
        base_url + "/xrpc/com.atproto.repo.uploadBlob",
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


def parse_mentions(text: str) -> List[Dict]:
    spans = []
    # regex based on: https://atproto.com/specs/handle#handle-identifier-syntax
    mention_regex = rb"[$|\W](@([a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+[a-zA-Z]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)"
    text_bytes = text.encode("UTF-8")
    for m in re.finditer(mention_regex, text_bytes):
        spans.append(
            {
                "start": m.start(1),
                "end": m.end(1),
                "handle": m.group(1)[1:].decode("UTF-8"),
            }
        )
    return spans

def parse_urls(text: str) -> List[Dict]:
    spans = []
    # partial/naive URL regex based on: https://stackoverflow.com/a/3809435
    # tweaked to disallow some training punctuation
    url_regex = rb"[$|\W](https?:\/\/(www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_\+.~#?&//=]*[-a-zA-Z0-9@%_\+~#//=])?)"
    text_bytes = text.encode("UTF-8")
    for m in re.finditer(url_regex, text_bytes):
        spans.append(
            {
                "start": m.start(1),
                "end": m.end(1),
                "url": m.group(1).decode("UTF-8"),
            }
        )
    return spans

async def parse_facets(text: str, base_url: str="https://bsky.social") -> List[Dict]:
    """
    parses post text and returns a list of app.bsky.richtext.facet objects for any mentions (@handle.example.com) or URLs (https://example.com)

    indexing must work with UTF-8 encoded bytestring offsets, not regular unicode string offsets, to match Bluesky API expectations
    """
    facets = []
    mentions = parse_mentions(text)
    
    for m in mentions:
        resp = requests.get(
            base_url + "/xrpc/com.atproto.identity.resolveHandle",
            params={"handle": m["handle"]},
        )
        # if handle couldn't be resolved, just skip it! will be text in the post
        if resp.status_code == 400:
            continue
        did = resp.json()["did"]
        facets.append(
            {
                "index": {
                    "byteStart": m["start"],
                    "byteEnd": m["end"],
                },
                "features": [{"$type": "app.bsky.richtext.facet#mention", "did": did}],
            }
        )
    urls = parse_urls(text)
    for u in urls:
        print("check")
        facets.append(
            {
                "index": {
                    "byteStart": u["start"],
                    "byteEnd": u["end"],
                },
                "features": [
                    {
                        "$type": "app.bsky.richtext.facet#link",
                        # NOTE: URI ("I") not URL ("L")
                        "uri": u["url"],
                    }
                ],
            }
        )
    return facets

async def get_embed_ref(ref_uri: str, base_url: str="https://bsky.social") -> Dict:
    uri_parts = parse_urls(ref_uri)
    resp = requests.get(
        base_url + "/xrpc/com.atproto.repo.getRecord",
        params=uri_parts,
    )
    print(resp.json())
    resp.raise_for_status()
    record = resp.json()

    return {
        "$type": "app.bsky.embed.record",
        "record": {
            "uri": record["uri"],
            "cid": record["cid"],
        },
    }

async def get_reply_refs(parent_uri: str, base_url: str="https://bsky.social") -> Dict:
    uri_parts = parse_urls(parent_uri)
    resp = requests.get(
        base_url + "/xrpc/com.atproto.repo.getRecord",
        params=uri_parts,
    )
    resp.raise_for_status()
    parent = resp.json()
    root = parent
    parent_reply = parent["value"].get("reply")
    if parent_reply is not None:
        root_uri = parent_reply["root"]["uri"]
        root_repo, root_collection, root_rkey = root_uri.split("/")[2:5]
        resp = requests.get(
            base_url + "/xrpc/com.atproto.repo.getRecord",
            params={
                "repo": root_repo,
                "collection": root_collection,
                "rkey": root_rkey,
            },
        )
        resp.raise_for_status()
        root = resp.json()

    return {
        "root": {
            "uri": root["uri"],
            "cid": root["cid"],
        },
        "parent": {
            "uri": parent["uri"],
            "cid": parent["cid"],
        },
    }

async def create_post(post_content: Dict, **args):
    base_url = "https://bsky.social"

    # trailing "Z" is preferred over "+00:00"
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    
    # these are the required fields which every post must include
    post = {
        "$type": "app.bsky.feed.post",
        "text": post_content["post"],
        "createdAt": now,
    }

    # indicate included languages (optional)
    try:
        if args["lang"]:
            post["langs"] = args["lang"]
    except KeyError:
        pass
    # parse out mentions and URLs as "facets"
   
    if len(post_content["post"]) > 0:
        facets = await parse_facets(post["text"], base_url)
        if facets:
            post["facets"] = facets
   

    # if this is a reply, get references to the parent and root
    try:
        if args["reply_to"]:
            post["reply"] = get_reply_refs(base_url, args["reply_to"])

        if args["image"]:
            post["embed"] = upload_images(
                base_url, session["accessJwt"], args["image"]#, alt_text
            )
        elif args["embed_url"]:
            post["embed"] = fetch_embed_url_card(
                base_url, session["accessJwt"], args["embed_url"]
            )
        elif args["embed_ref"]:
            post["embed"] = get_embed_ref(base_url, args["embed_ref"])
    except KeyError:
        pass


    print("creating post:", file=sys.stderr)
    # print(json.dumps(post, indent=2), file=sys.stderr)
    return post
    """
    resp = requests.post(
        args.base_url + "/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": "Bearer " + session["accessJwt"]},
        json={
            "repo": session["did"],
            "collection": "app.bsky.feed.post",
            "record": post,
        },
    )
    print("createRecord response:", file=sys.stderr)
    print(json.dumps(resp.json(), indent=2))
    resp.raise_for_status()
    """
    

@router.get("/publish/{page_id}")
async def publish_bsky(page_id):
   
    BSKY_SESSION_URL = 'https://bsky.social/xrpc/com.atproto.server.createSession'
    r = requests.post(BSKY_SESSION_URL, json={"identifier": BSKY_USERNAME, "password": BSKY_PASS})
    r.raise_for_status()
    session = r.json()
    access_token = session["accessJwt"]
    print(access_token)
    
    raw_posts = await transform_notion_to_posts(page_id)
    print(raw_posts)
    posts = []
    
    # loop through all the tweets and add corresponding images/video to it
    for i, item in enumerate(raw_posts):
        bsky_post = await create_post(item)
        posts.append(bsky_post)
        """
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
                    
                    img = upload_file(access_token=access_token, filename=temp_file_path, img_bytes=temp_file)
                    media.append(img)
        
        if len(tweets) <= 1:
            # there is only a single post
            if not media:
                # if no media we can directly post it
                response = client.create_tweet(text=item["post"], quote_tweet_id=item["quote"])
                tweets.append(response.data['id'])
                break

                
            else:
                response = client.create_tweet(text=item["post"], media_ids=[medium.media_id for medium in media])
                tweets.append(response.data['id'])
                break
        
        elif(i==0):
            # this is the first tweet of many
            if not media:
                response = client.create_tweet(text=item["post"], quote_tweet_id=item["quote"])
                tweets.append(response.data['id'])
                continue
            else:
                response = client.create_tweet(text=item["post"], media_ids=[medium.media_id for medium in media])
                tweets.append(response.data['id'])
                continue
        
        else:
            # this is a thread and we need to reply to the previous tweet
            if not media:
                response = client.create_tweet(text=item["post"], in_reply_to_tweet_id=tweets[-1], quote_tweet_id=item["quote"])
                tweets.append(response.data['id'])
                continue
            else:
                response = client.create_tweet(text=item["post"], in_reply_to_tweet_id=tweets[-1], media_ids=[medium.media_id for medium in media])
                tweets.append(response.data['id'])
                continue

    posted_tweets = [f"https://twitter.com/user/status/{tweet_id}" for tweet_id in tweets]
    tweet_url = posted_tweets[0]
    """
    
    # update_notion_properties = await update_notion_db(page_id, bksy_url)

    #return (tweet_url, update_notion_properties)
    return posts


@router.get("/{page_id}")
async def transform_notion_to_posts(page_id, post_length=300):
        url = f'https://api.notion.com/v1/blocks/{page_id}/children'
        headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": f"{NOTION_VERSION}",
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
            post["post"] = r""
            post["media"] = []
            post["quote"] = ""
            # TODO: parse bullet list blocks / numbered list blocks correctly
            
            # find paragraph blocks and publish
            paragraph_blocks = [block["paragraph"]["rich_text"] for block in chunks[i] if block["type"] == "paragraph"]
            for block in paragraph_blocks:
                if block:
                    # if our block starts with {{ we should is a quote_tweet 
                    if block[0]['plain_text'].strip().startswith("{{"):
                        post["quote"] = block[1]['plain_text'].split("/")[-1]
                    else:
                        post["post"] += f"{block[0]['plain_text'].rstrip()}\n"
                else:
                    post["post"] += "\n\n"
            
            media_blocks = [block["image"] for block in chunks[i] if block["type"] == "image"]
            for i, block in enumerate(media_blocks):
                if block:
                    post["media"].append({"fileUrl": block["file"]["url"]})
            
            try:
                post["char_count"] = len(post["post"])
                if post["char_count"] > post_length:
                    raise PostTooLongException() 
            except PostTooLongException:
                print(f'TOO LONG: {post["post"]}')
            
            try:
                if post["media"] and post["quote"]:
                # since media and quote tweets are mutually exclusive we need to stop here
                    raise TweetNoQuoteAndMediaException()
            except TweetNoQuoteAndMediaException:
                print(f"Quote Tweets cannot contain media - {post['post']}")

            posts.append(post)

        return posts