
# import os
from storage import user_table, UserRole, kitchen_assignment_table, KitchenAssignment
import slack_helpers as sh
import datetime
import logging
logger = logging.getLogger(__name__)


# Per datetime documentation, Monday is 0 and Sunday is 6
CHORE_DAY = 5   # Saturday


def remind_kitchen_cleaner(assignment: KitchenAssignment) -> None:
    assignee = user_table.get_user_by_name(assignment.name)
    if assignee is None:
        logger.error(f'No user corresponding to kitchen cleaning assignment: {assignment}')
        return
    logger.info(f'Reminding {assignee.name} to clean the kitchen today')
    disp_name = sh.get_user_display_name(assignee.slack_id)
    sh.msg_user(assignee.slack_id, f'Hello {disp_name}! Today is your day to clean the kitchen.')


def remind_choredoers() -> None:
    choredoers = (u for u in user_table if UserRole.CHOREDOER in u.roles)
    for u in choredoers:
        # if it is a manager and not the last day of the month, continue
        today = datetime.date.today()
        next_week = today + datetime.timedelta(7)
        if UserRole.MANAGER in u.roles and today.month == next_week.month:
            continue

        logger.info(f'Reminding {u.name} to do their chore')
        disp_name = sh.get_user_display_name(u.slack_id)
        msg = f'Hello {disp_name}! This is a reminder to complete your chore by 10 PM today.'
        try:
            sh.msg_user(u.slack_id, msg)
        except Exception as e:
            logger.error(f'Failed to remind {u.name} to do their chore!')
            logger.error(e)

def run_reminders() -> None:

    today = datetime.datetime.today()
    day_of_month = today.day

    # Get the assigned kitchen cleaner for today, if any
    kitchen_assignment = kitchen_assignment_table.get_assignment_by_date(day_of_month)

    if kitchen_assignment is not None:
        # Send them a reminder
        remind_kitchen_cleaner(kitchen_assignment)

    # If it is chore day, send reminder to all choredoers
    day_of_week = today.weekday()
    if day_of_week == CHORE_DAY:
        remind_choredoers()



if __name__ == '__main__':
    run_reminders()
