"""{
    "title": "services <argument> <name>",
    "text": "You can get more info about your services, using the `status`, `find` or `list` arguments. For more information, type `sdbot services help`.",
    "mrkdwn_in": ["text"],
    "color": "#8E44AD"
}"""

import json
import requests
import re

from datetime import timedelta
from datetime import datetime

from serverdensity.wrapper import Service
from serverdensity.wrapper import Metrics
from serverdensity.wrapper import ServiceStatus
from limbo.plugins.common.basewrapper import BaseWrapper

COMMANDS = ['status', 'find', 'list', 'help']
BASEURL = 'https://api.serverdensity.io/'
COLOR = '#8E44AD'


class Wrapper(BaseWrapper):
    def __init__(self, msg, server):
        super(Wrapper, self).__init__(msg, server)
        self.service = Service(self.token)
        self.metrics = Metrics(self.token)
        self.status = ServiceStatus(self.token)

    def results_of(self, command, name):
        if command == 'help' or name == 'help':
            result = self.extra_help(command)
        elif command == 'value':
            result = self.get_value(name)
        elif command == 'status':
            result = self.get_status(name)
        elif command == 'find':
            result = self.find_service(name)
        elif command == 'list':
            result = self.list_service(name)
        return result

    def extra_help(self, command):
        help_command = {
            'status': {
                'title': 'Overall Status',
                'mrkdwn_in': ['text'],
                'text': ('Overall Status displays statistics about your services. ' +
                         'It includes _Round trip time_, _Response Time_, ' +
                         '_Status Code_ and _Status of location_. To get ' +
                         'the status of a service you can type `sdbot services status serviceName`'),
                'color': COLOR
            },
            'find': {
                'title': 'Find a Service',
                'mrkdwn_in': ['text'],
                'text': ('You can find a service by typing `sdbot services find serviceName`. ' +
                         'I can also accept regex for the argument `serviceName`. ' +
                         'For example `sdbot services find 2$`.'),
                'color': COLOR
            },
            'list': {
                'title': 'List All Services',
                'mrkdwn_in': ['text'],
                'text': ('For a list of all services, type `sdbot services list <no>`.' +
                         'In this case `<no>` is a number. If you leave it out I will ' +
                         'list the first 5 services.'),
                'color': COLOR
            }
        }

        if command == 'status':
            helptext = [help_command['status']]
        elif command == 'find':
            helptext = [help_command['find']]
        elif command == 'list':
            helptext = [help_command['list']]
        elif command == 'help':
            helptext = [attachment for attachment in help_command.values()]
        return helptext, ''

    def _format_services(self, http, tcp):
        slack_http = [{
            'text': '*Service Name*: {}'.format(service['name']),
            'color': COLOR,
            'mrkdwn_in': ['text'],
            'fields': [{
                    'title': 'Group',
                    'value': service.get('group') if service.get('group') else 'Ungrouped',
                    'short': True
                },
                {
                    'title': 'Type of check',
                    'value': service.get('checkType'),
                    'short': True
                },
                {
                    'title': 'Url',
                    'value': service.get('checkUrl'),
                    'short': True
                },
                {
                    'title': 'Method',
                    'value': service.get('checkMethod'),
                    'short': True
                },
                {
                    'title': 'Slow threshold',
                    'value': str(service.get('slowThreshold')) + 'ms',
                    'short': True
                }
            ]
        } for service in http]

        slack_tcp = [{
            'text': '*Service Name*: {}'.format(service['name']),
            'color': COLOR,
            'mrkdwn_in': ['text'],
            'fields': [{
                    'title': 'Group',
                    'value': service.get('group') if service.get('group') else 'Ungrouped',
                    'short': True
                },
                {
                    'title': 'Type of check',
                    'value': service.get('checkType'),
                    'short': True
                },
                {
                    'title': 'Host',
                    'value': service.get('host'),
                    'short': True
                },
                {
                    'title': 'Port',
                    'value': service.get('port'),
                    'short': True
                }
            ]
        } for service in tcp]

        return slack_http + slack_tcp

    def list_service(self, number):
        if number:
            try:
                number = number.strip()
                number = int(number)
            except ValueError:
                text = '{} is not a number, now is it. You see, it needs to be.'.format(number)
                return text, ''

        services = self.service.list()
        if number:
            services_trunc = services[:number]
        else:
            services_trunc = services[:5]

        http = [s for s in services_trunc if s['checkType'] == 'http']
        tcp = [s for s in services_trunc if s['checkType'] == 'tcp']

        formatted = self._format_services(http, tcp)
        message = ('You have {} services, if you would like to'.format(len(services)) +
                   ' list more than these {} services, use '.format(len(services_trunc)) +
                   '`sdbot services list <no>`')
        return formatted, message

    def find_service(self, name):

        services = self.service.list()
        http = [s for s in services if s['checkType'] == 'http' and
                re.search(name, s['name'])]
        tcp = [s for s in services if s['checkType'] == 'tcp' and
               re.search(name, s['name'])]

        return self._format_services(http, tcp), ''

    def get_value(self, name):
        services = self.service.list()
        _id = self.find_id(name, services, [])
        if not _id:
            return 'I couldn\'t find your service', ''
        service = self.service.view(_id)
        locations = service['checkLocations']
        all_results = []
        for location in locations:
            filtered = {'time': {location: 'all'}}
            now = datetime.now()
            past30 = now - timedelta(minutes=35)

            metrics = self.metrics.get(_id, past30, now, filtered)
            service = metrics[0]['tree'][0]
            data = service['data']
            try:
                latest = '{}s'.format(round(data[-1]['y'], 3))
                avg = '{}s'.format(round(sum([point['y'] for point in data])/len(data), 3))
            except IndexError:
                latest = 'down'
                avg = 'down'

            result = {
                'title': service['name'],
                'color': COLOR,
                'fields': [
                    {
                        'title': '30 Minute Average',
                        'value': avg,
                        'short': True
                    },
                    {
                        'title': 'Latest Value',
                        'value': latest,
                        'short': True
                    }
                ]
            }
            all_results.append(result)

        message = 'Here is the latest values for the {} locations of the service {}'.format(len(locations), name)
        return all_results, message

    def real_name(self, _id, nodes):
        for node in nodes:
            if _id == node['id']:
                return node['name']

    def get_status(self, name):
        services = self.service.list()
        _id = self.find_id(name, services, [])
        if not _id:
            return 'I couldn\'t find your service', ''
        nodes = requests.get(BASEURL + 'service-monitor/nodes', params={'token': self.token})
        statuses = self.status.location(_id)

        all_results = []
        for status in statuses:

            result = {
                'title': self.real_name(status['location'], nodes.json()),
                'color': COLOR,
                'fields': [
                    {
                        'title': 'Round Trip Time',
                        'value': '{}s'.format(round(float(status.get('rtt', 0)), 3)),
                        'short': True
                    },
                    {
                        'title': 'Status of Location',
                        'value': status['status'],
                        'short': True
                    },
                    {
                        'title': 'Response Time',
                        'value': '{}s'.format(round(float(status.get('time', 0)), 3)),
                        'short': True
                    },
                    {
                        'title': 'Status Code',
                        'value': status['code'],
                        'short': True
                    }
                ]
            }
            all_results.append(result)
        message = 'This is the status of all your locations for the service {}'.format(name)
        return all_results, message


def on_message(msg, server):
    text = msg.get("text", "")
    text = Wrapper.clean_parsing(text)

    match = re.findall(r"^[sS][dD][bB]ot services? (\b\w+\b)\s?(\b\w+\b)?", text)
    if not match:
        return
    command, name = match[0]
    name = name.strip()
    if not name and command not in ['list', 'help']:
        text = ('It looks like you forgot to add a name, ' +
                'try `sdbot services {} serviceName`'.format(command))
        return text

    if command not in COMMANDS:
        text = ('I\'m sorry, but couldn\'t quite understand you there, perhaps' +
                ' you could try one of these commands `find`, `status`, `value`')

        return text

    api = Wrapper(msg, server)
    results, message = api.results_of(command, name)
    if isinstance(results, list):
        kwargs = {
            'attachments': json.dumps(results),
            'text': message
        }

        server.slack.post_message(
            msg['channel'],
            '',
            as_user=server.slack.server.username,
            **kwargs)
    else:
        return results
