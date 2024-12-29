
from .. import storage as st
from ..slack_send import get_user_display_name
from . import helpers
from .set_kitchen_assignments import act_set_kitchen_assignments
from .set_roles import act_roles_button, act_roles_selection
from slack_sdk.errors import SlackApiError
from slack_sdk import WebClient
from slack_bolt.kwargs_injection import Args
import json
from string import Template
from typing import Dict, Any
import logging

_logger = logging.getLogger(__name__)


def handle_home_opened(client: WebClient, event: Dict[str, Any]) -> None:

    user_id = event["user"]
    # _logger.info(f"home opened by user {user_id}")

    ut = st.get_user_table()
    if st.UserRole.DEVELOPER in ut[user_id].roles:
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


def handle_block_action(args: Args) -> None:
    args.ack()

    act_map = {
        'home_set_roles': act_roles_button,
        'action-set-roles': act_roles_selection,
        'home_set_kitchen_assignments': act_set_kitchen_assignments
    }

    # get function from map
    action_id = args.body['actions'][0]['action_id']
    try:
        f = act_map[action_id]
    except KeyError:
        _logger.warn('Unhandled block action: ' + action_id)
        return

    # call function
    f(args)


def home_admin(client: WebClient, event: Dict[str, Any]) -> None:
    """
    send the admin home screen
    """

    # Get the payload
    template_str = helpers.get_payload('home_admin')
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
