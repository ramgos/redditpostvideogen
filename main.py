import pyttsx3
import praw
import json
import os.path
from moviepy.editor import *
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from PIL import Image
from pathlib import Path
import math

rate = 135  # normal speed
res = 1920, 1080  # resolution of video

# load private information
credentials = json.load(open('config.json'))

# setup tts engine
# TODO find better tts solution
engine = pyttsx3.init()
engine.setProperty('rate', rate)

videobg = "Flavor/BG.mp4"
videocensor = "Flavor/censor2.mp4"

videocensorclip = VideoFileClip(videocensor)
videobgclip = VideoFileClip(videobg)  # TODO Make loopable
# (make function to create a video clip of space background of any length


def resize_to_screenbounds(filename, filedest, resolution=(1920, 1080)):
    im = Image.open(filename)
    size = im.size
    if size[0] / size[1] >= 1:  # if the image is horizontal
        ratio = size[1]/size[0]
        y = math.floor(ratio * resolution[0])
        resized_image = im.resize((resolution[0], y))
        resized_image.save(filedest, format='png')
    else:
        ratio = size[0]/size[1]
        x = math.floor(ratio * resolution[1])
        resized_image = im.resize((x, resolution[1]))


# screenshot a webpage element given a selector, a webdriver and a file name to save to
def screenshot_element(csselctor, driver, file_location):
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, csselctor))
        )
    except TimeoutException:
        print("Something went wrong while waiting for an element to load...")
        return
    image = driver.find_element\
        (By.CSS_SELECTOR, csselctor)
    driver.execute_script("arguments[0].scrollIntoView();", image)
    sleep(3)
    image.screenshot(file_location)


# screenshot reddit thread provided data from def get_reddit_data() and a working directory
# returns True if success, False if fail
def screenshot_thread(data, wrkdir, headless=True):
    # run it so it doesn't open firefox on desktop
    options = webdriver.FirefoxOptions()
    options.headless = headless

    # initialize webdriver
    fox = webdriver.Firefox(options=options)
    fox.get(data['general']['url'])

    # change to darkmode
    try:
        WebDriverWait(fox, 10).until(
            EC.element_to_be_clickable((By.ID, "USER_DROPDOWN_ID"))
        )
    except TimeoutException:
        print("Something went wrong while waiting for an element to load...")
        return False
    fox.find_element(By.ID, "USER_DROPDOWN_ID").click()

    try:
        WebDriverWait(fox, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()[contains(.,'Night Mode')]]"))
        )
    except TimeoutException:
        print("Something went wrong while waiting for an element to load...")
        return False
    fox.find_element\
        (By.XPATH, "//*[text()[contains(.,'Night Mode')]]").click()

    try:
        WebDriverWait(fox, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()[contains(.,'View Entire Disc')]]"))
        )
    except TimeoutException:
        print("Something went wrong while waiting for an element to load...")
        return False
    fox.find_element\
        (By.XPATH, "//*[text()[contains(.,'View Entire Disc')]]").click()

    # screenshot body
    screenshot_element\
        (
            "#" + data['general']['css-selector'],
            fox,
            wrkdir + data['general']['id'] + '.png'
        )

    # a bit of a mess, but essentially it means: iterate over every
    # comment, but slice it so it will only take the comments it gathered data about
    for comment in data['general']['comments'][:len(data['comment_data'])]:
        screenshot_element("#" + comment.name, fox, wrkdir + comment.id + '.png')

    fox.close()
    return True


# return all relevant regarding a reddit thread as a dictionary containing the body and comments
# size determines the amount of comments the script is going to return

def grab_reddit_data(submission_id, size):
    reddit = praw.Reddit(
        client_id=credentials['client_id'],
        client_secret=credentials['client_secret'],
        user_agent=credentials['user_agent'],
        username=credentials['username'],
        password=credentials['password']
    )

    target_submission = reddit.submission(id=submission_id)
    # target_submission.comment_sort = "top"

    # general data regarding the post
    main_post_dict = \
    {
        "id": submission_id,
        "title": target_submission.title,
        "upvotes": target_submission.score,
        "subreddit": target_submission.subreddit_name_prefixed,
        "comments": target_submission.comments,
        "author": target_submission.author,
        "url": target_submission.url,
        "css-selector": target_submission.name
    }

    # data is what will be returned by the function
    data = \
    {
        "general": main_post_dict
    }
    comment_data = []

    for comment in target_submission.comments[:size]:
        cmnt = \
        {
            "id": comment.id,
            "author": comment.author,
            "body": comment.body
        }
        comment_data.append(cmnt)

    data['comment_data'] = comment_data
    return data


'''
grab_reddit_data format:

{
    "general": main_post_dict ( see def grab_reddit_data() )
    "comment_data": 
        [
            {
                'id': id
                'author': author
                'body': body
            },
            {
                'id': id
                'author': author
                'body': body
            },
            ...
        ]
'''


def mkdir_ifnotexist(dirname):
    if not os.path.isdir(dirname):
        os.mkdir(dirname)


# this creats and organizes a directory containing all important
# material for the creation of the video

# returns video path
def organize_work_directory(data):
    cwd = os.getcwd()
    basepath = cwd + "/videos/"

    general = data['general']
    comment_data = data['comment_data']

    # creating all needed folders
    mkdir_ifnotexist(cwd + "/videos")

    mkdir_ifnotexist(basepath + general['id'])
    videopath = basepath + general['id'] + "/"

    mkdir_ifnotexist(videopath + "screenshots/")
    mkdir_ifnotexist(videopath + "clips/")
    mkdir_ifnotexist(videopath + "comments/")
    mkdir_ifnotexist(videopath + "body/")
    success = screenshot_thread(data=data, wrkdir=videopath + "screenshots/", headless=True)

    # TODO handle screenshot errors
    if success:
        print("success! screenshots saved succesfully")
    else:
        print(":(")

    bodydest = videopath + "body/" + general['id']
    bodysrc = videopath + "screenshots/" + general['id'] + ".png"

    bodydest_path = Path(bodydest + ".png")
    bodysrc_path = Path(bodysrc)

    resize_to_screenbounds(filename=bodysrc_path, filedest=bodydest_path)
    engine.save_to_file(general['title'], bodydest + ".mp3")
    engine.runAndWait()

    for comment in comment_data:
        dest = videopath + "comments/" + comment['id'] + "/"
        src = videopath + "screenshots/" + comment['id'] + ".png"

        mkdir_ifnotexist(dest)
        src_path = Path(src)
        dest_path = Path(dest + comment['id'] + ".png")
        resize_to_screenbounds(filename=src_path, filedest=dest_path)

        engine.save_to_file(comment['body'], dest + comment['id'] + ".mp3")
        engine.runAndWait()
    return videopath


# a function of this prob already exists and done better, couldn't bother to find it
# online. was faster to simply write it
def limit_high(a, b):
    if a < b:
        return a
    else:
        return b


# generates clips from material
# TODO Change this function to not depend on data, but only on folder structure
def generate_clips(videopath, data):
    general = data['general']
    comment_data = data['comment_data']
    clips = []

    # generate clip for body
    bodymp3_path = videopath + "body/" + general['id'] + ".mp3"
    bodyimage_path = videopath + "body/" + general['id'] + ".png"

    bodyimage_audio = AudioFileClip(bodymp3_path)
    bodyimage = ImageClip(bodyimage_path).set_duration(bodyimage_audio.duration)
    bodyimage.audio = bodyimage_audio

    bodybg = videobgclip.subclip(0, limit_high(bodyimage.duration, videobgclip.duration))
    bodyimagefinal = CompositeVideoClip([bodybg, bodyimage.set_position("center")], size=res)

    clips.append(bodyimagefinal)

    for comment in comment_data:
        commentimage_path = videopath + "comments/" + comment['id'] + "/" + comment['id'] + ".png"
        commentmp3_path = videopath + "comments/" + comment['id'] + "/" + comment['id'] + ".mp3"

        commentimage_audio = AudioFileClip(commentmp3_path)
        commentimage = ImageClip(commentimage_path).set_duration(commentimage_audio.duration)
        commentimage.audio = commentimage_audio

        commentbg = videobgclip.subclip(0, limit_high(commentimage.duration, videobgclip.duration))
        commentimagefinal = CompositeVideoClip([commentbg, commentimage.set_position("center")], size=res)

        clips.append(commentimagefinal)
        clips.append(videocensorclip)

    # remove the last beep from video
    clips.pop(-1)

    finalclip = concatenate_videoclips(clips=clips)
    finalclip.write_videofile("test.mp4", fps=15)


submission_id = 'lhxkmf'
data = grab_reddit_data(submission_id=submission_id, size=5)
videopath = organize_work_directory(data=data)
generate_clips(videopath=videopath, data=data)
