import config
from slack_bolt import App
from slack_bolt.context.say.say import Say
from slack_sdk import WebClient
from typing import Dict, Any

def handle_message(message: Dict[str, Any], say: Say, client: WebClient) -> None:
    ch_type: str = message["channel_type"]
    if ch_type == "im":
        handle_im(message, say, client)

def handle_im(message: Dict[str, Any], say: Say, client: WebClient) -> None:
    if "files" in message:
        handle_file(message, say, client)
    else:
        say("Hello!")

def handle_file(message: Dict[str, Any], say: Say, client: WebClient) -> None:
    # TODO: check user is Manager
    #   recieve picture, process picture
    #   ask user whether they would like to remind/scold/mark for fines based on time
    #   issue action, or not
    pass

def start_server() -> None:
    
    app = App(token=config.get_slack_bot_token(), signing_secret=config.get_slack_signing_secret())
    app.event({"type":"message"})(handle_message)
    app.start(port=3000)
