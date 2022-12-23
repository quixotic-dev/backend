from rest_framework.pagination import PageNumberPagination
from collections import OrderedDict, namedtuple
from rest_framework.response import Response


class LightweightPageNumberPagination(PageNumberPagination):

    def get_paginated_response(self, data):
        return Response(OrderedDict([
            ('next', self.get_next_link()),
            ('previous', self.get_previous_link()),
            ('results', data)
        ]))
