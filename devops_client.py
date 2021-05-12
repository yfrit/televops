import asyncio
import datetime
import math
import os

from azure.devops.connection import Connection
from azure.devops.v5_1.work.models import TeamContext
from azure.devops.v5_1.work_item_tracking.models import Wiql
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

# load env file
load_dotenv()

# constants
PARENT_TYPES = ['Product Backlog Item', 'Bug']


class Task:
    def __init__(self, id, name, owner, state, parent=None):
        self.id = id
        self.name = name
        self.owner = owner
        self.state = state
        self.parent = parent

    def __str__(self):
        return f'Task {self.id}: {self.name} ({self.owner})'

    def __repr__(self):
        return self.__str__()


class TaskBuilder():
    def from_work_item(self, work_item):
        wid = work_item.id
        name = work_item.fields['System.Title']
        owner = work_item.fields['System.AssignedTo']['displayName']
        state = work_item.fields['System.State']

        return Task(id=wid, name=name, owner=owner, state=state)


class Client:
    def __init__(self, collaborators):
        self._colaborators = collaborators

        # Fill in with your personal access token and org URL
        personal_access_token = os.getenv('DEVOPS_TOKEN')
        organization_url = 'https://dev.azure.com/YfritGames'

        # Create a connection to the org
        credentials = BasicAuthentication('', personal_access_token)
        connection = Connection(base_url=organization_url, creds=credentials)

        # clients and controllers
        self._wit_client = connection.clients.get_work_item_tracking_client()
        self._task_builder = TaskBuilder()
        self._work_client = connection.clients.get_work_client()

        # caching objects
        self._work_item_map = {}

    def _get_work_item(self, id):
        if id in self._work_item_map:
            return self._work_item_map[id]

        # work around for unhashable WorkItem class
        work_item = self._wit_client.get_work_item(id)
        self._work_item_map[id] = work_item

        return work_item

    def _query_by_wiql(self, query, top=100):
        wiql = Wiql(query=query)

        return self._wit_client.query_by_wiql(wiql, top=top)

    def _get_parent_by_task_id(self, task_id):
        query = f"""
                SELECT
                [System.Id],
                [System.WorkItemType],
                [System.Title],
                [System.AssignedTo],
                [System.State]
        FROM workitemLinks
        WHERE
                (
                        [System.Links.LinkType] = 'System.LinkTypes.Hierarchy-Forward'
                )
                AND (
                        [Target].[System.Id] = {task_id}
                )
        MODE (Recursive, ReturnMatchingChildren)
        """ # noqa
        wiql_results = self._query_by_wiql(query, top=30).work_item_relations

        if wiql_results:
            # WIQL query gives a WorkItemReference with ID only
            # => we get the corresponding WorkItem from id
            for res in wiql_results:
                wid = res.target.id
                work_item = self._get_work_item(wid)
                if work_item.fields['System.WorkItemType'] in PARENT_TYPES:
                    return work_item

    async def _get_tasks_by_user(self, username):
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        query = f"""
            select [System.Id],
                [System.Title],
                [System.State]
            from WorkItems
            where [System.WorkItemType] = 'Task'
            and (
                [System.State] = 'Done'
                and [System.ChangedDate] > '{yesterday}'
                and [System.AssignedTo] = '{username}'
            ) or (
                [System.State] = 'In Progress'
                and [System.AssignedTo] = '{username}'
            )
            order by [System.ChangedDate] desc"""
        wiql_results = self._query_by_wiql(query, top=30).work_items

        results = []
        if wiql_results:
            # WIQL query gives a WorkItemReference with ID only
            # => we get the corresponding WorkItem from id
            work_items = (self._get_work_item(int(res.id))
                          for res in wiql_results)
            for work_item in work_items:
                # create child
                child = self._task_builder.from_work_item(work_item)

                # get parent
                story_item = self._get_parent_by_task_id(child.id)
                parent = self._task_builder.from_work_item(story_item)

                child.parent = parent
                results.append(child)

        return (username, results)

    def get_current_scope(self):
        # this is hardcoded since it's very project specific for us
        # our SCRUMBAN scope is defined by all of the prioritized
        # work items, which all receive a tag with the name of our
        # current release
        qid = 'bda7bbb2-f777-4b1f-b925-effda36aba71'
        done_count = 0
        not_done_count = 0
        created_dates = []
        results = self._wit_client.query_by_id(qid).work_items
        work_items = [self._get_work_item(int(res.id)) for res in results]

        for work_item in work_items:
            state = work_item.fields['System.State']
            if state == 'Done':
                # get completion dates and match them with sprint start date
                closed_date_str = work_item.fields[
                    'Microsoft.VSTS.Common.ClosedDate']
                closed_date = datetime.datetime.strptime(
                    closed_date_str, '%Y-%m-%dT%H:%M:%S.%fZ').date()
                closed_date_str = str(closed_date)

                # store created dates from done items
                created_date = datetime.datetime.strptime(
                    work_item.fields['System.CreatedDate'],
                    '%Y-%m-%dT%H:%M:%S.%fZ').date()
                created_dates.append(str(created_date))

                done_count += 1
            else:
                # store created dates from not done items
                created_date = datetime.datetime.strptime(
                    work_item.fields['System.CreatedDate'],
                    '%Y-%m-%dT%H:%M:%S.%fZ').date()
                created_dates.append(str(created_date))

                not_done_count += 1

        # get sprint start date to make comparisons
        team_context = TeamContext(project='Card Game', team='Card Game Team')
        iteration = self._work_client.get_team_iterations(
            team_context, timeframe='current')[0]
        first_date = iteration.attributes.start_date.date()
        release_date = iteration.attributes.finish_date.date()

        # get number of worked days
        today = datetime.datetime.now().date()
        total_days = (today - first_date).days

        # get average
        average = done_count / total_days

        # calculate projected date
        days_left = not_done_count / average
        projected_date = today + datetime.timedelta(days=math.ceil(days_left))

        # calculate increased scope by matching created date with sprint start
        increased_scope = 0
        for created_date in created_dates:
            if created_date > str(first_date):
                increased_scope += 1

        results = {
            'done': done_count,
            'total': done_count + not_done_count,
            'completed': done_count / (done_count + not_done_count),
            'projected_date': projected_date,
            'release_date': release_date,
            'increased_scope': increased_scope
        }

        return results

    async def _get_tasks(self):
        task_map = {}

        # gather a call for each collaborator
        results = await asyncio.gather(*[
            self._get_tasks_by_user(colaborator)
            for colaborator in self._colaborators
        ])

        # merge all results into a single sorted task map
        for collaborator, tasks in results:
            tasks = sorted(tasks, key=lambda task: task.id)
            task_map[collaborator] = tasks

        return task_map

    def get_tasks(self):
        return asyncio.run(self._get_tasks())
