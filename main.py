import pyttsx3
import praw
import json
import os
import shutil
from time import sleep
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException


credentials = json.load(open('config.json'))
engine = pyttsx3.init()


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


def organize_work_directory(submission_id):
    cwd = os.getcwd()
    basepath = cwd + "/videos/"

    data = grab_reddit_data(submission_id=submission_id, size=5)
    general = data['general']
    comment_data = data['comment_data']

    # creating all needed folders
    mkdir_ifnotexist(cwd + "/videos")

    mkdir_ifnotexist(basepath + general['id'])
    videopath = basepath + general['id'] + "/"

    mkdir_ifnotexist(videopath + "screenshots/")
    success = screenshot_thread(data=data, wrkdir=videopath + "screenshots/", headless=True)

    if success:
        print("success!")
    else:
        print(":(")

    mkdir_ifnotexist(videopath + "/body/")
    shutil.copy\
        (
            videopath + "screenshots/" + general['id'] + ".png",
            videopath + "body/"
        )
    engine.save_to_file(general['title'], videopath + "body/" + general['id'] + ".mp3")
    engine.runAndWait()

    mkdir_ifnotexist(videopath + "clips/")
    mkdir_ifnotexist(videopath + "comments/")

    # Here should come the text-to-speech generation of the post's body
    # . . .

    for comment in comment_data:
        dest = videopath + "comments/" + comment['id']
        src = videopath + "screenshots/" + comment['id'] + ".png"

        mkdir_ifnotexist(dest)
        shutil.copy(src, dest)

        engine.save_to_file(comment['body'], dest + "/" + comment['id'] + ".mp3")
        engine.runAndWait()


organize_work_directory('lhxkmf')
