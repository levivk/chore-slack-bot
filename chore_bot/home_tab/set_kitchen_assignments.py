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

VIEW_ROLE_ACTION_BLOCK = {
    "type": "actions",
    "elements": [
        {
            "type": "static_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Select date",
            },
            "options": [
            ],
            "initial_option": {
            }
        },
        {
            "type": "static_select",
            "placeholder": {
                "type": "plain_text",
                "text": "Select person",
            },
            "options": [
            ],
            "initial_option": {
            }
        }
    ]
}

VIEW_OPTION = {
    "text": {
        "type": "plain_text",
        "text": "",
    },
    "value": ""
}


def act_set_kitchen_assignments(args: Args) -> None:

    view: dict[str, Any] = copy.deepcopy(VIEW_BASE)

    # Create list of dates
    date_options = []
    for i in range(31):
        option: dict[str, Any] = copy.deepcopy(VIEW_OPTION)
        option['text']['text'] = str(i)
        option['value'] = str(i)
        date_options.append(option)

    kat = st.get_kitchen_assignment_table()
    ut = st.get_user_table()
    # Create list of users
    user_options = []
    for a in kat:
        if a.date is None:
            option = copy.deepcopy(VIEW_OPTION)
            option['text']['text'] = ut[a.id].name
            option['value'] = a.id
            user_options.append(option)

    # TODO add the above to block in view and see if this will work

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
