from PIL import Image
from PIL import ImageDraw
from rake_nltk import Rake
import re
import random


# get the foundation of the thumbnail provided data (see main.py for what does "data" mean)
def get_basic_thumbnail(data):
    base = Image.open(data['thumbnail_data']['assets']['template_image'])

    overlayimage = ""
    if data['thumbnail_data']['assets']['overlay_image']:
        overlayimage = Image.open(data['thumbnail_data']['assets']['overlay_image'])
    else:
        overlayimage = Image.open(data['thumbnail_data']['assets']['default_overlay'])

    base.paste(overlayimage, data['thumbnail_data']['construction']['image_position'], overlayimage)
    return base


# returns a list of word-boolean pairs, along with some line-breaks.
# the boolean part indicates if the word should be marked with some color
# in the thumbnail or not
def get_thumbnail_text(text, font, data):
    # im writing this for my future self incase i put off this project
    # and decide to come back to it for some reason:

    # rake is an algorithm to find keywords in a text (in other words, important parts of a sentecne)

    r = Rake()
    r.extract_keywords_from_text(text=text)
    phrases = r.get_ranked_phrases()[:data['thumbnail_data']['font']['keyword_count']]

    # this method finds the ranking of each keyword (the keyword can be multiple words)
    # in order to determain which words need to be colored in the thumbnail
    #
    # if a word is paired with True, it should be colored
    # if with False, it shouldn't

    marked_phrases = []
    marked_words = []
    words = text.split()

    # some regex action to find the locations of the keywords in the original text
    for phrase in phrases:
        pattern = re.compile(r"\b{phrase}\b".format(phrase=phrase), flags=re.I)
        match = re.search(pattern, text)
        marked_phrases.append((phrase, (match.start(), match.end())))

    # a bit painful to read, but essentially it iterates over
    # every word in the original text, calculates its location
    # in the text, if the word starts at or after the beginning of a keyword
    # and also ends at or before the ending of a keyword it is part of that keyword, and it marks it
    # as "should be colored".
    letter_count = 0
    for word in words:
        for index, phrase in enumerate(marked_phrases):
            if letter_count >= phrase[1][0] and letter_count + len(word) <= phrase[1][1]:
                marked_words.append((word, True))
                break
            if index == len(marked_phrases) - 1:
                marked_words.append((word, False))

        letter_count += len(word)
        letter_count += 1

    new_word_list = []

    # iterates over the new list of marked_words, according to font and point size
    # it calculates where there should be line breaks and modifies the marked_words list
    # to account for line breaks
    currentline = ""
    for index, wordmark_pair in enumerate(marked_words):
        word = wordmark_pair[0]
        marked = wordmark_pair[1]

        new_word_list.append((word, marked))

        currentline += word
        size = font.getsize(currentline)

        if size[0] >= data['thumbnail_data']['font']['text_width']:
            new_word_list.append("\n")
            currentline = ""
            if new_word_list.count("\n") == data['thumbnail_data']['font']['number_of_lines']:
                if index != len(words) - 1:
                    new_word_list[-1] = "..."
                else:
                    new_word_list.pop(-1)
                break
        else:
            currentline += " "
    return new_word_list


# given an ImageDraw object and text_data which is
# retrived from def get_thumbnail_text() it writes the thumbnail text
# on the thumbnail
def draw_colored_text(image, text_data, data, font):
    draw = ImageDraw.Draw(image)

    space_size = font.getsize(" ")
    pos = data['thumbnail_data']['font']['position']
    start_x = pos[0]
    last_color = [255, 255, 255]

    was_recent_word_colored = False
    last_colored_word_color = random.choice(data['thumbnail_data']['font']['keyword_color'])

    for word in text_data:
        if word == "\n":
            pos = start_x, pos[1] + data['thumbnail_data']['font']['vertical_spacing']
        elif word == "...":
            draw.text(pos, "...", font=font, fill=tuple(last_color))
        else:
            word_content = word[0]
            word_is_colored = word[1]
            word_size = font.getsize(word_content)
            word_color = ""

            if word_is_colored:
                if was_recent_word_colored:
                    word_color = last_colored_word_color
                else:
                    was_recent_word_colored = True
                    word_color = random.choice(data['thumbnail_data']['font']['keyword_color'])
                    last_colored_word_color = word_color
            else:
                was_recent_word_colored = False
                word_color = data['thumbnail_data']['font']['color']

            draw.text(pos, word_content, font=font, fill=tuple(word_color))
            pos = pos[0] + word_size[0] + space_size[0], pos[1]

            last_color = word_color
