# import os
import storage as st
import slack_send as ss
import datetime
import schedule
import time
import logging

logger = logging.getLogger(__name__)


# Per datetime documentation, Monday is 0 and Sunday is 6
CHORE_DAY = 5  # Saturday
REMINDER_TIME = "18:00"


def remind_kitchen_cleaner(assignment: st.KitchenAssignment) -> None:
    ut = st.get_user_table()
    assignee = ut.get_user_by_name(assignment.name)
    if assignee is None:
        logger.error(f"No user corresponding to kitchen cleaning assignment: {assignment}")
        return
    logger.info(f"Reminding {assignee.name} to clean the kitchen today")
    disp_name = ss.get_user_display_name(assignee.slack_id)
    ss.msg_user(assignee.slack_id, f"Hello {disp_name}! Today is your day to clean the kitchen.",
                ignore_test_mode=True)


def remind_choredoers() -> None:
    ut = st.get_user_table()
    choredoers = (u for u in ut if st.UserRole.CHOREDOER in u.roles)
    for u in choredoers:
        # if it is a manager and not the last day of the month, continue
        today = datetime.date.today()
        next_week = today + datetime.timedelta(7)
        if st.UserRole.MANAGER in u.roles and today.month == next_week.month:
            continue

        logger.info(f"Reminding {u.name} to do their chore")
        disp_name = ss.get_user_display_name(u.slack_id)
        msg = f"Hello {disp_name}! This is a reminder to complete your chore by 10 PM today."
        try:
            ss.msg_user(u.slack_id, msg, ignore_test_mode=True)
        except Exception as e:
            logger.error(f"Failed to remind {u.name} to do their chore!")
            logger.error(e)


def run_reminders() -> None:
    today = datetime.datetime.today()
    day_of_month = today.day

    # Get the assigned kitchen cleaner for today, if any
    kat = st.get_kitchen_assignment_table()
    kitchen_assignment = kat.get_assignment_by_date(day_of_month)

    if kitchen_assignment is not None:
        # Send them a reminder
        remind_kitchen_cleaner(kitchen_assignment)

    # If it is chore day, send reminder to all choredoers
    day_of_week = today.weekday()
    if day_of_week == CHORE_DAY:
        remind_choredoers()


def reminder_thread() -> None:
    # Set up reminders
    logger.info(f"Current time is: {datetime.datetime.today()}")
    schedule.every().day.at(REMINDER_TIME).do(run_reminders)
    logger.info(f"Running reminders every day at {REMINDER_TIME}")

    while True:
        schedule.run_pending()
        time.sleep(1)


if __name__ == "__main__":
    run_reminders()
