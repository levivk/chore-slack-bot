import config
from vision import PhotoProcessor
from storage import kitchen_assignment_table, user_table, UserRole, User
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
    left_buttons = phop.get_left_buttons()
    right_buttons = phop.get_right_buttons()
    kitchen_complete_names = [kitchen_assignment_table[i].name for i in left_buttons]
    chore_complete_names = [kitchen_assignment_table[i].name for i in right_buttons]
    text = "Kitchen completed by " + ",".join(kitchen_complete_names) + "\n"
    text += "Chore completed by " + ",".join(chore_complete_names) + "\n"
    say(text)

    chore_missers: list[User] = []
    for i, ka in enumerate(kitchen_assignment_table):
        chore_complete = i in right_buttons
        user = user_table.get_user_by_name(ka.name)
        user_roles = user.roles
        is_manager = UserRole.MANAGER in user_roles
        is_choredoer = UserRole.CHOREDOER in user_roles

        # TODO: check date to see what chore status should be
        # Record status in table
        # Send reminder to incompletes
        # Refactor this to be in another file
        if is_choredoer and not chore_complete and not is_manager:
            chore_missers.append(user)
        
    say("chore missers: \n" + "\n".join([u.name for u in chore_missers]))


    #   recieve picture, process picture
    #   ask user whether they would like to remind/scold/mark for fines based on time
    #   issue action, or not


def start_server() -> None:
    
    app = App(token=config.get_slack_bot_token(), signing_secret=config.get_slack_signing_secret())
    app.event({"type":"message"})(handle_message)
    app.start(port=3000)
