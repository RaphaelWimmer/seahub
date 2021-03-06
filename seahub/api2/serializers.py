# Copyright (c) 2012-2016 Seafile Ltd.
from rest_framework import serializers

from seahub.auth import authenticate
from seahub.api2.models import Token, TokenV2, DESKTOP_PLATFORMS
from seahub.api2.utils import get_token_v1, get_token_v2
from seahub.profile.models import Profile
from seahub.utils.two_factor_auth import has_two_factor_auth, two_factor_auth_enabled, verify_two_factor_token

def all_none(values):
    for value in values:
        if value is not None:
            return False

    return True

def all_not_none(values):
    for value in values:
        if value is None:
            return False

    return True

class AuthTokenSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    # There fields are used by TokenV2
    platform = serializers.CharField(required=False)
    device_id = serializers.CharField(required=False)
    device_name = serializers.CharField(required=False)

    # These fields may be needed in the future
    client_version = serializers.CharField(required=False, default='')
    platform_version = serializers.CharField(required=False, default='')

    def __init__(self, *a, **kw):
        super(AuthTokenSerializer, self).__init__(*a, **kw)
        self.two_factor_auth_failed = False

    def validate(self, attrs):
        login_id = attrs.get('username')
        password = attrs.get('password')

        platform = attrs.get('platform', None)
        device_id = attrs.get('device_id', None)
        device_name = attrs.get('device_name', None)
        client_version = attrs.get('client_version', None)
        platform_version = attrs.get('platform_version', None)

        v2_fields = (platform, device_id, device_name)

        # Decide the version of token we need
        if all_none(v2_fields):
            v2 = False
        elif all_not_none(v2_fields):
            v2 = True
        else:
            raise serializers.ValidationError('invalid params')

        username = Profile.objects.get_username_by_login_id(login_id)
        if username is None:
            username = login_id

        if username and password:
            user = authenticate(username=username, password=password)
            if user:
                if not user.is_active:
                    raise serializers.ValidationError('User account is disabled.')
            else:
                raise serializers.ValidationError('Unable to login with provided credentials.')
        else:
            raise serializers.ValidationError('Must include "username" and "password"')

        self._two_factor_auth(self.context['request'], username)

        # Now user is authenticated
        if v2:
            token = get_token_v2(self.context['request'], username, platform, device_id, device_name,
                                 client_version, platform_version)
        else:
            token = get_token_v1(username)
        return token.key

    def _two_factor_auth(self, request, username):
        if not has_two_factor_auth() or not two_factor_auth_enabled(username):
            return
        token = request.META.get('HTTP_X_SEAFILE_OTP', '')
        if not token:
            self.two_factor_auth_failed = True
            msg = 'Two factor auth token is missing.'
            raise serializers.ValidationError(msg)
        if not verify_two_factor_token(username, token):
            self.two_factor_auth_failed = True
            msg = 'Two factor auth token is invalid.'
            raise serializers.ValidationError(msg)

class AccountSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()
    is_staff = serializers.BooleanField(default=False)
    is_active = serializers.BooleanField(default=True)
