import json
import codecs
from functools import partial

from django.conf import settings
from django.core.cache import caches
from django.db.models.signals import post_save
from django.db.models.signals import post_delete
from django.db.models.signals import m2m_changed

from rest_framework.serializers import ModelSerializer

from .signals import handle_change
from .signals import handle_delete


class SerializedModelCache:
    # Required
    serializer_class = None

    # Optional
    lookup_field = 'pk'
    key_prefix = ''
    compress_data = True

    # Django cache attributes (optional)
    backend = 'default'
    version = 1
    timeout = None

    # Automatically populated
    model = None

    def __init_subclass__(cls, **kwargs):
        if cls.__name__ == 'SerializedModelCacheWithIndexes':
            return

        assert not isinstance(cls.serializer_class, ModelSerializer), \
            f'"serializer_class" attribute must be an subclass of rest_framework.serializers.ModelSerializer'
        assert isinstance(cls.key_prefix, str), '"key_prefix" attribute must be a string'
        assert isinstance(cls.lookup_field, str), '"lookup_field" attribute must be a string'

        cache_settings = getattr(settings, 'CACHES')
        assert cache_settings and cls.backend in cache_settings, f'"{cls.backend}" is not a django cache backend'

        cls.model = cls.serializer_class.Meta.model

    @property
    def cache(self):
        return caches[self.backend]

    def compress_value(self, value):
        if not self.compress_data:
            return value

        value = json.dumps(value, separators=(',', ':'))
        return codecs.encode(value.encode('utf-8'), encoding='zlib')

    def decompress_value(self, value):
        if not self.compress_data:
            return value

        if value is None:
            return None

        value = codecs.decode(value, encoding='zlib')
        return json.loads(value, encoding='utf-8')

    def get_lookup_value(self, instance):
        return getattr(instance, self.lookup_field)

    def make_key(self, lookup_value, suffix=''):
        return f'{self.key_prefix}{self.__class__.__name__}:{lookup_value}{suffix}'

    def get(self, lookup_value, key_suffix=''):
        key = self.make_key(lookup_value, suffix=key_suffix)
        data = self.cache.get(key, version=self.version)
        return self.decompress_value(data)

    def set_data(self, instance, data, key_suffix=''):
        lookup_value = self.get_lookup_value(instance)
        compressed_data = self.compress_value(data)
        key = self.make_key(lookup_value, suffix=key_suffix)
        self.cache.set(key, compressed_data, timeout=self.timeout, version=self.version)

    def set(self, instance, key_suffix=''):
        data = self.serializer_class(instance=instance).data
        self.set_data(instance, data, key_suffix=key_suffix)

        return data

    def delete(self, instance, key_suffix=''):
        lookup_value = self.get_lookup_value(instance)
        key = self.make_key(lookup_value, suffix=key_suffix)

        return self.cache.delete_pattern(key + '*', version=self.version)

    def populate(self, key_suffix='', **filter_kwargs):
        for instance in self.model.objects.filter(**filter_kwargs):
            self.set(instance, key_suffix=key_suffix)

    @classmethod
    def register_signals(cls):
        handle_change_for_cache = partial(handle_change, cache_class=cls)
        handle_delete_for_cache = partial(handle_delete, cache_class=cls)

        post_save.connect(handle_change_for_cache, sender=cls.model)
        post_delete.connect(handle_delete_for_cache, sender=cls.model)

    @classmethod
    def register_signal_for_m2m(cls, m2m_field_name):
        handle_change_for_cache = partial(handle_change, cache_class=cls)
        m2m_model = getattr(cls.model, m2m_field_name).through
        m2m_changed.connect(handle_change_for_cache, sender=m2m_model)


class SerializedModelCacheWithIndexes(SerializedModelCache):
    indexes = ()  # list or tuple of pairs (index_name, index_value_getter), where index_value_getter
    # is a function that takes an instance and returns a list of index values that point to this instance
    index_names = ()  # list of index names for this cache, this is automatically populated from indexes

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        index_names = []
        for index_name, index_value_getter in cls.indexes:
            assert isinstance(index_name, str), '"index_name" must be a string'
            assert callable(index_value_getter), '"index_name" must be a callable'
            index_names.append(index_name)

        cls.index_names = tuple(index_names)

    def make_index_key(self, index_name, index_value):
        return f'{self.key_prefix}{self.__class__.__name__}:i:{index_name}:{index_value}'

    def get_index_keys(self, instance):
        for index_name, index_value_getter in self.indexes:
            index_values = index_value_getter(instance)

            for index_value in index_values:
                yield self.make_index_key(index_name, index_value)

    def set_indexes(self, instance):
        lookup_value = self.get_lookup_value(instance)
        for index_key in self.get_index_keys(instance):
            self.cache.set(index_key, lookup_value, version=self.version)

    def get_for_index(self, index_name, index_value, key_suffix=''):
        assert index_name in self.index_names, f'"{index_name}" is not a valid index_name'
        index_key = self.make_index_key(index_name, index_value)
        lookup_value = self.cache.get(index_key, version=self.version)

        if lookup_value is None:
            return None

        key = self.make_key(lookup_value, suffix=key_suffix)
        data = self.cache.get(key, version=self.version)
        return self.decompress_value(data)

    def set_data(self, instance, data, key_suffix=''):
        super().set_data(instance, data, key_suffix=key_suffix)
        self.set_indexes(instance)

    def delete(self, instance, key_suffix=''):
        for index_key in self.get_index_keys(instance):
            self.cache.delete(index_key)

        return super().delete(instance, key_suffix=key_suffix)

    def delete_index(self, index_name, index_value):
        index_key = self.make_index_key(index_name, index_value)
        self.cache.delete(index_key)
