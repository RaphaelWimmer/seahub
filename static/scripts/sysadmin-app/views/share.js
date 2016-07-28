define([
    'jquery',
    'underscore',
    'backbone',
    'common',
    'sysadmin-app/views/folder-share-item'
], function($, _, Backbone, Common, FolderShareItemView) {
    'use strict';

    var SharePopupView = Backbone.View.extend({
        tagName: 'div',
        id: 'share-popup',
        template: _.template($('#share-popup-tmpl').html()),

        initialize: function(options) {
            this.repo_id = options.repo_id;
            this.repo_name = options.repo_name;

            this.render();

            this.$el.modal();
            $('#simplemodal-container').css({'width':'auto', 'height':'auto'});

            this.$("#share-tabs").tabs();

            this.dirUserSharePanelInit();
            this.dirGroupSharePanelInit();

            var _this = this;
            $(document).on('click', function(e) {
                var target = e.target || event.srcElement;
                if (!_this.$('.perm-edit-icon, .perm-toggle-select').is(target)) {
                    _this.$('.perm').removeClass('hide');
                    _this.$('.perm-toggle-select').addClass('hide');
                }
            });
        },

        render: function () {
            this.$el.html(this.template({
                title: gettext("Share {placeholder}")
                    .replace('{placeholder}', '<span class="op-target ellipsis ellipsis-op-target" title="' + Common.HTMLescape(this.repo_name) + '">' + Common.HTMLescape(this.repo_name) + '</span>'),
                repo_id: this.repo_id,
            }));

            return this;
        },

        events: {
            'click [type="checkbox"]': 'clickCheckbox',
            'click #add-dir-user-share-item .submit': 'dirUserShare',
            'click #add-dir-group-share-item .submit': 'dirGroupShare'
        },

        clickCheckbox: function(e) {
            var $el = $(e.currentTarget);
            // for link options such as 'password', 'expire'
            $el.closest('.checkbox-label').next().toggleClass('hide');
        },

        dirUserSharePanelInit: function() {
            var form = this.$('#dir-user-share');

            $('[name="emails"]', form).select2($.extend({
                //width: '292px' // the container will copy class 'w100' from the original element to get width
            },Common.contactInputOptionsForSelect2()));

            // show existing items
            var $add_item = $('#add-dir-user-share-item');
            var repo_id = this.repo_id;

            Common.ajaxGet({
                'get_url': Common.getUrl({name: 'admin_library_user_shares', repo_id: repo_id}),
                'after_op_success': function (data) {
                    $(data).each(function(index, item) {
                        var new_item = new FolderShareItemView({
                            'repo_id': repo_id,
                            'item_data': {
                                "user_email": item.user_email,
                                "user_name": item.user_name,
                                "permission": item.permission,
                                'for_user': true
                            }
                        });
                        $add_item.after(new_item.el);
                    });
                }
            });

            form.removeClass('hide');
            this.$('.loading-tip').hide();
        },

        dirGroupSharePanelInit: function() {
            var form = this.$('#dir-group-share');

            $('[name="groups"]', form).select2($.extend({
                //width: '292px' // the container will copy class 'w100' from the original element to get width
            },Common.groupInputOptionsForSelect2()));

            // show existing items
            var $add_item = $('#add-dir-group-share-item');
            var repo_id = this.repo_id;
            Common.ajaxGet({
                'get_url': Common.getUrl({name: 'admin_library_group_shares', repo_id: repo_id}),
                'after_op_success': function (data) {
                    $(data).each(function(index, item) {
                        var new_item = new FolderShareItemView({
                            'repo_id': repo_id,
                            'item_data': {
                                "group_id": item.group_id,
                                "group_name": item.group_name,
                                "permission": item.permission,
                                'for_user': false
                            }
                        });
                        $add_item.after(new_item.el);
                    });
                }
            });

            form.removeClass('hide');
            this.$('.loading-tip').hide();
        },

        dirUserShare: function () {
            var $panel = $('#dir-user-share');
            var $form = this.$('#add-dir-user-share-item'); // pseudo form

            var emails_input = $('[name="emails"]', $form),
                emails = emails_input.val(); // string
            if (!emails) {
                return false;
            }

            var $add_item = $('#add-dir-user-share-item');
            var repo_id = this.repo_id;
            var $perm = $('[name="permission"]', $form);
            var perm = $perm.val();
            var $error = $('.error', $panel);
            var $submitBtn = $('[type="submit"]', $form);

            Common.disableButton($submitBtn);
            $.ajax({
                url: Common.getUrl({name: 'admin_library_user_shares', repo_id: repo_id}),
                dataType: 'json',
                method: 'POST',
                beforeSend: Common.prepareCSRFToken,
                traditional: true,
                data: {
                    'email': emails.split(','),
                    'permission': perm
                },
                success: function(data) {
                    if (data.success.length > 0) {
                        $(data.success).each(function(index, item) {
                            var new_item = new FolderShareItemView({
                                'repo_id': repo_id,
                                'item_data': {
                                    "user_email": item.user_email,
                                    "user_name": item.user_name,
                                    "permission": item.permission,
                                    'for_user': true
                                }
                            });
                            $add_item.after(new_item.el);
                        });
                        emails_input.select2("val", "");
                        $('[value="rw"]', $perm).attr('selected', 'selected');
                        $('[value="r"]', $perm).removeAttr('selected');
                        $error.addClass('hide');
                    }
                    if (data.failed.length > 0) {
                        var err_msg = '';
                        $(data.failed).each(function(index, item) {
                            err_msg += Common.HTMLescape(item.user_email) + ': ' + item.error_msg + '<br />';
                        });
                        $error.html(err_msg).removeClass('hide');
                    }
                },
                error: function(xhr) {
                    var err_msg;
                    if (xhr.responseText) {
                        var parsed_resp = $.parseJSON(xhr.responseText);
                        err_msg = parsed_resp.error||parsed_resp.error_msg;
                    } else {
                        err_msg = gettext("Failed. Please check the network.")
                    }
                    $error.html(err_msg).removeClass('hide');
                },
                complete: function() {
                    Common.enableButton($submitBtn);
                }
            });
        },

        dirGroupShare: function () {
            var $panel = $('#dir-group-share');
            var $form = this.$('#add-dir-group-share-item'); // pseudo form

            var $groups_input = $('[name="groups"]', $form),
                groups = $groups_input.val(); // null or [group.id]

            if (!groups) {
                return false;
            }

            var $add_item = $('#add-dir-group-share-item');
            var repo_id = this.repo_id;
            var $perm = $('[name="permission"]', $form),
                perm = $perm.val();
            var $error = $('.error', $panel);
            var $submitBtn = $('[type="submit"]', $form);

            Common.disableButton($submitBtn);
            $.ajax({
                url: Common.getUrl({name: 'admin_library_group_shares',repo_id: repo_id}),
                dataType: 'json',
                method: 'POST',
                beforeSend: Common.prepareCSRFToken,
                traditional: true,
                data: {
                    'group_id': groups,
                    'permission': perm
                },
                success: function(data) {
                    if (data.success.length > 0) {
                        $(data.success).each(function(index, item) {
                            var new_item = new FolderShareItemView({
                                'repo_id': repo_id,
                                'item_data': {
                                    "group_id": item.group_id,
                                    "group_name": item.group_name,
                                    "permission": item.permission,
                                    'for_user': false
                                }
                            });
                            $add_item.after(new_item.el);
                        });
                        $groups_input.select2("val", "");
                        $('[value="rw"]', $perm).attr('selected', 'selected');
                        $('[value="r"]', $perm).removeAttr('selected');
                        $error.addClass('hide');
                    }
                    if (data.failed.length > 0) {
                        var err_msg = '';
                        $(data.failed).each(function(index, item) {
                            err_msg += Common.HTMLescape(item.group_name) + ': ' + item.error_msg + '<br />';
                        });
                        $error.html(err_msg).removeClass('hide');
                    }
                },
                error: function(xhr) {
                    var err_msg;
                    if (xhr.responseText) {
                        var parsed_resp = $.parseJSON(xhr.responseText);
                        err_msg = parsed_resp.error||parsed_resp.error_msg;
                    } else {
                        err_msg = gettext("Failed. Please check the network.")
                    }
                    $error.html(err_msg).removeClass('hide');
                },
                complete: function() {
                    Common.enableButton($submitBtn);
                }
            });
        }

    });

    return SharePopupView;
});
