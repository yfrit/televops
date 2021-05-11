import asyncio
import datetime
import os

from azure.devops.connection import Connection
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


class Client:
    def __init__(self, collaborators):
        self._colaborators = collaborators

        # Fill in with your personal access token and org URL
        personal_access_token = os.getenv('DEVOPS_TOKEN')
        organization_url = 'https://dev.azure.com/YfritGames'

        # Create a connection to the org
        credentials = BasicAuthentication('', personal_access_token)
        connection = Connection(base_url=organization_url, creds=credentials)

        self._wit_client = connection.clients.get_work_item_tracking_client()

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
        ORDER BY [System.Id]
        MODE (Recursive, ReturnMatchingChildren)
        """ # noqa
        wiql_results = self._query_by_wiql(query, top=30).work_item_relations

        if wiql_results:
            # WIQL query gives a WorkItemReference with ID only
            # => we get the corresponding WorkItem from id
            for res in wiql_results:
                wid = res.target.id
                work_item = self._wit_client.get_work_item(wid)
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
            work_items = (self._wit_client.get_work_item(int(res.id))
                          for res in wiql_results)
            for work_item in work_items:
                # create child
                wid = work_item.id
                name = work_item.fields['System.Title']
                owner = work_item.fields['System.AssignedTo']['displayName']
                state = work_item.fields['System.State']
                child = Task(id=wid, name=name, owner=owner, state=state)

                # get parent
                story_item = self._get_parent_by_task_id(wid)
                wid = story_item.id
                name = story_item.fields['System.Title']
                owner = story_item.fields['System.AssignedTo']['displayName']
                state = story_item.fields['System.State']
                parent = Task(id=wid, name=name, owner=owner, state=state)

                child.parent = parent
                results.append(child)

        return (username, results)

    def get_current_scope(self):
        # this is hardcoded since it's very project specific for us
        # our SCRUMBAN scope is defined by all of the prioritized
        # work items, which all receive a tag with the name of our
        # current release

        # fetch work that is done
        qid = '29ee26af-1b5e-42b6-9a62-00f023530620'
        done_results = list(self._wit_client.query_by_id(qid).work_items)
        done_count = len(done_results)

        # fetch work that is not done
        qid = '8ea659e8-04c4-41af-9d83-d763b3679737'
        not_done_results = list(self._wit_client.query_by_id(qid).work_items)
        not_done_count = len(not_done_results)

        # TODO: use the objects for cool things, for now, too lazy
        # maye completion dates to plot estimated project delivery
        results = {
            'done': done_count,
            'total': done_count + not_done_count,
            'completed': done_count / (done_count + not_done_count)
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
