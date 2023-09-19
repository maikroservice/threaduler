import requests
import os
import sys
import json
import tempfile
from fastapi import APIRouter
from typing import Dict, List
from ..vars import get_notion_envs, get_bsky_envs
from ..dependencies import notion_blocks_to_post_chunks, PostTooLongException
from .debug import update_notion_metadata
from datetime import datetime, timezone
import re
from bs4 import BeautifulSoup
import shutil
from urllib3.exceptions import InvalidChunkLength
import numpy as np
import cv2


NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_API_VERSION = get_notion_envs()
BSKY_USERNAME, BSKY_PASS, BSKY_BASEURL = get_bsky_envs()
MAX_FILE_SIZE = 100000

router = APIRouter(
    prefix="/bsky",
    tags=["bsky"],
    responses={404: {"description": "Not found"}},
)
# bsky functions from: https://github.com/bluesky-social/atproto-website/blob/main/examples/create_bsky_post.py
def upload_file(access_token, img_bytes) -> Dict:
    # FIXME: refactor and automate
    """
    suffix = filename.split(".")[-1].lower()
    mimetype = "application/octet-stream"
    if suffix in ["png"]:
        mimetype = "image/png"
    elif suffix in ["jpeg", "jpg"]:
        mimetype = "image/jpeg"
    elif suffix in ["webp"]:
        mimetype = "image/webp"
    """
    #TODO: figure  out if notion removes EXIF data by default 
    # TODO: refactor so that there is only 1 function?
    resp = requests.post(
        "https://bsky.social/xrpc/com.atproto.repo.uploadBlob",
        headers={
            "Content-Type": "image/png",
            "Authorization": "Bearer " + access_token,
        },
        data=img_bytes,
    )
    resp.raise_for_status()
    return {"alt": "test123", "image": resp.json()["blob"]}
    

def parse_uri(uri: str) -> Dict:
    if uri.startswith("at://"):
        repo, collection, rkey = uri.split("/")[2:5]
        return {"repo": repo, "collection": collection, "rkey": rkey}
    elif uri.startswith("https://bsky.app/"):
        repo, collection, rkey = uri.split("/")[4:7]
        if collection == "post":
            collection = "app.bsky.feed.post"
        elif collection == "lists":
            collection = "app.bsky.graph.list"
        elif collection == "feed":
            collection = "app.bsky.feed.generator"
        return {"repo": repo, "collection": collection, "rkey": rkey}
    else:
        raise Exception("unhandled URI format: " + uri)

def fetch_embed_url_card(pds_url: str, access_token: str, url: str) -> Dict:
    # the required fields for an embed card
    card = {
        "uri": url,
        "title": "",
        "description": "",
    }

    # fetch the HTML
    resp = requests.get(url)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    title_tag = soup.find("meta", property="og:title")
    if title_tag:
        card["title"] = title_tag["content"]

    description_tag = soup.find("meta", property="og:description")
    if description_tag:
        card["description"] = description_tag["content"]

    image_tag = soup.find("meta", property="og:image")
    if image_tag:
        img_url = image_tag["content"]
        if "://" not in img_url:
            img_url = url + img_url
        resp = requests.get(img_url)
        resp.raise_for_status()
        card["thumb"] = upload_file(pds_url, access_token, img_url, resp.content)

    return {
        "$type": "app.bsky.embed.external",
        "external": card,
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

def parse_facets(text: str) -> List[Dict]:
    """
    parses post text and returns a list of app.bsky.richtext.facet objects for any mentions (@handle.example.com) or URLs (https://example.com)

    indexing must work with UTF-8 encoded bytestring offsets, not regular unicode string offsets, to match Bluesky API expectations
    """
    facets = []
    mentions = parse_mentions(text)
    
    for m in mentions:
        resp = requests.get(
            BSKY_BASEURL + "/xrpc/com.atproto.identity.resolveHandle",
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

def get_embed_ref(ref_uri: str) -> Dict:
    uri_parts = parse_uri(ref_uri)
    resp = requests.get(
        BSKY_BASEURL + "/xrpc/com.atproto.repo.getRecord",
        params=uri_parts,
    )
    #print(resp.json())
    resp.raise_for_status()
    record = resp.json()

    return {
        "$type": "app.bsky.embed.record",
        "record": {
            "uri": record["uri"],
            "cid": record["cid"],
        },
    }

def get_reply_refs(parent_uri: str) -> Dict:
    uri_parts = parse_uri(parent_uri)
    resp = requests.get(
        BSKY_BASEURL + "/xrpc/com.atproto.repo.getRecord",
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
            BSKY_BASEURL + "/xrpc/com.atproto.repo.getRecord",
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


def reduce_image_memory(path, max_file_size: int = MAX_FILE_SIZE):
    #https://stackoverflow.com/questions/66455731/how-to-calculate-the-resulting-filesize-of-image-resize-in-pil
    """
        Reduce the image memory by downscaling the image.

        :param path: (str) Path to the image
        :param max_file_size: (int) Maximum size of the file in bytes
        :return: (np.ndarray) downscaled version of the image
    """
    image = cv2.imread(path)
    height, width = image.shape[:2]

    original_memory = os.stat(path).st_size
    original_bytes_per_pixel = original_memory / np.product(image.shape[:2])

    # perform resizing calculation
    new_bytes_per_pixel = original_bytes_per_pixel * (max_file_size / original_memory)
    new_bytes_ratio = np.sqrt(new_bytes_per_pixel / original_bytes_per_pixel)
    new_width, new_height = int(new_bytes_ratio * width), int(new_bytes_ratio * height)

    new_image = cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_LINEAR_EXACT)
    return new_image

@router.get("/{page_id}")
def transform_notion_to_posts(page_id, post_length=300):
        url = f'https://api.notion.com/v1/blocks/{page_id}/children'
        headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_API_VERSION,
        }
        r = requests.get(url, headers=headers)
        
        
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

            posts.append(post)

        return posts

def create_post(post_content: Dict, args: Dict):
    #print(args["media"])

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
        facets = parse_facets(post["text"])
        if facets:
            post["facets"] = facets
   
    

    # if this is a reply, get references to the parent and root
    try:
        if args["posts"]:
            post["reply"] = get_reply_refs(args["posts"][-1])
        
        elif args["embed_url"]:
            post["embed"] = fetch_embed_url_card(
                args["session"]["accessJwt"], args["embed_url"]
            )
        elif args["embed_ref"]:
            post["embed"] = get_embed_ref(args["embed_ref"])
    except KeyError:
        pass

    # if post has images/media attached we hand it over to the post
    try:
        if args["media"]:
            post["embed"] = args["media"]
    except KeyError:
        pass


    #print("creating post:", file=sys.stderr)
    #print(json.dumps(post, indent=2), file=sys.stderr)

    resp = requests.post(
        BSKY_BASEURL + "/xrpc/com.atproto.repo.createRecord",
        headers={"Authorization": "Bearer " + args["session"]["accessJwt"]},
        json={
            "repo": args["session"]["did"],
            "collection": "app.bsky.feed.post",
            "record": post,
        },
    )
    
    #print("createRecord response:", file=sys.stderr)
    #print(json.dumps(resp.json(), indent=2))
    resp.raise_for_status()
    return resp.json()
    

@router.get("/publish/{page_id}")
def publish_bsky(page_id):
   
    BSKY_SESSION_URL = f'{BSKY_BASEURL}/xrpc/com.atproto.server.createSession'
    r = requests.post(BSKY_SESSION_URL, json={"identifier": BSKY_USERNAME, "password": BSKY_PASS})
    r.raise_for_status()
    session = r.json()
    args = {"session": session}
    
    raw_posts = transform_notion_to_posts(page_id)
    posts = []
    # loop through all the posts and add corresponding images/video to it
    for item in raw_posts:
        
        args["posts"] = posts

        if item["media"]:
            args["media"] = {'$type': 'app.bsky.embed.images', 'images': []}
            for image in item["media"]:
                if image:
                    """
                    try:
                        with tempfile.NamedTemporaryFile(mode='w+b') as temp_file:
                            response = requests.get(image["fileUrl"], stream=True)
                            try:
                                shutil.copyfileobj(response.raw, temp_file)
                                temp_file_path = temp_file.name
                                
                                if temp_file.tell() > 1000000:
                                    from PIL import Image
                                    f_size = temp_file.tell()
                                    print(f_size)
                                    image = Image.open(temp_file)
                                    image.thumbnail([sys.maxsize, 800], Image.LANCZOS)
                                    img = upload_file(access_token=session["accessJwt"], img_bytes=image.tobytes())
                                    args['media']["images"].append(img)
                                    break

                                temp_file.seek(0)
                                img = upload_file(access_token=session["accessJwt"], img_bytes=temp_file.read())
                                args['media']["images"].append(img)

                                except InvalidChunkLength as e:
                                    print(f"Error copying file: {e}")
                                else:
                                    print(f"Request failed with status code: {response.status_code}")
                                
                    except Exception as e:
                        print(f"An error occurred: {e}")
                    """
                    with tempfile.NamedTemporaryFile(mode='w+b') as temp_file:
                        
                        # TODO: maybe add line 268 until 278 into a debug/util function and use the same one in twitter
                        import shutil
                        # we first need to download the image from the s3 bucket that notion places them in
                        response = requests.get(image["fileUrl"], stream=True)
                        # Write data to the temporary file
                        # we do it this way because we need to figure out the file mime type and shutil does that for us
                        # + the raw response needs to be stored and this was the easiest solution stackoverflow had 😅
                        shutil.copyfileobj(response.raw, temp_file)
                        #del response
                        
                        # Get the path of the temporary file
                        temp_file_path = temp_file.name

                        # this size limit specified in the app.bsky.embed.images lexicon
                        if temp_file.tell() > MAX_FILE_SIZE:
                            f_size = temp_file.tell()
                            print(f_size)
                            image = reduce_image_memory(temp_file_path, max_file_size=MAX_FILE_SIZE)
                            img = upload_file(access_token=session["accessJwt"], img_bytes=image.tobytes())
                            args['media']["images"].append(img)
                            break
                            #raise Exception(
                            #    f"{image['fileUrl']} - image file size was too large. 1000000 bytes (~1MB) maximum, got: {f_size} resized to {temp_file.tell()}"
                            #)
                            # print(f"resized image - {image['fileUrl']}")
                        # upload the medium to bsky
                        temp_file.seek(0)
                        img = upload_file(access_token=session["accessJwt"], img_bytes=temp_file.read())
                        args['media']["images"].append(img)
                        # TODO figure out how we can initialize the embed section of the post properly
                        
        else:
            try:
                del args["media"]
            except KeyError:
                args["media"] = None
        # publishing the posts
        response = create_post(item, args=args)
        posts.append(response["uri"])
                
    
    posted_bsky_posts = [f"https://bsky.app/profile/{BSKY_USERNAME}/post/{post_id.split('/')[-1]}" for post_id in posts]
    bsky_url = posted_bsky_posts[0]
    
    
    update_notion_properties = update_notion_metadata(page_id, "bsky", bsky_url)

    return (bsky_url, update_notion_properties)