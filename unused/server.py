# https://slack.dev/bolt-python/tutorial/getting-started-http

import os
from slack_bolt import App
from slack_bolt.context.say.say import Say
import requests
import pprint
from vision import PhotoProcessor
from payloads import Payloads
pp = pprint.PrettyPrinter(indent=4)

payloads = Payloads()

# Initialize slack app
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Listens to incoming messages that contain "hello"
# To learn available listener arguments,
# visit https://slack.dev/bolt-python/api-docs/slack_bolt/kwargs_injection/args.html
# @app.message("hello")
# def message_hello(message, say):
#     # say() sends a message to the channel where the event was triggered
#     say(f"Hey there <@{message['user']}>!")

def handle_picture(url: str, say: Say) -> None:
    # Download image
    header = {'Authorization':f'Bearer {os.environ.get("SLACK_BOT_TOKEN")}'}
    img_data = requests.get(url, headers=header).content
    # process image
    phop = PhotoProcessor(img_data)
    right_buttons = phop.get_right_buttons()
    say(str(right_buttons))


@app.event({'type':'message', 'channel_type':'im'})
def handle_message_events(body, logger, message, say):
    # Someone sent a DM. 
    logger.info(body)

    # Check if it is a picture.
    try:
        filetype = message['files'][0]['filetype']
        download_url = message['files'][0]['url_private']
    except KeyError:
        pass
    else:
        if filetype == 'jpg':
            handle_picture(download_url, say)
        else:
            say('What is this file thingy??')
        return

    # Check if it is text
    try:
        msg = message['blocks'][0]['elements'][0]['elements'][0]['text']
    except:
        say('Huh?')
        pass
    else:
        # This is text
        if any(i in msg for i in ('hi', 'hello', '.')):
            say(blocks=payloads.get_what_do_blocks())
            print('sent what_do payload')
        else:
            say(f'You said "{msg}"')

    pp.pprint(message)
    print()
    # pp.pprint(message)
    # say(f"Hey there <@{message['user']}>!")


@app.action({'type':'block_actions','action_id':"name-order"})
def handle_action(ack, body):
    print('pre-action!')
    ack()
    print('action!')
    pp.pprint(body)
    # client.chat_update

# Start your app
if __name__ == "__main__":
    app.start(port=8081)


# bad guide: https://python.plainenglish.io/lets-create-a-slackbot-cause-why-not-2972474bf5c1
# question following bad guide: https://stackoverflow.com/questions/74482489/slack-bolt-send-response-when-button-is-clicked-app-has-not-been-configured
# undocumented enpoints: https://stackoverflow.com/questions/59175223/unable-to-detect-action-from-multi-user-select-using-slack-bolt
