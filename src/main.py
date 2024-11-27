from reminder import reminder_thread
from slack_receive import start_server
from storage import init_storage
from admin_log import AdminLogHandler
import logging
import signal
from threading import Thread
from typing import Any


def main() -> None:

    # Handle signals
    def sigterm_handler(_signo: Any, _stack_frame: Any) -> None:
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, sigterm_handler)

    # TODO: init stream logging before this?
    init_storage()

    # Set up logging
    al = AdminLogHandler()
    al_fmtr = logging.Formatter('{levelname:<4.4}: {message}', style='{')
    al.setFormatter(al_fmtr)
    sh = logging.StreamHandler()
    sh_fmtr = logging.Formatter('[{levelname:<4.4}:{name:<10.10}] {message}', style='{')
    sh.setFormatter(sh_fmtr)

    logging.basicConfig(level=logging.INFO, handlers=[sh, al])

    # start reminder thread
    t = Thread(target=reminder_thread, daemon=True)
    t.start()

    # start slack server
    start_server()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info('Exiting...')
        logging.shutdown()
