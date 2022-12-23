from api.models import RewardsCampaign
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Refresh campaigns"

    def handle(self, *args, **kwargs):
        for campaign in RewardsCampaign.objects.all():
            self.stdout.write(f"Refreshing campaign for: {campaign.collection}")
            campaign.refresh_campaign()
