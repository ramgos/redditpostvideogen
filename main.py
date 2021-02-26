import subprocess
import pathlib
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
import auto_thumbnail
'''
NOTE: Known issue: if you have a whitespace in your path it would cause errors
when trying to synthesize audio clips
'''

# TODO Add option to gather comments by video length rather than comment amount
# TODO Handle Balcon TTS issues (like the whitespace in path)
# TODO Code multiple posts export
#   - Each video needs a seperate videoexport.json of itself,
#   an image which will be placed on top of the thumbnail, a defualt image
#   incase a custom image for the thumbnail isn't provided.

# LOWPRIORITY Add more customization (Read authors, read upvote count, etc...)
#   More ideas for cusstomization: Skip over comments that are longer that N characters

# load private information
credentials = json.load(open('config.json'))


def balcon_tts(voicename, speed, volume, outputfile, text):
    print(outputfile)
    wrkdir = os.path.dirname(outputfile)

    with open(str(wrkdir) + "/textholder.txt", "w", encoding="utf-8") as textholder:
        textholder.write(text)

    finalvoicename = '"' + voicename + '"'
    template = "balcon -n {voicename} -s {speed} -v {volume} -w {outputfile} -f {inputfile}"
    command = \
        template.format\
            (voicename=finalvoicename,
             speed=speed,
             volume=volume,
             outputfile=outputfile,
             inputfile=str(wrkdir) + "/textholder.txt")

    subprocess.run(command)
    os.remove(str(wrkdir) + "/textholder.txt")


def resize_to_screenbounds(filename, filedest, resolution=(1920, 1080)):
    im = Image.open(filename)
    resized_image = auto_thumbnail.smart_resize(image=im, new_res=resolution)
    resized_image.save(filedest, format='png')


# screenshot a webpage element given a selector, a webdriver and a file name to save to
def screenshot_element(csselctor, driver, file_location, wait_for_element_to_load):
    try:
        WebDriverWait(driver, wait_for_element_to_load).until(
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
def screenshot_thread(data, wrkdir, videoexport, headless=True):
    # run it so it doesn't open firefox on desktop
    options = webdriver.FirefoxOptions()
    options.headless = headless

    # initialize webdriver
    fox = webdriver.Firefox(options=options)
    fox.get(data['general']['url'])

    # change to darkmode
    # TODO Except TimeoutException Properly
    try:
        WebDriverWait(fox, videoexport['technical']['wait_for_elements_to_load']).until(
            EC.element_to_be_clickable((By.ID, "USER_DROPDOWN_ID"))
        )
    except TimeoutException:
        print("Something went wrong while waiting for an element to load...")
        return False
    fox.find_element(By.ID, "USER_DROPDOWN_ID").click()

    try:
        WebDriverWait(fox, videoexport['technical']['wait_for_elements_to_load']).until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()[contains(.,'Night Mode')]]"))
        )
    except TimeoutException:
        print("Something went wrong while waiting for an element to load...")
        return False
    fox.find_element\
        (By.XPATH, "//*[text()[contains(.,'Night Mode')]]").click()

    try:
        WebDriverWait(fox, videoexport['technical']['wait_for_elements_to_load']).until(
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
            wrkdir + data['general']['id'] + '.png',
            videoexport['technical']['wait_for_elements_to_load']
        )

    # a bit of a mess, but essentially it means: iterate over every
    # comment, but slice it so it will only take the comments it gathered data about
    for comment in data['general']['comments'][:len(data['comment_data'])]:
        screenshot_element("#" + comment.name, fox, wrkdir + comment.id + '.png', videoexport['technical']
        ['wait_for_elements_to_load'])

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
        "body": target_submission.selftext,
        "upvotes": target_submission.score,
        "subreddit": target_submission.subreddit_name_prefixed,
        "comments": target_submission.comments,
        "author": target_submission.author,
        "url": target_submission.url,
        "css-selector": target_submission.name
    }

    # data is what will be returned by the function
    reddit_data = \
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

    reddit_data['comment_data'] = comment_data
    return reddit_data

    # LOWPRIORITY Log post data


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
def organize_work_directory(data, videoexport):
    cwd = os.getcwd()
    # basepath = cwd + "/videos/"
    basepath = "videos/"

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

    success = screenshot_thread(data=data, wrkdir=videopath + "screenshots/", videoexport=videoexport, headless=True)

    # TODO Handle screenshot errors
    if success:
        print("success! screenshots saved succesfully")
    else:
        print(":(")

    bodydest = videopath + "body/" + general['id']
    bodysrc = videopath + "screenshots/" + general['id'] + ".png"

    bodydest_path = Path(bodydest + ".png")
    bodysrc_path = Path(bodysrc)

    resize_to_screenbounds(filename=bodysrc_path, filedest=bodydest_path)
    # engine.save_to_file(general['title'], bodydest + ".mp3")
    # engine.runAndWait()
    bodysaveunder = bodydest + ".mp3"
    additional_text = ""  # text that comes in addition after the reading of the title
    if bool(videoexport['video']['read_title_body']):
        additional_text += " "
        additional_text += general['body']

    balcon_tts\
        (voicename=videoexport['tts']['voice'],
         speed=videoexport['tts']['speed'],
         volume=videoexport['tts']['volume'],
         outputfile=bodysaveunder,
         text=general['title'] + additional_text)

    for comment in comment_data:
        dest = videopath + "comments/" + comment['id'] + "/"
        src = videopath + "screenshots/" + comment['id'] + ".png"

        mkdir_ifnotexist(dest)
        src_path = Path(src)
        dest_path = Path(dest + comment['id'] + ".png")
        resize_to_screenbounds(filename=src_path, filedest=dest_path)

        # engine.save_to_file(comment['body'], dest + comment['id'] + ".mp3")
        # engine.runAndWait()
        commentsaveunder = dest + comment['id'] + ".mp3"
        balcon_tts \
            (voicename=videoexport['tts']['voice'],
             speed=videoexport['tts']['speed'],
             volume=videoexport['tts']['volume'],
             outputfile=commentsaveunder,
             text=comment['body'])

    return videopath


# a function of this prob already exists and done better, couldn't bother to find it
# online. was faster to simply write it
def limit_high(a, b):
    if a < b:
        return a
    else:
        return b


def reverse_clip(clip):
    new_clip = clip.fl_time(lambda t: clip.duration-1-t)
    new_clip.duration = clip.duration
    return new_clip


def make_bg_video(bgbase, clip):
    dev = math.floor(clip.duration / bgbase.duration)
    rem = clip.duration % bgbase.duration

    if dev == 0:
        return bgbase.subclip(0, rem)
    else:
        clips = []
        for i in range(dev):
            if i % 2 == 1:
                clips.append(bgbase)
            else:
                clips.append(reverse_clip(bgbase))
        if rem > 0:
            clips.append(bgbase.subclip(0, rem))

    finalclip = concatenate_videoclips(clips=clips)
    return finalclip


def make_bg_audio(bgbase, clip):
    dev = math.floor(clip.duration / bgbase.duration)
    rem = clip.duration % bgbase.duration

    if dev == 0:
        return bgbase.subclip(0, rem)
    else:
        clips = []
        for _ in range(dev):
            clips.append(bgbase)
        if rem > 0:
            clips.append(bgbase.subclip(0, rem))

    finalclip = concatenate_audioclips(clips=clips)
    return finalclip


# essentially works like generate_clips() but doesn't require the reddit data
# dictionary to work (you can use an existing reddit video folder)

# assets_clips:
#   {
#       "videobgclip": VideoFileClip(videobg)
#       "videocensorclip": VideoFileClip(videocensor)
#       "bgmusicclip": VideoFileClip(bgmusic)
#   }
#
def generate_clips_folder_only(videopath, videoexport, asset_clips):
    clips = []

    videobgclip = asset_clips['videobgclip']
    videocensorclip = asset_clips['videocensorclip']
    bgmusicclip = asset_clips['bgmusicclip']

    # generate clip for body
    bodymp3_path = videopath + "body/" + [each for each in os.listdir(videopath + "body/") if each.endswith('.mp3')][0]
    bodyimage_path = videopath + "body/" + [each for each in os.listdir(videopath + "body/") if each.endswith('.png')][0]

    bodyimage_audio = AudioFileClip(bodymp3_path)
    bodyimage = ImageClip(bodyimage_path).set_duration(bodyimage_audio.duration +
                                                       videoexport['video']['wait_before_start'])
    bodyimage.audio = bodyimage_audio

    bodyid = Path(bodyimage_path).stem

    # bodybg = videobgclip.subclip(0, limit_high(bodyimage.duration, videobgclip.duration))
    bodybg = make_bg_video(bgbase=videobgclip, clip=bodyimage)
    bodyimagefinal = CompositeVideoClip([bodybg, bodyimage.set_position("center")],
                                        size=tuple(videoexport['video']['res']))

    clips.append(bodyimagefinal)

    for item in os.scandir(videopath + "comments/"):
        if item.is_dir():
            commentmp3_path = item.path + "/" + [each for each in os.listdir(item.path) if each.endswith('.mp3')][0]
            commentimage_path = item.path + "/" + [each for each in os.listdir(item.path) if each.endswith('.png')][0]

            commentimage_audio = AudioFileClip(commentmp3_path)
            commentimage = ImageClip(commentimage_path).\
                set_duration(commentimage_audio.duration + videoexport['video']['wait_between_comments'])
            commentimage.audio = commentimage_audio

            # commentbg = videobgclip.subclip(0, limit_high(commentimage.duration, videobgclip.duration))
            commentbg = make_bg_video(bgbase=videobgclip, clip=commentimage)
            commentimagefinal = CompositeVideoClip([commentbg, commentimage.set_position("center")],
                                                   size=tuple(videoexport['video']['res']))

            clips.append(commentimagefinal)
            if bool(videoexport['video']['enable_transitions']):
                clips.append(videocensorclip)

    # remove the last beep from video
    # clips.pop(-1)

    mergedclip = concatenate_videoclips(clips=clips)
    audiomain = mergedclip.audio
    audiobg = make_bg_audio(bgbase=bgmusicclip, clip=mergedclip)
    finalaudio = CompositeAudioClip([audiomain, audiobg.volumex(videoexport['video']['bgaudiovolume'])])

    mergedclip.audio = finalaudio
    mergedclip.write_videofile(videoexport['video']['save_under'] + bodyid + ".mp4", fps=videoexport['video']['fps'])


# main function - generates video from videoexport
def video_from_json(videoexport):
    assets = {
        "videobgclip": VideoFileClip(videoexport['assets']['videobg']),
        "videocensorclip": VideoFileClip(videoexport['assets']['videocensor']),
        "bgmusicclip": AudioFileClip(videoexport['assets']['bgmusic'])
    }
    r_data = grab_reddit_data(submission_id=videoexport['info']['submission_id'], size=5)
    # video_path = organize_work_directory(data=r_data, videoexport=videoexport)
    # generate_clips_folder_only(videopath=video_path, videoexport=videoexport, asset_clips=assets)

    text_data = auto_thumbnail.get_thumbnail_text(text=r_data['general']['title'], data=videoexport)
    thumbnail = auto_thumbnail.draw_colored_text(text_data=text_data, data=videoexport)
    thumbnail.save(videoexport['video']['save_under'] + videoexport['info']['submission_id'] + ".png")


if __name__ == "__main__":
    video_from_json(json.load(open('videoexport.json')))
