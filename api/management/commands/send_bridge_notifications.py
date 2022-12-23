import os
from datetime import datetime, timedelta, timezone

from api.models import BlockchainState, BridgedContract, Erc721Activity
from api.utils.constants import WEBSITE_URL
from django.core.management.base import BaseCommand
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Asm, From, GroupId, GroupsToDisplay, Mail, To


class Command(BaseCommand):
    help = "Send email notifications for bridged tokens that are ready to finalize"

    def handle(self, *args, **kwargs):
        last_check = BlockchainState.objects.get(key="bridge_notification_timestamp")
        last_check_timestamp = datetime.fromtimestamp(
            int(last_check.value), timezone.utc
        )
        current_timestamp = datetime.now(timezone.utc)

        lower_bound = last_check_timestamp - timedelta(days=7)
        upper_bound = current_timestamp - timedelta(days=7)

        activity = Erc721Activity.objects.filter(
            event_type_short="BR",
            to_profile__address="0x0000000000000000000000000000000000000000",
            timestamp__gt=lower_bound,
            timestamp__lte=upper_bound,
        )

        for act in activity:
            try:
                token = act.token
                user = act.from_profile
                if user.email:

                    l1_address = BridgedContract.objects.get(
                        to_contract=token.smart_contract
                    ).from_contract.address

                    message = Mail(
                        from_email=From("no-reply@quixotic.io", "Quix"),
                        to_emails=To(user.email),
                    )
                    message.dynamic_template_data = {
                        "item_name": token.name,
                        "item_link": f"{WEBSITE_URL}/bridge?address={l1_address}&token_id={token.token_id}&network=ethereum",
                        "image_link": token.image,
                        "unsubscribe_link": "<%a sm_group_unsubscribe_raw_url %>",
                    }

                    message.template_id = "d-7eb398546f7c4e75b88c56d6c25e4c1e"
                    message.asm = Asm(GroupId(17166), GroupsToDisplay([17166]))

                    try:
                        sg = SendGridAPIClient(os.environ.get("SENDGRID_API_KEY"))
                        response = sg.send(message)
                        print("Sent bridge notification email to " + user.email)
                    except Exception as e:
                        print(
                            "Error sending bridge notification email to " + user.email
                        )
                        print(e)
            except Exception as e:
                print(e)

        last_check.value = str(int(current_timestamp.timestamp()))
        last_check.save()
