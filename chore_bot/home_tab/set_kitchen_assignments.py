
from slack_bolt.kwargs_injection import Args
import logging
_logger = logging.getLogger(__name__)


def act_set_kitchen_assignments(args: Args) -> None:
    _logger.info("rec ka button")
