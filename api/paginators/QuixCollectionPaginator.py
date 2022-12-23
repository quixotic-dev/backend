from rest_framework import pagination
from rest_framework.response import Response
from collections import OrderedDict
from django.conf import settings
from django.core import cache

class QuixCollectionPaginator(pagination.LimitOffsetPagination):

    # def get_count(self, queryset):
    #     """
    #     Overrides get_count query because it's expensive.
    #     """
    #     return queryset[:500].count()

    def paginate_queryset(self, queryset, request, view=None):
        self.limit = self.get_limit(request)
        if self.limit is None:
            return None

        self.count = self.get_count(queryset)
        self.offset = self.get_offset(request)
        self.request = request
        if self.count > self.limit and self.template is not None:
            self.display_page_controls = True

        if self.count == 0 or self.offset > self.count:
            return []
        return list(queryset[self.offset:self.offset + self.limit])

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('count', self.count),
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))
