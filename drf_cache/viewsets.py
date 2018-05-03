from rest_framework import mixins
from rest_framework.viewsets import GenericViewSet

from .mixins import CachedListModelMixin
from .mixins import CachedRetrieveModelMixin


class CachedReadOnlyModelViewSet(CachedRetrieveModelMixin, CachedListModelMixin, GenericViewSet):
    pass


class CachedModelViewSet(mixins.CreateModelMixin,
                         CachedRetrieveModelMixin,
                         mixins.UpdateModelMixin,
                         mixins.DestroyModelMixin,
                         CachedListModelMixin,
                         GenericViewSet):
    pass
