import os
import sys
import logging

from dotenv import load_dotenv

# load dot env file
load_dotenv()


class Singleton(type):
    _instances = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton,
                                        cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Environment(metaclass=Singleton):
    def _validate(self, key):
        env_var = os.getenv(key)

        if not env_var:
            logging.error(f'Missing required environment variable "{key}".')
            sys.exit(1)

        return env_var

    def __init__(self):
        # set the logging stuff
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO)

        # set env vars
        self.devops_token = self._validate('DEVOPS_TOKEN')
        self.sprint_items_query_id = self._validate('SPRINT_ITEMS_QUERY_ID')
        self.epic_items_query_id = self._validate('EPIC_ITEMS_QUERY_ID')
        self.telegram_token = self._validate('TELEGRAM_TOKEN')
        self.discord_bot_token = self._validate('DISCORD_BOT_TOKEN')
        self.org_id = self._validate('ORGANIZATION_ID')
        self.project_id = self._validate('PROJECT_ID')
        self.team_id = self._validate('TEAM_ID')
        self.increased_scope_threshold = os.getenv('INCREASED_SCOPE_THRESHOLD',
                                                   1)
        self.work_days_per_week = os.getenv('WORK_DAYS_PER_WEEK', 4)
        self.telegram_allowed_chat_ids = os.getenv('TELEGRAM_ALLOWED_CHAT_IDS',
                                                   ',').split(',')
