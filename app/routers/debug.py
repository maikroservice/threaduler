import requests
import os 
from fastapi import APIRouter
from ..vars import get_notion_envs

router = APIRouter(
    prefix="/debug",
    tags=["debug"],
)

NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_VERSION = get_notion_envs()

@router.get("/schedule")
async def schedule():
    
    url = f'https://api.notion.com/v1/databases/{NOTION_DATABASE_ID}/query'
    
    r = requests.post(url, headers={
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28"
        })
    result_dict = r.json()
    
    only_scheduled_posts = [
        {
            "url": item["url"],
            "page_id": item["id"],
            "title": item["properties"]["Title"]["title"][0]["text"]["content"], 
            "publish_time": item["properties"]["publish_time"]["date"]["start"], 
            "time_zone": item["properties"]["publish_time"]["date"]["time_zone"],
            "status": item["properties"]["Status"]["status"]["name"]}
        for item in result_dict["results"]
            if item["properties"]["publish_time"]["date"] is not None]
    
    only_non_published = [item for item in only_scheduled_posts if item["status"] == "Ready"]
    # TODO this should just be a comparison of unix timestamps and take care of the time as well? 
    only_future_posts = [posts for post in only_non_published if datetime.fromisoformat(post["publish_time"]).date() >= datetime.today().date()]
    
    # sort the results by the publish time (ascending)
    return sorted(only_future_posts, key=lambda x: x['publish_time'])


@router.get("/{page_id}")
async def transform_notion_to_raw_posts(page_id):
    # this gives us the raw notion api response for potential debugging
    url = f'https://api.notion.com/v1/blocks/{page_id}/children'
    r = requests.get(url, headers={
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": f"{NOTION_VERSION}",
    
    })
    return r.json()


@router.get("/update_notion/{page_id}")
# write data to notion?/database / sync current likes/retweets etc 
# update URL property + Status Property after publishing
async def update_notion_metadata(page_id, platform, post_url):
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
                f"{platform}_url": {
                    "url": post_url
                }
            }
        }
    )

    return int(r.status_code != 200)