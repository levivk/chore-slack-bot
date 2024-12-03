from . import helpers
from .. import storage as st
from slack_sdk.errors import SlackApiError
from slack_bolt.kwargs_injection import Args
import copy
from typing import Any
import logging

_logger = logging.getLogger(__name__)

VIEW_BASE = {
    "type": "home",
    "blocks": [
    ]
}

VIEW_ROLE_SELECT = {
    "type": "section",
    "block_id": "",
    "text": {
        "type": "plain_text",
        "text": ""
    },
    "accessory": {
        "type": "multi_static_select",
        "placeholder": {
            "type": "plain_text",
            "text": "Select roles",
        },
        "options": [
        ],
        "initial_options": [
        ],
        "action_id": "action-set-roles"
    }
}

VIEW_ROLE_OPTION = {
    "text": {
        "type": "plain_text",
        "text": "",
    },
    "value": ""
}


def act_roles_button(args: Args) -> None:
    """
    Trigger when the roles button is pressed to set user roles
    """

    id = helpers.id_from_args(args)

    view: dict[str, Any] = copy.deepcopy(VIEW_BASE)
    ut = st.get_user_table()

    # Create a block with a selection for each user
    for u in ut.keys():
        block: dict[str, Any] = copy.deepcopy(VIEW_ROLE_SELECT)
        block['text']['text'] = ut[u].name
        block['block_id'] = u

        # Create an option in the selection for each role
        for r in st.UserRole:
            option: dict[str, Any] = copy.deepcopy(VIEW_ROLE_OPTION)
            option['text']['text'] = r.name
            option['value'] = r.name
            block['accessory']['options'].append(option)

        # Preset the selection with current roles
        for r in ut[u].roles:
            option = copy.deepcopy(VIEW_ROLE_OPTION)
            option['text']['text'] = r.name
            option['value'] = r.name
            block['accessory']['initial_options'].append(option)

        # initial options cannot be empty
        if not block['accessory']['initial_options']:
            del block['accessory']['initial_options']

        view['blocks'].append(block)

    # sort blocks by name
    view['blocks'].sort(key=lambda b: b['text']['text'])

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


def act_roles_selection(args: Args) -> None:
    _logger.info(args.body)
