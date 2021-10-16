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
        self.telegram_token = self._validate('TELEGRAM_TOKEN')
