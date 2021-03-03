import praw
import json
import videogen
from time import sleep
from copy import deepcopy

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

base = json.load(open("videoexport.json"))

posts = ['lwjlif', 'lw2g2z', 'luf0ki', 'lvbv6v', 'lsyhdg']
submissions = []
for post_id in posts:
    videoexport = deepcopy(base)
    videoexport['info']['submission_id'] = post_id
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

