# Copyright (c) 2012-2016 Seafile Ltd.
import logging
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from seaserv import seafile_api

from seahub.api2.authentication import TokenAuthentication
from seahub.api2.throttling import UserRateThrottle
from seahub.api2.utils import api_error

from seahub.base.accounts import User
from seahub.base.templatetags.seahub_tags import email2nickname

from seahub.utils import (is_valid_username, send_perm_audit_msg)
from seahub.share.signals import share_repo_to_user_successful

logger = logging.getLogger(__name__)

def get_library_user_share_info(share_item):
    result = {}
    result['user_email'] = share_item.user
    result['user_name'] = email2nickname(share_item.user)
    result['permission'] = share_item.perm
    result['repo_id'] = share_item.repo_id

    return result


class AdminLibraryUserShares(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsAdminUser,)

    def get(self, request, repo_id):
        """ List all user shares of a repo

        Permission checking:
        1. admin user.
        """

        # resource check
        repo = seafile_api.get_repo(repo_id)
        if not repo:
            error_msg = 'Library %s not found.' % repo_id
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        # current `request.user.username` is admin user,
        # so need to identify the repo owner specifically.
        repo_owner = seafile_api.get_repo_owner(repo_id)
        try:
            share_items = seafile_api.list_repo_shared_to(repo_owner, repo_id)
        except Exception as e:
            logger.error(e)
            error_msg = 'Internal Server Error'
            return api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, error_msg)

        result = []
        for share_item in share_items:
            share_item_info = get_library_user_share_info(share_item)
            result.append(share_item_info)

        return Response(result)

    def post(self, request, repo_id):
        """ Admin share a library to user.

        Permission checking:
        1. admin user.
        """

        # argument check
        permission = request.data.get('permission', None)
        if not permission or permission not in ('r', 'rw'):
            error_msg = 'permission invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        # resource check
        repo = seafile_api.get_repo(repo_id)
        if not repo:
            error_msg = 'Library %s not found.' % repo_id
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        result = {}
        result['failed'] = []
        result['success'] = []
        share_to_users = request.data.getlist('email')

        # current `username` is admin user
        username = request.user.username
        repo_owner = seafile_api.get_repo_owner(repo_id)

        for to_user in share_to_users:
            if repo_owner == to_user:
                result['failed'].append({
                    'user_email': to_user,
                    'error_msg': 'email %s is library owner.' % to_user
                    })
                continue

            if not is_valid_username(to_user):
                result['failed'].append({
                    'user_email': to_user,
                    'error_msg': 'email %s invalid.' % to_user
                    })
                continue

            try:
                User.objects.get(email=to_user)
            except User.DoesNotExist:
                result['failed'].append({
                    'user_email': to_user,
                    'error_msg': 'User %s not found.' % to_user
                    })
                continue

            try:
                seafile_api.share_repo(repo_id,
                        username, to_user, permission)

                # send a signal when sharing repo successful
                share_repo_to_user_successful.send(sender=None,
                        from_user=username, to_user=to_user, repo=repo)

                result['success'].append({
                    "repo_id": repo_id,
                    "user_email": to_user,
                    "user_name": email2nickname(to_user),
                    "permission": permission
                })

                send_perm_audit_msg('add-repo-perm', username,
                        to_user, repo_id, '/', permission)
            except Exception as e:
                logger.error(e)
                result['failed'].append({
                    'user_email': to_user,
                    'error_msg': 'Internal Server Error'
                    })
                continue

        return Response(result)

class AdminLibraryUserShare(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsAdminUser,)

    def put(self, request, repo_id, format=None):
        """ Update library user share permission.

        Permission checking:
        1. admin user.
        """

        # argument check
        permission = request.data.get('permission', None)
        if not permission or permission not in ('r', 'rw'):
            error_msg = 'permission invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        to_user = request.data.get('user_email', None)
        if not to_user or not is_valid_username(to_user):
            error_msg = 'user_email invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        # resource check
        repo = seafile_api.get_repo(repo_id)
        if not repo:
            error_msg = 'Library %s not found.' % repo_id
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        try:
            User.objects.get(email=to_user)
        except User.DoesNotExist:
            error_msg = 'User %s not found.' % to_user
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        username = request.user.username

        try:
            seafile_api.set_share_permission(
                    repo_id, username, to_user, permission)
        except Exception as e:
            logger.error(e)
            error_msg = 'Internal Server Error'
            return api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, error_msg)

        send_perm_audit_msg('modify-repo-perm', username,
                to_user, repo_id, '/', permission)

        return Response({'success': True})

    def delete(self, request, repo_id, format=None):
        """ Delete library user share permission.

        Permission checking:
        1. admin user.
        """

        # argument check
        permission = request.data.get('permission', None)
        if not permission or permission not in ('r', 'rw'):
            error_msg = 'permission invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        to_user = request.data.get('user_email', None)
        if not to_user or not is_valid_username(to_user):
            error_msg = 'user_email invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        # resource check
        repo = seafile_api.get_repo(repo_id)
        if not repo:
            error_msg = 'Library %s not found.' % repo_id
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        username = request.user.username
        try:
            seafile_api.remove_share(repo_id, username, to_user)
        except Exception as e:
            logger.error(e)
            error_msg = 'Internal Server Error'
            return api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, error_msg)

        send_perm_audit_msg('delete-repo-perm', username,
                to_user, repo_id, '/', permission)

        return Response({'success': True})
