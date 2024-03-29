import praw
import json
import videogen
from time import sleep
from copy import deepcopy
import random
import os

# load credentials
credentials = json.load(open("config.json"))

with open('posted.txt', 'r') as f:
    posted = [x.replace('\n', '') for x in f.readlines()]

# create reddit client
reddit = praw.Reddit(
    client_id=credentials['client_id'],
    client_secret=credentials['client_secret'],
    user_agent=credentials['user_agent'],
    username=credentials['username'],
    password=credentials['password']
)

base = json.load(open("videoexport.json"))

posts = ['my7b6s', 'mxx3ag']
only_new_posts = [x for x in posts if x not in posted]
print(only_new_posts)

if only_new_posts:
    submissions = []

    with open('posted.txt', 'a') as f:
        for post in posts:
            f.write(post + '\n')

    for post_id in posts:
        videoexport = deepcopy(base)
        videoexport['info']['submission_id'] = post_id
        videoexport['thumbnail_data']['assets']['overlay_image'] = \
            "hidden/sauce/" + random.choice(os.listdir("hidden/sauce/"))
        submissions.append(videoexport)

    for export in submissions:
        videogen.video_from_json(export, reddit)
        sleep(5)


'''
# EXAMPLE SCRIPT USING VIDEOGEN.py
# This script uses videogen.py along side with
# praw, to grab the 2 hottest posts from r/learnpython
# and make them youtube reddit reader videos

import praw
import json
import videogen

# load credentials
credentials = json.load(open("config.json"))

# create reddit client
reddit = praw.Reddit(
    client_id=credentials['client_id'],
    client_secret=credentials['client_secret'],
    user_agent=credentials['user_agent'],
    username=credentials['username'],
    password=credentials['password']
)

# get subreddit object of r/learn python
subreddit = reddit.subreddit("learnpython")

# create base template for video export settings
base = json.load(open("videoexport.json"))

submissions = []
for submission in subreddit.hot(limit=2):
    if submission.is_self:
        videoexport = base
        videoexport['info']['submission_id'] = submission.id
        submissions.append(videoexport)

for export in submissions:
    videogen.video_from_json(export, reddit)
'''

