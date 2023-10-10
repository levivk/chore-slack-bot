from reminder import run_reminders
from admin_log import AdminLogHandler
import schedule
import time
from datetime import datetime
import logging
import signal
from typing import Any

REMINDER_TIME = '18:00'

def main() -> None:

    # Handle signals
    def sigterm_handler(_signo: Any, _stack_frame: Any) -> None:
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, sigterm_handler)

    # Set up logging
    al = AdminLogHandler()
    al_fmtr = logging.Formatter('{levelname:<4.4}: {message}', style='{')
    al.setFormatter(al_fmtr)
    sh = logging.StreamHandler()
    sh_fmtr = logging.Formatter('[{levelname:<4.4}:{name:<10.10}] {message}', style='{')
    sh.setFormatter(sh_fmtr)

    logging.basicConfig(level=logging.INFO, handlers=[sh, al])
    logger = logging.getLogger(__name__)

    # Set up reminders
    logger.info(f'Current time is: {datetime.today()}')
    schedule.every().day.at(REMINDER_TIME).do(run_reminders)
    logger.info(f'Running reminders every day at {REMINDER_TIME}')

    while True:
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logging.info('Exiting...')
        logging.shutdown()
