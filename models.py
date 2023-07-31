from enum import Enum
from typing import List
from pydantic import BaseModel
from uuid import uuid4
from datetime import datetime

class Status(str, Enum):
    draft = "Draft"
    ready = "Ready"
    scheduled = "Scheduled"
    done = "Done"

class TweetText(BaseModel):
    content: str = None
    max_length: int = 280


class Tweet(BaseModel):
    uuid = uuid4()
    tweet_id: float = None
    tweet_text = TweetText()
    # TODO: does this work?
    status: Enum = Status("Draft")
    publish_time: datetime = None
    link: str = ""
    retweet_time: datetime = None
    retweet_status = Status("Draft")
    likes: int = 0
    retweets: int = 0
    impressions: int = 0
    profile_visits: int = 0
    link_clicks: int = 0
    replies: int = 0


class TweetThread(BaseModel):
    uuid = uuid4()
    tweets: List[Tweet]
    max_tweets = 25
    first_tweet: Tweet = None
    last_tweet: Tweet = None

