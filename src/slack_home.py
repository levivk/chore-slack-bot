
import config
import storage as st
from slack_send import get_user_display_name
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient
from slack_bolt.kwargs_injection import Args
from slack_bolt import App
import json
from pathlib import Path
from string import Template
from typing import Dict, Any
import logging

_logger = logging.getLogger(__name__)


def get_payload(file_name: str) -> str:
    json_file = (Path(__file__).parent / ("../payloads/" + file_name + ".json")).resolve()
    with open(json_file, 'r') as f:
        json_str = f.read()
    return json_str


def home_admin(client: WebClient, event: Dict[str, Any]) -> None:
    """
    send the admin home screen
    """

    # Get the payload
    template_str = get_payload('home_admin')
    id = event["user"]
    name = get_user_display_name(id)
    t = Template(template_str)
    view = json.loads(t.substitute(name=name))

    # send the payload
    try:
        result = client.views_publish(
            user_id=id,
            view=view
        )

        if result["ok"] is not True:
            _logger.error(f"views_publish: {result}")

    except SlackApiError as e:
        _logger.error(f"Error publishing home tab for user {event['user']}: {e}")


def handle_home_opened(client: WebClient, event: Dict[str, Any]) -> None:

    user_id = event["user"]
    # _logger.info(f"home opened by user {user_id}")

    ut = st.get_user_table()
    if st.UserRole.ADMIN in ut[user_id].roles:
        home_admin(client, event)
        return

    try:
        result = client.views_publish(
            user_id=user_id,
            view={
                "type": "home",
                "callback_id": "home_view",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": "This is a test again :smile: :smile:"
                        }
                    }
                ]
            }
        )

        if result["ok"] is not True:
            _logger.error(f"views_publish: {result}")

    except SlackApiError as e:
        _logger.error(f"Error publishing home tab for user {event['user']}: {e}")

# class BlockAction():
#     """
#     Handle button actions
#     """


def handle_block_action(args: Args) -> None:
    args.ack()

    # get function by name
    action_id = args.body['actions'][0]['action_id']
    try:
        f = globals()['act_' + action_id]
    except KeyError:
        _logger.warn('Unhandled block action: ' + action_id)
        return

    # call function
    f(args)


def act_admin_home_roles(args: Args) -> None:
    _logger.info("rec roles button")
    # _logger.info(args.body)
    id = id_from_args(args)

    # Get the payload
    template_str = get_payload('roles_set')
    view = json.loads(template_str)
    # name = get_user_display_name(id)
    # t = Template(template_str)
    # view = json.loads(t.substitute(name=name))

    # send the payload
    try:
        result = args.client.views_publish(
            user_id=id,
            view=view
        )

        if result["ok"] is not True:
            _logger.error(f"views_publish: {result}")

    except SlackApiError as e:
        _logger.error(f"Error publishing home tab for user {id}: {e}")


def id_from_args(args: Args) -> str:
    id = args.context.user_id
    if id is None:
        _logger.error("Args does not have a user ID!")
        _logger.info(args.body)
        return ''
    return id


def act_admin_home_ka(args: Args) -> None:
    _logger.info("rec ka button")
