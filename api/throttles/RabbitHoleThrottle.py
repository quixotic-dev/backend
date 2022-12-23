from rest_framework.throttling import UserRateThrottle
import random


class RabbitHoleThrottle(UserRateThrottle):
    scope = 'rabbithole'
