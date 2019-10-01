# Copyright 2017 Neural Networks and Deep Learning lab, MIPT
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import threading
from collections import namedtuple
from logging import getLogger
from queue import Empty, Queue
from threading import Thread

import requests
from requests.exceptions import HTTPError

from deeppavlov.utils.ms_bot_framework.conversation import Conversation

log = getLogger(__name__)

ConvKey = namedtuple('ConvKey', ['channel_id', 'conversation_id'])


class Bot(Thread):
    def __init__(self, agent_generator: callable, config: dict, input_queue: Queue):
        super(Bot, self).__init__()
        self.config = config
        self._run_flag = True

        self.conversations = {}
        self.access_info = {}
        self.http_sessions = {}
        self.input_queue = input_queue

        self.agent = None
        self.agent_generator = agent_generator

        if not self.config['multi_instance']:
            self.agent = self._init_agent()
            log.info('New bot instance level agent initiated')

        polling_interval = self.config['auth_polling_interval']
        self.timer = threading.Timer(polling_interval, self._update_access_info)
        self._request_access_info()
        self.timer.start()

    def run(self):
        while self._run_flag:
            try:
                activity = self.input_queue.get(timeout=1)
            except Empty:
                pass
            else:
                self._handle_activity(activity)

    def join(self, timeout=None):
        self._run_flag = False
        for timer in threading.enumerate():
            if isinstance(timer, threading.Timer):
                timer.cancel()
        Thread.join(self, timeout)

    def del_conversation(self, conversation_key: ConvKey):
        del self.conversations[conversation_key]
        log.info(f'Deleted conversation, key: {str(conversation_key)}')

    def _init_agent(self):
        # TODO: Decide about multi-instance mode necessity.
        # If model multi-instancing is still necessary - refactor and remove
        agent = self.agent_generator()
        return agent

    def _update_access_info(self):
        polling_interval = self.config['auth_polling_interval']
        self.timer = threading.Timer(polling_interval, self._update_access_info)
        self.timer.start()
        self._request_access_info()

    def _request_access_info(self):
        headers = {'Host': self.config['auth_host'],
                   'Content-Type': self.config['auth_content_type']}

        payload = {'grant_type': self.config['auth_grant_type'],
                   'scope': self.config['auth_scope'],
                   'client_id': self.config['auth_app_id'],
                   'client_secret': self.config['auth_app_secret']}

        result = requests.post(url=self.config['auth_url'],
                               headers=headers,
                               data=payload)

        status_code = result.status_code
        if status_code != 200:
            raise HTTPError(f'Authentication token request returned wrong HTTP status code: {status_code}')

        self.access_info = result.json()
        log.info(f'Obtained authentication information from Microsoft Bot Framework: {str(self.access_info)}')

    def _handle_activity(self, activity: dict):
        conversation_key = ConvKey(activity['channelId'], activity['conversation']['id'])

        if conversation_key not in self.conversations.keys():
            if self.config['multi_instance']:
                conv_agent = self._init_agent()
                log.info('New conversation instance level agent initiated')
            else:
                conv_agent = self.agent

            self.conversations[conversation_key] = Conversation(bot=self,
                                                                agent=conv_agent,
                                                                activity=activity,
                                                                conversation_key=conversation_key)

            log.info(f'Created new conversation, key: {str(conversation_key)}')

        conversation = self.conversations[conversation_key]
        conversation.handle_activity(activity)
