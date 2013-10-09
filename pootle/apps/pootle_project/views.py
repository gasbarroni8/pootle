#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2008-2013 Zuza Software Foundation
# Copyright 2013 Evernote Corporation
#
# This file is part of Pootle.
#
# Pootle is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import locale

from django import forms
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.translation import ugettext as _

from pootle.core.decorators import get_path_obj, permission_required
from pootle.core.helpers import (get_export_view_context,
                                 get_overview_context,
                                 get_translation_context)
from pootle.core.url_helpers import split_pootle_path
from pootle_app.views.admin import util
from pootle_app.views.admin.permissions import admin_permissions
from pootle_language.models import Language
from pootle_misc.browser import (make_language_item,
                                 make_project_list_item,
                                 get_table_headings)
from pootle_misc.forms import LiberalModelChoiceField
from pootle_project.models import Project
from pootle_translationproject.models import TranslationProject


@get_path_obj
@permission_required('view')
def overview(request, project):
    """page listing all languages added to project"""
    translation_projects = project.translationproject_set.all()

    items = [make_language_item(translation_project)
             for translation_project in translation_projects.iterator()]
    items.sort(lambda x, y: locale.strcoll(x['title'], y['title']))

    table_fields = ['name', 'progress', 'total', 'need-translation',
                    'suggestions', 'critical', 'activity']
    table = {
        'id': 'project',
        'proportional': False,
        'fields': table_fields,
        'headings': get_table_headings(table_fields),
        'items': items,
    }

    ctx = get_overview_context(request)
    ctx.update({
        'project': {
          'code': project.code,
          'name': project.fullname,
        },
        'table': table,

        'browser_extends': 'projects/base.html',
        'browser_body_id': 'projectoverview',
    })

    return render_to_response('browser/overview.html', ctx,
                              context_instance=RequestContext(request))


@get_path_obj
@permission_required('view')
def translate(request, project):
    request.pootle_path = project.pootle_path
    # TODO: support arbitrary resources
    request.ctx_path = project.pootle_path
    request.resource_path = ''

    request.store = None
    request.directory = project.directory

    language = None

    context = get_translation_context(request)
    context.update({
        'language': language,
        'project': project,

        'editor_extends': 'projects/base.html',
        'editor_body_id': 'projecttranslate',
    })

    return render_to_response('editor/main.html', context,
                              context_instance=RequestContext(request))


@get_path_obj
@permission_required('view')
def export_view(request, project):
    request.pootle_path = project.pootle_path
    # TODO: support arbitrary resources
    request.ctx_path = project.pootle_path
    request.resource_path = ''

    request.store = None
    request.directory = project.directory

    language = None

    ctx = get_export_view_context(request)
    ctx.update({
        'source_language': 'en',
        'language': language,
        'project': project,
    })

    return render_to_response('editor/export_view.html', ctx,
                              context_instance=RequestContext(request))


class TranslationProjectFormSet(forms.models.BaseModelFormSet):

    def save_existing(self, form, instance, commit=True):
        result = super(TranslationProjectFormSet, self) \
                .save_existing(form, instance, commit)
        form.process_extra_fields()

        return result


    def save_new(self, form, commit=True):
        result = super(TranslationProjectFormSet, self).save_new(form, commit)
        form.process_extra_fields()

        return result


@get_path_obj
@permission_required('administrate')
def project_admin(request, current_project):
    """adding and deleting project languages"""
    template_translation_project = current_project \
                                        .get_template_translationproject()


    class TranslationProjectForm(forms.ModelForm):
        #FIXME: maybe we can detect if initialize is needed to avoid
        # displaying it when not relevant
        #initialize = forms.BooleanField(required=False, label=_("Initialize"))

        project = forms.ModelChoiceField(
                queryset=Project.objects.filter(pk=current_project.pk),
                initial=current_project.pk, widget=forms.HiddenInput
        )
        language = LiberalModelChoiceField(
                label=_("Language"),
                queryset=Language.objects.exclude(
                    translationproject__project=current_project),
                widget=forms.Select(attrs={
                    'class': 'js-select2 select2-language',
                }),
        )

        class Meta:
            prefix = "existing_language"
            model = TranslationProject

        def process_extra_fields(self):
            if self.instance.pk is not None:
                if self.cleaned_data.get('initialize', None):
                    self.instance.initialize()

    queryset = TranslationProject.objects.filter(
            project=current_project).order_by('pootle_path')

    model_args = {
        'project': {
            'code': current_project.code,
            'name': current_project.fullname,
        }
    }

    def generate_link(tp):
        path_args = split_pootle_path(tp.pootle_path)[:2]
        perms_url = reverse('pootle-tp-admin-permissions', args=path_args)
        return '<a href="%s">%s</a>' % (perms_url, tp.language)

    return util.edit(request, 'projects/admin/languages.html',
                     TranslationProject, model_args, generate_link,
                     linkfield="language", queryset=queryset,
                     can_delete=True, form=TranslationProjectForm,
                     formset=TranslationProjectFormSet)


@get_path_obj
@permission_required('administrate')
def project_admin_permissions(request, project):
    template_vars = {
        "project": project,
        "directory": project.directory,
    }

    return admin_permissions(request, project.directory,
                             "projects/admin/permissions.html", template_vars)


@get_path_obj
@permission_required('view')
def projects_index(request, root):
    """Page listing all projects"""
    user_accessible_projects = Project.accessible_by_user(request.user)
    user_projects = Project.objects.filter(code__in=user_accessible_projects)
    items = [make_project_list_item(project) for project in user_projects]

    table_fields = ['name']
    table = {
        'id': 'projects',
        'fields': table_fields,
        'headings': get_table_headings(table_fields),
        'items': items,
    }

    ctx = {
        'table': table,
    }

    return render_to_response('projects/list.html', ctx,
                              RequestContext(request))
