import config
from vision import PhotoProcessor
from slack_bolt import App
from slack_bolt.context.say.say import Say
from slack_sdk import WebClient
from typing import Dict, Any
import requests

def handle_message(message: Dict[str, Any], say: Say, client: WebClient) -> None:
    print("Received message")
    ch_type: str = message["channel_type"]
    if ch_type == "im":
        handle_im(message, say, client)

def handle_im(message: Dict[str, Any], say: Say, client: WebClient) -> None:
    print("Received IM")
    # Try and handle file
    try:
        file = message['files'][0]
    except KeyError:
        pass
    else:
        handle_file(file, say, client)
        return

    # no file, give a cortial response
    say("Hello!!")

def handle_file(file: Dict[str, Any], say: Say, client: WebClient) -> None:
    print("Received file")
    # TODO: check user is Manager
    filetype = file['filetype']
    download_url = file['url_private']
    if filetype == 'jpg':
        # TODO
        handle_picture(download_url, say)
    else:
        say('What is this file thingy??')
    return

def handle_picture(url: str, say: Say) -> None:
    # download image
    header = {'Authorization':f'Bearer {config.get_slack_bot_token()}'}
    img_data = requests.get(url, headers=header).content
    # process picture
    phop = PhotoProcessor(img_data)
    right_buttons = phop.get_right_buttons()
    say(str(right_buttons))

    #   recieve picture, process picture
    #   ask user whether they would like to remind/scold/mark for fines based on time
    #   issue action, or not


def start_server() -> None:
    
    app = App(token=config.get_slack_bot_token(), signing_secret=config.get_slack_signing_secret())
    app.event({"type":"message"})(handle_message)
    app.start(port=3000)
