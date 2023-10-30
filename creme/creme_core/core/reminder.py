################################################################################
#    Creme is a free/open-source Customer Relationship Management software
#    Copyright (C) 2009-2024  Hybird
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU Affero General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Affero General Public License for more details.
#
#    You should have received a copy of the GNU Affero General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
################################################################################

from __future__ import annotations

import logging
from datetime import datetime
from typing import Iterator

# from django.conf import settings
# from django.core.mail import EmailMessage, get_connection
from django.db.models.query_utils import Q
# from django.utils.timezone import now
# from django.utils.translation import gettext as _
from django.db.transaction import atomic

from ..constants import UUID_CHANNEL_REMINDERS
# from ..models import DateReminder, Job, JobResult
from ..models import CremeModel, CremeUser, Notification, NotificationChannel
from .notification import NotificationContent

logger = logging.getLogger(__name__)
FIRST_REMINDER = 1


class Reminder:
    id: str = ''  # Override with generate_id()
    model: type[CremeModel]  # Override with a CremeModel subclass

    # def __init__(self):
    #     pass

    @staticmethod
    def generate_id(app_name: str, name: str) -> str:
        return f'reminder_{app_name}-{name}'

    def get_users(self, instance: CremeModel) -> list[CremeUser]:
        raise NotImplementedError

    def get_notification_content(self, instance: CremeModel) -> NotificationContent:
        raise NotImplementedError

    # def get_emails(self, object) -> list[str]:
    #     addresses = []
    #     default_addr = getattr(settings, 'DEFAULT_USER_EMAIL', None)
    #
    #     if default_addr:
    #         addresses.append(default_addr)
    #     else:
    #         logger.critical(
    #             'Reminder: the setting DEFAULT_USER_EMAIL has not been filled ; '
    #             'no email will be sent.'
    #         )
    #
    #     return addresses

    # def generate_email_subject(self, object: CremeModel) -> str:
    #     pass

    # def generate_email_body(self, object: CremeModel) -> str:
    #     pass

    # TODO: get_queryset/get_instance_to_remind instead
    def get_Q_filter(self) -> Q:
        pass

    def ok_for_continue(self) -> bool:
        return True

    # def send_mails(self, instance: CremeModel, job: Job) -> bool:
    #     body    = self.generate_email_body(instance)
    #     subject = self.generate_email_subject(instance)
    #
    #     EMAIL_SENDER = settings.EMAIL_SENDER
    #     messages = [
    #         EmailMessage(subject, body, EMAIL_SENDER, [email])
    #         for email in self.get_emails(instance)
    #     ]
    #
    #     try:
    #         with get_connection() as connection:
    #             connection.send_messages(messages)
    #     except Exception as e:
    #         logger.critical('Error while sending reminder emails (%s)', e)
    #         JobResult.objects.create(
    #             job=job,
    #             messages=[
    #                 _('An error occurred while sending emails related to «{model}»').format(
    #                     model=self.model._meta.verbose_name,
    #                 ),
    #                 _('Original error: {}').format(e),
    #             ],
    #         )
    #
    #         return False
    #
    #     return True  # Means 'OK'

    # def execute(self, job: Job) -> None:
    def execute(self) -> None:
        if not self.ok_for_continue():
            return

        # dt_now = now().replace(microsecond=0, second=0)
        #
        # for instance in self.model.objects.filter(self.get_Q_filter()).exclude(reminded=True):
        #     self.send_mails(instance, job)
        #
        #     with atomic():
        #         DateReminder.objects.create(
        #             date_of_remind=dt_now,
        #             ident=FIRST_REMINDER,
        #             object_of_reminder=instance,
        #         )
        #
        #         instance.reminded = True
        #         instance.save()
        instances = self.model.objects.filter(self.get_Q_filter()).exclude(reminded=True)

        if instances:
            channel = NotificationChannel.objects.get_for_uuid(UUID_CHANNEL_REMINDERS)

            for instance in instances:
                with atomic():
                    Notification.objects.send(
                        channel=channel,
                        users=self.get_users(instance),
                        content=self.get_notification_content(instance),
                    )

                    instance.reminded = True
                    instance.save()

    def next_wakeup(self, now_value: datetime) -> datetime | None:
        """Returns the next time when the job manager should wake up in order
        to send the related emails.
        @param now_value: datetime object representing 'now'.
        @return None -> the job has not to be woken up.
                A datetime instance -> the job should be woken up at this time.
                    If it's in the past, it means the job should be run immediately
                    (tip: you can simply return now_value).
        """
        raise NotImplementedError


class ReminderRegistry:
    class RegistrationError(Exception):
        pass

    def __init__(self):
        self._reminders: dict[str, Reminder] = {}

    def register(self, reminder_class: type[Reminder]) -> ReminderRegistry:
        """Register a class of Reminder.
        @type reminder_class: Class "inheriting" <creme_core.core.reminder.Reminder>.
        """
        reminders = self._reminders
        reminder_id = reminder_class.id

        if not reminder_id:
            raise self.RegistrationError(
                f"Reminder class with empty id: {reminder_class}",
            )

        if reminder_id in reminders:
            raise self.RegistrationError(
                f"Duplicated reminder's id or reminder registered twice: {reminder_id}"
            )

        reminders[reminder_id] = reminder_class()

        return self

    def unregister(self, reminder_class: type[Reminder]) -> None:
        if self._reminders.pop(reminder_class.id, None) is None:
            raise self.RegistrationError(
                f'No reminder is registered with this ID: {reminder_class.id}'
            )

    def __iter__(self) -> Iterator[Reminder]:
        return iter(self._reminders.values())


reminder_registry = ReminderRegistry()
