from rest_framework import mixins
from rest_framework.response import Response

from .caches import SerializedModelCache
from .caches import SerializedModelCacheWithIndexes


class CachedMixin:
    cache_class = None

    def __init_subclass__(cls, **kwargs):
        if cls.__name__ in ['CachedRetrieveModelMixin', 'CachedListModelMixin', 'CachedIndexedRetrieveModelMixin']:
            return
        assert issubclass(cls.cache_class, SerializedModelCache), \
            '"cache_class" has to be set and a subclass of "SerializedModelCache"'
        assert cls.cache_class.lookup_field == cls.lookup_field, \
            '"lookup_field" of the "cache_class" and viewset must be the same'
        assert cls.cache_class.serializer_class == cls.serializer_class, \
            '"cache_class.serializer_class" and "serializer_class" must be the same'

    @property
    def lookup_field_name(self):
        return self.lookup_url_kwarg or self.lookup_field

    def get_cache(self, *args, **kwargs):
        return self.cache_class()

    def get_cache_key_suffix(self, *args, **kwargs):
        return ''

    def cache_instance(self, instance):
        return True

    def process_data(self, data):
        """Hook for doing something with the data before returning it"""
        return data

    def get_and_cache_data(self, instance, cache, key_suffix):
        if self.cache_instance(instance):
            return cache.set(instance, key_suffix=key_suffix)
        else:
            return self.get_serializer(instance).data

    def get_from_cache(self, cache, lookup_value, key_suffix=''):
        if self.request.query_params.get('refresh_cache'):
            return None  # Force cache refresh

        return cache.get(lookup_value, key_suffix=key_suffix)

    def get_lookup_value(self):
        # Get the name of the lookup parameter.
        lookup_url_kwarg = self.lookup_field_name

        assert lookup_url_kwarg in self.kwargs, (
            'Expected view %s to be called with a URL keyword argument '
            'named "%s". Fix your URL conf, or set the `.lookup_field` '
            'attribute on the view correctly.' %
            (self.__class__.__name__, lookup_url_kwarg)
        )

        return self.kwargs[lookup_url_kwarg]


class CachedRetrieveModelMixin(mixins.RetrieveModelMixin, CachedMixin):

    def retrieve(self, request, *args, **kwargs):
        lookup_value = self.get_lookup_value()
        cache = self.get_cache(*args, **kwargs)
        key_suffix = self.get_cache_key_suffix(*args, **kwargs)

        data = self.get_from_cache(cache, lookup_value, key_suffix=key_suffix)

        if data is None:
            instance = self.get_object()
            data = self.get_and_cache_data(instance, cache, key_suffix)

        return Response(self.process_data(data))


class CachedIndexedRetrieveModelMixin(CachedRetrieveModelMixin):
    cache_index = None

    def __init_subclass__(cls, **kwargs):
        if cls.cache_index is None:
            cls.cache_index = cls.lookup_field

        assert issubclass(cls.cache_class, SerializedModelCacheWithIndexes), \
            '"cache_class" must be a subclass of SerializedModelCacheWithIndexes'
        assert cls.cache_index in cls.cache_class.index_names, \
            '"cache_index" must be an index_field of the cache'
        assert cls.cache_class.serializer_class == cls.serializer_class, \
            '"cache_class.serializer_class" and "serializer_class" must be the same'

    def get_from_cache(self, cache, lookup_value, key_suffix=''):
        if self.request.query_params.get('refresh_cache'):
            return None  # Force cache refresh

        return cache.get_for_index(self.cache_index, lookup_value, key_suffix=key_suffix)


class CachedListModelMixin(mixins.ListModelMixin, CachedMixin):

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        cache = self.get_cache(*args, **kwargs)
        key_suffix = self.get_cache_key_suffix(*args, **kwargs)

        page = self.paginate_queryset(queryset.values_list(self.lookup_field, flat=True))
        if page is not None:
            results = []
            cache_miss_indexes, cache_misses = [], []

            for index, lookup_value in enumerate(page):
                data = cache.get(lookup_value, key_suffix=key_suffix)
                if data is None:
                    cache_misses.append(lookup_value)
                    cache_miss_indexes.append(index)
                else:
                    data = self.process_data(data)
                results.append(data)

            filter_kwargs = {self.lookup_field_name + '__in': cache_misses}
            for index, instance in zip(cache_miss_indexes, queryset.filter(**filter_kwargs)):
                data = self.get_and_cache_data(instance, cache, key_suffix)
                results[index] = self.process_data(data)  # TODO: check if this preserves order

            return self.get_paginated_response(results)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)
