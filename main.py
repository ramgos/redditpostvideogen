import pyttsx3
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

'''
NOTE: Known issue: if you have a whitespace in your path it would cause errors
when trying to synthesize audio clips
'''

# TODO Add option to gather comments by video length rather than comment amount
# TODO Handle Balcon TTS issues (like the whitespace in path)
# TODO Create automatic thumbnail

# TODO (low priority) Add more customization (Read authors, read upvote count, etc...)
# More ideas for cusstomization: Skip over comments that are longer that N characters

# rate = 135  # normal speed

# load private information
credentials = json.load(open('config.json'))
videoprofile = json.load(open('videoexport.json'))

# setup tts engine
# engine = pyttsx3.init()
# engine.setProperty('rate', rate)

post_id = videoprofile['info']['submission_id']

wait_for_element_to_load = videoprofile['technical']['wait_for_elements_to_load']

ttsvoice = videoprofile['tts']['voice']
ttsspeed = videoprofile['tts']['speed']
ttsvolume = videoprofile['tts']['volume']

fps = videoprofile['video']['fps']
bgaudiovolume = videoprofile['video']['bgaudiovolume']
res = tuple(videoprofile['video']['res'])
wait_before_start = videoprofile['video']['wait_before_start']
wait_between_comments = videoprofile['video']['wait_between_comments']
enable_transitions = bool(videoprofile['video']['enable_transitions'])
read_title_body = bool(videoprofile['video']['read_title_body'])

videobg = videoprofile['assets']['videobg']
videocensor = videoprofile['assets']['videocensor']
bgmusic = videoprofile['assets']['bgmusic']

videocensorclip = VideoFileClip(videocensor)
videobgclip = VideoFileClip(videobg)
bgmusicclip = AudioFileClip(bgmusic)


def balcon_tts(voicename, speed, volume, outputfile, text):
    wrkdir = pathlib.Path(outputfile).absolute().parent

    with open(str(wrkdir) + "/" + "textholder.txt", "w", encoding="utf-8") as textholder:
        textholder.write(text)

    finalvoicename = '"' + voicename + '"'
    template = "balcon -n {voicename} -s {speed} -v {volume} -w {outputfile} -f {inputfile}"
    command = \
        template.format\
            (voicename=finalvoicename,
             speed=speed,
             volume=volume,
             outputfile=outputfile,
             inputfile=str(wrkdir) + "/" + "textholder.txt")

    subprocess.run(command)
    os.remove(str(wrkdir) + "/" + "textholder.txt")


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
        resized_image.save(filedest, format='png')


# screenshot a webpage element given a selector, a webdriver and a file name to save to
def screenshot_element(csselctor, driver, file_location):
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
def screenshot_thread(data, wrkdir, headless=True):
    # run it so it doesn't open firefox on desktop
    options = webdriver.FirefoxOptions()
    options.headless = headless

    # initialize webdriver
    fox = webdriver.Firefox(options=options)
    fox.get(data['general']['url'])

    # change to darkmode
    # TODO Except TimeoutException Properly
    try:
        WebDriverWait(fox, wait_for_element_to_load).until(
            EC.element_to_be_clickable((By.ID, "USER_DROPDOWN_ID"))
        )
    except TimeoutException:
        print("Something went wrong while waiting for an element to load...")
        return False
    fox.find_element(By.ID, "USER_DROPDOWN_ID").click()

    try:
        WebDriverWait(fox, wait_for_element_to_load).until(
            EC.element_to_be_clickable((By.XPATH, "//*[text()[contains(.,'Night Mode')]]"))
        )
    except TimeoutException:
        print("Something went wrong while waiting for an element to load...")
        return False
    fox.find_element\
        (By.XPATH, "//*[text()[contains(.,'Night Mode')]]").click()

    try:
        WebDriverWait(fox, wait_for_element_to_load).until(
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

    # TODO (Low priority) Optional: Log post data


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
    if read_title_body:
        additional_text += " "
        additional_text += general['body']

    balcon_tts\
        (voicename=ttsvoice,
         speed=ttsspeed,
         volume=ttsvolume,
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
            (voicename=ttsvoice,
             speed=ttsspeed,
             volume=ttsvolume,
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


# generates clips from material and renders a final video
# TODO Add start and end clip
def generate_clips(videopath, data):
    general = data['general']
    comment_data = data['comment_data']
    clips = []

    # generate clip for body
    bodymp3_path = videopath + "body/" + general['id'] + ".mp3"
    bodyimage_path = videopath + "body/" + general['id'] + ".png"

    bodyimage_audio = AudioFileClip(bodymp3_path)
    bodyimage = ImageClip(bodyimage_path).set_duration(bodyimage_audio.duration + wait_before_start)
    bodyimage.audio = bodyimage_audio

    # bodybg = videobgclip.subclip(0, limit_high(bodyimage.duration, videobgclip.duration))
    bodybg = make_bg_video(bgbase=videobgclip, clip=bodyimage)
    bodyimagefinal = CompositeVideoClip([bodybg, bodyimage.set_position("center")], size=res)

    clips.append(bodyimagefinal)

    for comment in comment_data:
        commentimage_path = videopath + "comments/" + comment['id'] + "/" + comment['id'] + ".png"
        commentmp3_path = videopath + "comments/" + comment['id'] + "/" + comment['id'] + ".mp3"

        commentimage_audio = AudioFileClip(commentmp3_path)
        commentimage = ImageClip(commentimage_path).set_duration(commentimage_audio.duration)
        commentimage.audio = commentimage_audio

        # commentbg = videobgclip.subclip(0, limit_high(commentimage.duration, videobgclip.duration))
        commentbg = make_bg_video(bgbase=videobgclip, clip=commentimage)
        commentimagefinal = CompositeVideoClip([commentbg, commentimage.set_position("center")], size=res)

        clips.append(commentimagefinal)
        if enable_transitions == 1:
            clips.append(videocensorclip)

    # remove the last beep from video
    # clips.pop(-1)

    mergedclip = concatenate_videoclips(clips=clips)
    audiomain = mergedclip.audio
    audiobg = make_bg_audio(bgbase=bgmusicclip, clip=mergedclip)
    finalaudio = CompositeAudioClip([audiomain, audiobg.volumex(bgaudiovolume)])

    mergedclip.audio = finalaudio
    mergedclip.write_videofile(general['id'] + ".mp4", fps=fps)


# essentially works like generate_clips() but doesn't require the reddit data
# dictionary to work (you can use an existing reddit video folder)
def generate_clips_folder_only(videopath):
    clips = []

    # generate clip for body
    bodymp3_path = videopath + "body/" + [each for each in os.listdir(videopath + "body/") if each.endswith('.mp3')][0]
    bodyimage_path = videopath + "body/" + [each for each in os.listdir(videopath + "body/") if each.endswith('.png')][0]

    bodyimage_audio = AudioFileClip(bodymp3_path)
    bodyimage = ImageClip(bodyimage_path).set_duration(bodyimage_audio.duration + wait_before_start)
    bodyimage.audio = bodyimage_audio

    bodyid = Path(bodyimage_path).stem

    # bodybg = videobgclip.subclip(0, limit_high(bodyimage.duration, videobgclip.duration))
    bodybg = make_bg_video(bgbase=videobgclip, clip=bodyimage)
    bodyimagefinal = CompositeVideoClip([bodybg, bodyimage.set_position("center")], size=res)

    clips.append(bodyimagefinal)

    for item in os.scandir(videopath + "comments/"):
        if item.is_dir():
            commentmp3_path = item.path + "/" + [each for each in os.listdir(item.path) if each.endswith('.mp3')][0]
            commentimage_path = item.path + "/" + [each for each in os.listdir(item.path) if each.endswith('.png')][0]

            commentimage_audio = AudioFileClip(commentmp3_path)
            commentimage = ImageClip(commentimage_path).\
                set_duration(commentimage_audio.duration + wait_between_comments)
            commentimage.audio = commentimage_audio

            # commentbg = videobgclip.subclip(0, limit_high(commentimage.duration, videobgclip.duration))
            commentbg = make_bg_video(bgbase=videobgclip, clip=commentimage)
            commentimagefinal = CompositeVideoClip([commentbg, commentimage.set_position("center")], size=res)

            clips.append(commentimagefinal)
            if enable_transitions:
                clips.append(videocensorclip)

    # remove the last beep from video
    # clips.pop(-1)

    mergedclip = concatenate_videoclips(clips=clips)
    audiomain = mergedclip.audio
    audiobg = make_bg_audio(bgbase=bgmusicclip, clip=mergedclip)
    finalaudio = CompositeAudioClip([audiomain, audiobg.volumex(bgaudiovolume)])

    mergedclip.audio = finalaudio
    mergedclip.write_videofile(bodyid + ".mp4", fps=fps)


if __name__ == '__main__':
    r_data = grab_reddit_data(submission_id=post_id, size=1)
    video_path = organize_work_directory(data=r_data)
    generate_clips_folder_only(videopath=video_path)
