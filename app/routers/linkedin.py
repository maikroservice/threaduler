from ..vars import get_notion_envs, get_linkedin_envs
from typing import List, Dict
NOTION_TOKEN, NOTION_DATABASE_ID, NOTION_API_VERSION = get_notion_envs()
LINKEDIN_CLIENT_ID, LINKEDIN_ACCESS_TOKEN, LINKEDIN_CLIENT_SECRET = get_linkedin_envs()
import requests
from enum import Enum
from fastapi import APIRouter
import random
import json

router = APIRouter(
    prefix="/linkedin",
    tags=["linkedin"],
    responses={404: {"description": "Not found"}},
)

class LinkedinType(Enum):
    person = 1
    organization = 2

@router.get("/token")
def get_user_token():
    URL = "https://www.linkedin.com/oauth/v2/authorization"
    params = {
    "response_type":"code",
    "client_id": LINKEDIN_CLIENT_ID,
    "redirect_uri": "http://localhost:8000/linkedin/token2",
    "state": str(random.randint(0, 12039401293)),
    "scope": "w_member_social",
    }
    headers = {"X-Restli-Protocol-Version": "2.0.0"}#, "Content-Type": "application/json"}
    r = requests.get(URL, params=params, headers=headers)
    return (r.url)

@router.get("/token2")
def authenticate_linkedin(code: str, state: str):
    url = 'https://www.linkedin.com/oauth/v2/accessToken'
    params = {
      'grant_type': 'authorization_code',
      'code': code,
      "state": state,
      "redirect_uri": "http://localhost:8000/linkedin/token2",
      'client_id': LINKEDIN_CLIENT_ID,
      'client_secret': LINKEDIN_CLIENT_SECRET,
    }
    headers = {"X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/x-www-form-urlencoded", "User-Agent": "OAuth gem v0.4.4"}
    response = requests.post(url, data=params, headers=headers)

    try:
        access_token = response.json()['access_token']
        return ('Access token:', access_token)
    except:
        return ('Error:', response.status_code, response.text)

def create_post(text: str, args: Dict) -> Dict:
    headers = {"X-Restli-Protocol-Version": "2.0.0"}
    URL = ""
    try:
        linkedinType = args["Entitity"]
    except KeyError:
        pass

    r = requests.post(URL, data=data, headers=headers)

    data = {
        "author": f"urn:li:{linkedinType}:{USERNAME}",
        "lifecycleState": "PUBLISHED",
        "specificContent": {
            "com.linkedin.ugc.ShareContent": {
                "media": [
                    {
                        "media": f"urn:li:digitalmediaAsset:{IMAGE}",
                        "status": "READY"
                    }
                ],
                "shareCommentary": {
                    "attributes": [],
                    "text": "Let's go live on LinkedIn!"
                },
                "shareMediaCategory": "LIVE_VIDEO"
            }
        },
        "visibility": {
            "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
        }
    }
