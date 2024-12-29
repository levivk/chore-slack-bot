from . import helpers
from .. import storage as st
from slack_sdk.errors import SlackApiError
from slack_bolt.kwargs_injection import Args
import json
from pathlib import Path
import copy
from typing import Any
import logging

_logger = logging.getLogger(__name__)

VIEW_BASE = {
    "type": "home",
    "blocks": [
    ]
}

VIEW_ROLE_INPUT_BLOCK = {
    "type": "input",
    "block_id": "",
    "optional": True,
    "dispatch_action": True,
    "label": {
        "type": "plain_text",
        "text": ""
    },
    "element": {
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

    view: dict[str, Any] = copy.deepcopy(VIEW_BASE)
    ut = st.get_user_table()

    # Create list of options. One for each role.
    options = []
    for r in st.UserRole:
        option: dict[str, Any] = copy.deepcopy(VIEW_ROLE_OPTION)
        option['text']['text'] = r.name
        option['value'] = r.name
        options.append(option)

    # sort roles by name
    options.sort(key=lambda op: op['value'])

    # Create a block with a selection for each user
    for u in ut.keys():
        block: dict[str, Any] = copy.deepcopy(VIEW_ROLE_INPUT_BLOCK)
        block['label']['text'] = ut[u].name
        block['block_id'] = u

        # Same options for all users
        block['element']['options'] = options

        # Preset the selection with current roles
        for r in ut[u].roles:
            option = copy.deepcopy(VIEW_ROLE_OPTION)
            option['text']['text'] = r.name
            option['value'] = r.name
            block['element']['initial_options'].append(option)

        # initial options cannot be empty
        if not block['element']['initial_options']:
            del block['element']['initial_options']

        view['blocks'].append(block)

    # sort blocks by name
    view['blocks'].sort(key=lambda b: b['label']['text'])

    # send the payload
    id = helpers.id_from_args(args)
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
    p = (Path(__file__).parent / ("../../data/temp.json")).resolve()
    with open(p, 'w+') as fp:
        json.dump(args.body, fp)

    ut = st.get_user_table()
    # loop through changed settings
    for a in args.body['actions']:
        # Create a new role based on selected
        r = st.UserRole(0)
        for opt in a['selected_options']:
            r |= st.UserRole[opt['value']]

        # set role in db
        uid = a['block_id']
        ut[uid].roles = r
