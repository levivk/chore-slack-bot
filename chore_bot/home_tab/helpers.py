
from slack_bolt.kwargs_injection import Args
from pathlib import Path
import logging

_logger = logging.getLogger(__name__)


def id_from_args(args: Args) -> str:
    id = args.context.user_id
    if id is None:
        _logger.error("Args does not have a user ID!")
        _logger.info(args.body)
        return ''
    return id


def get_payload(file_name: str) -> str:
    json_file = (Path(__file__).parent / ("../../payloads/" + file_name + ".json")).resolve()
    with open(json_file, 'r') as f:
        json_str = f.read()
    return json_str
