import datetime
import os

from azure.devops.connection import Connection
from azure.devops.v5_1.work_item_tracking.models import Wiql
from dotenv import load_dotenv
from msrest.authentication import BasicAuthentication

# load env file
load_dotenv()

# constants
PARENT_TYPES = ["Product Backlog Item", "Bug"]


class Task:
    def __init__(self, id, name, owner, state, parent=None):
        self.id = id
        self.name = name
        self.owner = owner
        self.state = state
        self.parent = parent

    def __str__(self):
        return f"Task {self.id}: {self.name} ({self.owner})"

    def __repr__(self):
        return self.__str__()


class Client:
    def __init__(self, collaborators):
        self.colaborators = collaborators

        # Fill in with your personal access token and org URL
        personal_access_token = os.getenv("DEVOPS_TOKEN")
        organization_url = 'https://dev.azure.com/YfritGames'

        # Create a connection to the org
        credentials = BasicAuthentication('', personal_access_token)
        connection = Connection(base_url=organization_url, creds=credentials)

        self.wit_client = connection.clients.get_work_item_tracking_client()

        # caching object
        self.parent_map = {}

    def query_by_wiql(self, query, top=100):
        wiql = Wiql(query=query)

        return self.wit_client.query_by_wiql(wiql, top=top)

    def get_parent_by_task_id(self, task_id):
        if task_id in self.parent_map:
            return self.parent_map[task_id]

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
        wiql_results = self.query_by_wiql(query, top=30).work_item_relations

        if wiql_results:
            # WIQL query gives a WorkItemReference with ID only
            # => we get the corresponding WorkItem from id
            for res in wiql_results:
                wid = res.target.id
                work_item = self.wit_client.get_work_item(wid)
                if work_item.fields["System.WorkItemType"] in PARENT_TYPES:
                    self.parent_map[task_id] = work_item

                    return work_item

    def get_tasks_by_user(self,
                          username,
                          state="In Progress",
                          date_range=False):
        date_range_option = ""
        if date_range:
            yesterday = datetime.date.today() - datetime.timedelta(days=1)
            date_range_option = f'and [System.ChangedDate] > "{yesterday}"'

        query = f"""
            select [System.Id],
                [System.Title],
                [System.State]
            from WorkItems
            where [System.WorkItemType] = 'Task'
            and [System.State] = "{state}"
            and [System.AssignedTo] = '{username}'
            {date_range_option}
            order by [System.ChangedDate] desc"""
        wiql_results = self.query_by_wiql(query, top=30).work_items

        results = []
        if wiql_results:
            # WIQL query gives a WorkItemReference with ID only
            # => we get the corresponding WorkItem from id
            work_items = (self.wit_client.get_work_item(int(res.id))
                          for res in wiql_results)
            for work_item in work_items:
                # create child
                wid = work_item.id
                name = work_item.fields['System.Title']
                owner = work_item.fields['System.AssignedTo']['displayName']
                state = work_item.fields['System.State']
                child = Task(id=wid, name=name, owner=owner, state=state)

                # get parent
                story_item = self.get_parent_by_task_id(wid)
                wid = story_item.id
                name = story_item.fields['System.Title']
                owner = story_item.fields['System.AssignedTo']['displayName']
                state = story_item.fields['System.State']
                parent = Task(id=wid, name=name, owner=owner, state=state)

                child.parent = parent
                results.append(child)

        return results

    def get_current_scope(self):
        # this is hardcoded since it's very project specific for us
        # our SCRUMBAN scope is defined by all of the prioritized
        # work items, which all receive a tag with the name of our
        # current release

        # fetch work that is done
        qid = "29ee26af-1b5e-42b6-9a62-00f023530620"
        done_results = list(self.wit_client.query_by_id(qid).work_items)
        done_count = len(done_results)

        # fetch work that is not done
        qid = "8ea659e8-04c4-41af-9d83-d763b3679737"
        not_done_results = list(self.wit_client.query_by_id(qid).work_items)
        not_done_count = len(not_done_results)

        # TODO: use the objects for cool things, for now, too lazy
        # maye completion dates to plot estimated project delivery
        results = {
            "done": done_count,
            "total": done_count + not_done_count,
            "completed": done_count / (done_count + not_done_count)
        }
        return results

    def get_tasks(self, include_completed=False):
        tasks = {}
        for c in self.colaborators:
            t = self.get_tasks_by_user(c)

            if include_completed:
                t += self.get_tasks_by_user(c, state="Done", date_range=True)

            t = sorted(t, key=lambda task: task.id)
            tasks[c] = t

        return tasks
