from rest_framework import serializers


class TimestampField(serializers.Field):
    def to_representation(self, value):
        return int(value.timestamp())
