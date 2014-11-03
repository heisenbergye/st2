# Licensed to the StackStorm, Inc ('StackStorm') under one or more
# contributor license agreements.  See the NOTICE file distributed with
# this work for additional information regarding copyright ownership.
# The ASF licenses this file to You under the Apache License, Version 2.0
# (the "License"); you may not use this file except in compliance with
# the License.  You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import abc
import six
import json
import logging

from st2client import commands
from st2client.formatters import table


LOG = logging.getLogger(__name__)


def add_auth_token_to_kwargs_from_cli(func):
    def decorate(*args, **kwargs):
        ns = args[1]
        if getattr(ns, 'token', None):
            kwargs['token'] = ns.token
        return func(*args, **kwargs)
    return decorate


class ResourceCommandError(Exception):
    pass


class ResourceNotFoundError(Exception):
    pass


class ResourceBranch(commands.Branch):

    def __init__(self, resource, description, app, subparsers,
                 parent_parser=None, read_only=False, commands={}):

        self.resource = resource
        super(ResourceBranch, self).__init__(
            self.resource.get_alias().lower(), description,
            app, subparsers, parent_parser=parent_parser)

        # Registers subcommands for managing the resource type.
        self.subparsers = self.parser.add_subparsers(
            help=('List of commands for managing %s.' %
                  self.resource.get_plural_display_name().lower()))

        # Resolves if commands need to be overridden.
        if 'list' not in commands:
            commands['list'] = ResourceListCommand
        if 'get' not in commands:
            commands['get'] = ResourceGetCommand
        if 'create' not in commands:
            commands['create'] = ResourceCreateCommand
        if 'update' not in commands:
            commands['update'] = ResourceUpdateCommand
        if 'delete' not in commands:
            commands['delete'] = ResourceDeleteCommand

        # Instantiate commands.
        args = [self.resource, self.app, self.subparsers]
        self.commands['list'] = commands['list'](*args)
        self.commands['get'] = commands['get'](*args)
        if not read_only:
            self.commands['create'] = commands['create'](*args)
            self.commands['update'] = commands['update'](*args)
            self.commands['delete'] = commands['delete'](*args)


@six.add_metaclass(abc.ABCMeta)
class ResourceCommand(commands.Command):

    def __init__(self, resource, *args, **kwargs):

        has_token_opt = kwargs.pop('has_token_opt', True)

        super(ResourceCommand, self).__init__(*args, **kwargs)

        self.resource = resource

        if has_token_opt:
            self.parser.add_argument('-t', '--token', dest='token',
                                     help='Access token for user authentication. '
                                          'Get ST2_AUTH_TOKEN from the environment '
                                          'variables by default.')

        self.parser.add_argument('-j', '--json',
                                 action='store_true', dest='json',
                                 help='Prints output in JSON format.')

    @property
    def manager(self):
        return self.app.client.managers[self.resource.__name__]

    @property
    def arg_name_for_resource_id(self):
        resource_name = self.resource.get_display_name().lower()
        return '%s-id' % resource_name.replace(' ', '-')

    def print_not_found(self, name):
        print ('%s "%s" is not found.\n' %
               (self.resource.get_display_name(), name))

    def get_resource(self, name_or_id, **kwargs):
        return self.get_resource_by_name_or_id(name_or_id=name_or_id, **kwargs)

    def get_resource_by_name_or_id(self, name_or_id, **kwargs):
        instance = self.manager.get_by_name(name_or_id, **kwargs)
        if not instance:
            try:
                instance = self.manager.get_by_id(name_or_id, **kwargs)
            except:
                pass
        if not instance:
            message = ('Resource with id or name "%s" doesn\'t exist.' %
                       (name_or_id))
            raise ResourceNotFoundError(message)
        return instance

    def get_resource_by_ref_or_id(self, ref_or_id, **kwargs):
        instance = self.manager.get_by_ref_or_id(ref_or_id=ref_or_id, **kwargs)

        if not instance:
            message = ('Resource with id or reference "%s" doesn\'t exist.' %
                       (ref_or_id))
            raise ResourceNotFoundError(message)
        return instance

    @abc.abstractmethod
    def run(self, args, **kwargs):
        raise NotImplementedError

    @abc.abstractmethod
    def run_and_print(self, args, **kwargs):
        raise NotImplementedError

    def _get_metavar_for_argument(self, argument):
        return argument.replace('_', '-')

    def _get_help_for_argument(self, resource, argument):
        resource_display_name = resource.get_display_name().lower()

        if 'ref' in argument:
            result = ('Reference or ID of the %s.' % resource_display_name)
        else:
            result = ('Name or ID of the %s.' % resource_display_name)

        return result


class ResourceListCommand(ResourceCommand):
    display_attributes = ['id', 'name', 'description']

    def __init__(self, resource, *args, **kwargs):
        super(ResourceListCommand, self).__init__(resource, 'list',
            'Get the list of %s.' % resource.get_plural_display_name().lower(),
            *args, **kwargs)

        self.parser.add_argument('-a', '--attr', nargs='+',
                                 default=self.display_attributes,
                                 help=('List of attributes to include in the '
                                       'output. "all" will return all '
                                       'attributes.'))
        self.parser.add_argument('-w', '--width', nargs='+', type=int,
                                 default=None,
                                 help=('Set the width of columns in output.'))

    @add_auth_token_to_kwargs_from_cli
    def run(self, args, **kwargs):
        return self.manager.get_all(**kwargs)

    def run_and_print(self, args, **kwargs):
        instances = self.run(args, **kwargs)
        self.print_output(instances, table.MultiColumnTable,
                          attributes=args.attr, widths=args.width,
                          json=args.json)


class ContentPackResourceListCommand(ResourceListCommand):
    """
    Base command class for use with resources which belong to a content pack.
    """
    def __init__(self, resource, *args, **kwargs):
        super(ContentPackResourceListCommand, self).__init__(resource,
                                                             *args, **kwargs)

        self.parser.add_argument('-p', '--pack', type=str,
                                 help=('Only return resources belonging to the'
                                       ' provided pack'))

    @add_auth_token_to_kwargs_from_cli
    def run(self, args, **kwargs):
        filters = {'pack': args.pack}
        return self.manager.get_all(**filters)


class ResourceGetCommand(ResourceCommand):
    display_attributes = ['all']
    attribute_display_order = ['id', 'name', 'description']

    pk_argument_name = 'name_or_id'  # name of the attribute which stores resource PK

    def __init__(self, resource, *args, **kwargs):
        super(ResourceGetCommand, self).__init__(resource, 'get',
            'Get individual %s.' % resource.get_display_name().lower(),
            *args, **kwargs)

        argument = self.pk_argument_name
        metavar = self._get_metavar_for_argument(argument=self.pk_argument_name)
        help = self._get_help_for_argument(resource=resource,
                                           argument=self.pk_argument_name)

        self.parser.add_argument(argument,
                                 metavar=metavar,
                                 help=help)
        self.parser.add_argument('-a', '--attr', nargs='+',
                                 default=self.display_attributes,
                                 help=('List of attributes to include in the '
                                       'output. "all" or unspecified will '
                                       'return all attributes.'))

    @add_auth_token_to_kwargs_from_cli
    def run(self, args, **kwargs):
        resource_id = getattr(args, self.pk_argument_name, None)
        return self.get_resource(resource_id, **kwargs)

    def run_and_print(self, args, **kwargs):
        try:
            instance = self.run(args, **kwargs)
            self.print_output(instance, table.PropertyValueTable,
                              attributes=args.attr, json=args.json,
                              attribute_display_order=self.attribute_display_order)
        except ResourceNotFoundError:
            resource_id = getattr(args, self.pk_argument_name, None)
            self.print_not_found(resource_id)


class ContentPackResourceGetCommand(ResourceGetCommand):
    """
    Command for retrieving a single resource which belongs to a content pack.

    Note: All the resources which belong to the content pack can either be
    retrieved by a reference or by an id.
    """

    attribute_display_order = ['id', 'pack', 'name', 'description']

    pk_argument_name = 'ref_or_id'

    def get_resource(self, ref_or_id, **kwargs):
        return self.get_resource_by_ref_or_id(ref_or_id=ref_or_id, **kwargs)


class ResourceCreateCommand(ResourceCommand):

    def __init__(self, resource, *args, **kwargs):
        super(ResourceCreateCommand, self).__init__(resource, 'create',
            'Create a new %s.' % resource.get_display_name().lower(),
            *args, **kwargs)

        self.parser.add_argument('file',
                                 help=('JSON file containing the %s to create.'
                                       % resource.get_display_name().lower()))

    @add_auth_token_to_kwargs_from_cli
    def run(self, args, **kwargs):
        if not os.path.isfile(args.file):
            raise Exception('File "%s" does not exist.' % args.file)
        with open(args.file, 'r') as f:
            data = json.loads(f.read())
            instance = self.resource.deserialize(data)
            return self.manager.create(instance, **kwargs)

    def run_and_print(self, args, **kwargs):
        instance = self.run(args, **kwargs)
        self.print_output(instance, table.PropertyValueTable,
                          attributes=['all'], json=args.json)


class ResourceUpdateCommand(ResourceCommand):
    pk_argument_name = 'name_or_id'

    def __init__(self, resource, *args, **kwargs):
        super(ResourceUpdateCommand, self).__init__(resource, 'update',
            'Updating an existing %s.' % resource.get_display_name().lower(),
            *args, **kwargs)

        argument = self.pk_argument_name
        metavar = self._get_metavar_for_argument(argument=self.pk_argument_name)
        help = self._get_help_for_argument(resource=resource,
                                           argument=self.pk_argument_name)

        self.parser.add_argument(argument,
                                 metavar=metavar,
                                 help=help)
        self.parser.add_argument('file',
                                 help=('JSON file containing the %s to update.'
                                       % resource.get_display_name().lower()))

    @add_auth_token_to_kwargs_from_cli
    def run(self, args, **kwargs):
        if not os.path.isfile(args.file):
            raise Exception('File "%s" does not exist.' % args.file)

        resource_id = getattr(args, self.pk_argument_name, None)
        instance = self.get_resource(resource_id, **kwargs)

        with open(args.file, 'r') as f:
            data = json.loads(f.read())
            modified_instance = self.resource.deserialize(data)
            if not getattr(modified_instance, 'id', None):
                modified_instance.id = instance.id
            else:
                if modified_instance.id != instance.id:
                    raise Exception('The value for the %s id in the JSON file '
                                    'does not match the ID provided in the '
                                    'command line arguments.' %
                                    self.resource.get_display_name().lower())
            return self.manager.update(modified_instance, **kwargs)

    def run_and_print(self, args, **kwargs):
        instance = self.run(args, **kwargs)
        self.print_output(instance, table.PropertyValueTable,
                          attributes=['all'], json=args.json)


class ContentPackResourceUpdateCommand(ResourceUpdateCommand):
    pk_argument_name = 'ref_or_id'


class ResourceDeleteCommand(ResourceCommand):
    pk_argument_name = 'name_or_id'

    def __init__(self, resource, *args, **kwargs):
        super(ResourceDeleteCommand, self).__init__(resource, 'delete',
            'Delete an existing %s.' % resource.get_display_name().lower(),
            *args, **kwargs)

        argument = self.pk_argument_name
        metavar = self._get_metavar_for_argument(argument=self.pk_argument_name)
        help = self._get_help_for_argument(resource=resource,
                                           argument=self.pk_argument_name)

        self.parser.add_argument(argument,
                                 metavar=metavar,
                                 help=help)

    @add_auth_token_to_kwargs_from_cli
    def run(self, args, **kwargs):
        resource_id = getattr(args, self.pk_argument_name, None)
        instance = self.get_resource(resource_id, **kwargs)
        self.manager.delete(instance, **kwargs)

    def run_and_print(self, args, **kwargs):
        try:
            self.run(args, **kwargs)
        except ResourceNotFoundError:
            resource_id = getattr(args, self.pk_argument_name, None)
            self.print_not_found(resource_id)


class ContentPackResourceDeleteCommand(ResourceDeleteCommand):
    """
    Base command class for deleting a resource which belongs to a content pack.
    """

    pk_argument_name = 'ref_or_id'
