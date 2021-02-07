
import os
from requests import get, post
import sys

from ratelimit import *

get = sleep_and_retry(limits(calls=1, period=0.25)(get))

registry = "https://hub.docker.com"
namespace = "satex"

def get_token(username, password):
    H = {"Content-Type": "application/json"}
    r = post(f"{registry}/v2/users/login", headers=H,
        data=f'{{"username": "{username}", "password": "{password}"}}')
    return r.json()["token"]

TOKEN = get_token(os.getenv("DOCKER_USERNAME"), os.getenv("DOCKER_PASSWORD"))

H = {"Authorization": f"JWT {TOKEN}"}

repositories = []
next_url = f"{registry}/v2/repositories/{namespace}/?page_size=10000"
while next_url:
    r = get(next_url, headers=H)
    d = r.json()
    repositories += [e["name"] for e in d["results"]]
    next_url = d.get("next")

for repo in repositories:
    r = get(f"{registry}/v2/repositories/{namespace}/{repo}/tags/?page_size=10000")
    d = r.json()
    if "results" not in d:
        print(f"No results for {repo}! {d}", file=sys.stderr)
        continue
    for t in d["results"]:
        print(f"{repo}:{t['name']}")
