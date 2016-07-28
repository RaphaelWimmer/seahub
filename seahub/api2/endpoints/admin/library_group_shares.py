# Copyright (c) 2012-2016 Seafile Ltd.
import logging
from rest_framework import status
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from seaserv import seafile_api, ccnet_api

from seahub.api2.authentication import TokenAuthentication
from seahub.api2.throttling import UserRateThrottle
from seahub.api2.utils import api_error

from seahub.utils import send_perm_audit_msg
from seahub.share.signals import share_repo_to_group_successful

logger = logging.getLogger(__name__)

def get_library_group_share_info(share_item):
    result = {}
    group = ccnet_api.get_group(share_item.group_id)
    result['group_id'] = share_item.group_id
    result['group_name'] = group.group_name
    result['permission'] = share_item.perm
    result['repo_id'] = share_item.repo_id

    return result


class AdminLibraryGroupShares(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsAdminUser,)

    def get(self, request, repo_id):
        """ List all group shares of a repo

        Permission checking:
        1. admin user.
        """

        # resource check
        repo = seafile_api.get_repo(repo_id)
        if not repo:
            error_msg = 'Library %s not found.' % repo_id
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        repo_owner = seafile_api.get_repo_owner(repo_id)
        try:
            share_items = seafile_api.list_repo_shared_group_by_user(repo_owner, repo_id)
        except Exception as e:
            logger.error(e)
            error_msg = 'Internal Server Error'
            return api_error(status.HTTP_500_INTERNAL_SERVER_ERROR, error_msg)

        result = []
        for share_item in share_items:
            share_item_info = get_library_group_share_info(share_item)
            result.append(share_item_info)

        return Response(result)

    def post(self, request, repo_id):
        """ Admin share a library to group.

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
        username = request.user.username
        group_ids = request.data.getlist('group_id')

        for group_id in group_ids:
            try:
                group_id = int(group_id)
            except ValueError:
                error_msg = 'group_id %s invalid.' % group_id
                return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

            group = ccnet_api.get_group(group_id)
            if not group:
                error_msg = 'Group %s not found' % group_id
                return api_error(status.HTTP_404_NOT_FOUND, error_msg)

            try:
                seafile_api.set_group_repo(repo_id, group_id, username, permission)
            except Exception as e:
                logger.error(e)
                result['failed'].append({
                    'group_name': group.group_name,
                    'error_msg': 'Internal Server Error'
                    })
                continue

            share_repo_to_group_successful.send(sender=None,
                    from_user=username, group_id=group_id, repo=repo)

            send_perm_audit_msg('add-repo-perm', username, group_id,
                                repo_id, '/', permission)

            result['success'].append({
                "group_id": group_id,
                "group_name": group.group_name,
                "permission": permission
            })

        return Response(result)

class AdminLibraryGroupShare(APIView):
    authentication_classes = (TokenAuthentication, SessionAuthentication)
    throttle_classes = (UserRateThrottle,)
    permission_classes = (IsAdminUser,)

    def put(self, request, repo_id, format=None):
        """ Update library group share permission.

        Permission checking:
        1. admin user.
        """

        # argument check
        permission = request.data.get('permission', None)
        if not permission or permission not in ('r', 'rw'):
            error_msg = 'permission invalid.'
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        group_id = request.data.get('group_id', None)

        try:
            group_id = int(group_id)
        except ValueError:
            error_msg = 'group_id %s invalid.' % group_id
            return api_error(status.HTTP_400_BAD_REQUEST, error_msg)

        # resource check
        repo = seafile_api.get_repo(repo_id)
        if not repo:
            error_msg = 'Library %s not found.' % repo_id
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        group = ccnet_api.get_group(group_id)
        if not group:
            error_msg = 'Group %s not found' % group_id
            return api_error(status.HTTP_404_NOT_FOUND, error_msg)

        username = request.user.username
        seafile_api.set_group_repo_permission(group_id, repo.id, permission)
        send_perm_audit_msg('modify-repo-perm', username, group_id,
                            repo_id, '/', permission)

        return Response({'success': True})

    def delete(self, request, repo_id, format=None):
        """ Delete library group share permission.

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

        group_id = request.data.get('group_id')
        try:
            group_id = int(group_id)
        except ValueError:
            return api_error(status.HTTP_400_BAD_REQUEST, 'group_id %s invalid' % group_id)

        # hacky way to get group repo permission
        permission = ''
        repo_owner = seafile_api.get_repo_owner(repo_id)
        shared_groups = seafile_api.list_repo_shared_group(
                repo_owner, repo_id)

        for e in shared_groups:
            if e.group_id == group_id:
                permission = e.perm
                break

        username = request.user.username
        seafile_api.unset_group_repo(repo_id, group_id, username)

        send_perm_audit_msg('delete-repo-perm', username, group_id,
                            repo_id, '/', permission)

        return Response({'success': True})
