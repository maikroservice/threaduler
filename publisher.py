import requests
from datetime import datetime 
import pytz

URL = "http://localhost:8000"
SCHEDULE_ENDPOINT = "/schedule/"
PUBLISH_ENDPOINT = "/publish/"
r = requests.get(f"{URL}{SCHEDULE_ENDPOINT}")
data = r.json()

for tweet in data:
    timestamp = datetime.strptime(tweet['publish_time'], '%Y-%m-%dT%H:%M:%S.%f%z')

    if timestamp < datetime.now(pytz.utc):
        # this timestamp is in the past and should be published
        r = requests.get(f"{URL}{PUBLISH_ENDPOINT}{tweet['page_id']}")
        print(r.json())