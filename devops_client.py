import asyncio
import datetime
import math

from azure.devops.connection import Connection
from azure.devops.v5_1.work.models import TeamContext
from azure.devops.v5_1.work_item_tracking.models import Wiql
from msrest.authentication import BasicAuthentication
from utils import force_format_timestamp

from environment import Environment

# constants
PARENT_TYPES = ['Product Backlog Item', 'Bug']

# load env
env = Environment()


class Task:
    def __init__(self, id, name, owner, state, parent=None, effort=None):
        self.id = id
        self.name = name
        self.owner = owner
        self.state = state
        self.parent = parent
        self.effort = int(effort) if effort else 0

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
        effort = work_item.fields.get('Microsoft.VSTS.Scheduling.Effort')

        return Task(id=wid, name=name, owner=owner, state=state, effort=effort)


class Client:
    def __init__(self, collaborators):
        self._colaborators = collaborators

        # Fill in with your personal access token and org URL
        personal_access_token = env.devops_token
        organization_url = f"https://dev.azure.com/{env.org_id}"

        # Create a connection to the org
        credentials = BasicAuthentication('', personal_access_token)
        connection = Connection(base_url=organization_url, creds=credentials)

        # clients and controllers
        self._wit_client = connection.clients.get_work_item_tracking_client()
        self._task_builder = TaskBuilder()
        self._work_client = connection.clients.get_work_client()

    def _get_work_item(self, id):
        return self._wit_client.get_work_item(id)

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
            SELECT [System.Id],
                [System.Title],
                [System.State]
            FROM WorkItems
            WHERE [System.WorkItemType] = 'Task'
            AND (
                [System.State] = 'Done'
                AND [System.ChangedDate] > '{yesterday}'
                AND [System.AssignedTo] = '{username}'
            ) or (
                [System.State] = 'In Progress'
                AND [System.AssignedTo] = '{username}'
            )
            ORDER BY [System.ChangedDate] DESC"""
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

    def _get_current_sprint(self):
        team_context = TeamContext(project='Card Game', team='Card Game Team')
        iteration = self._work_client.get_team_iterations(
            team_context, timeframe='current')[0]
        first_date = iteration.attributes.start_date.date()
        release_date = iteration.attributes.finish_date.date()
        path = iteration.path

        return {
            'first_date': first_date,
            'release_date': release_date,
            'path': path
        }

    def get_current_scope(self):
        # this is hardcoded since it's very project specific for us
        # our SCRUMBAN scope is defined by all of the prioritized
        # work items, which all receive a tag with the name of our
        # current release
        qid = env.sprint_items_query_id
        done_count = 0
        not_done_count = 0
        remaning_effort = 0
        completed_effort = 0
        created_dates = []
        results = self._wit_client.query_by_id(qid).work_items
        work_items = [self._get_work_item(int(res.id)) for res in results]

        for work_item in work_items:
            state = work_item.fields['System.State']
            if state == 'Done':
                # get completion dates and match them with sprint start date
                closed_date_str = work_item.fields[
                    'Microsoft.VSTS.Common.ClosedDate']
                closed_date = force_format_timestamp(closed_date_str)
                closed_date_str = str(closed_date)

                # store created dates from done items
                created_date = force_format_timestamp(
                    work_item.fields['System.CreatedDate'])
                created_dates.append(str(created_date))

                # get effort
                effort = work_item.fields.get(
                    'Microsoft.VSTS.Scheduling.Effort')
                completed_effort += effort if effort else 0

                done_count += 1
            else:
                # store created dates from not done items
                created_date = force_format_timestamp(
                    work_item.fields['System.CreatedDate'])
                created_dates.append(str(created_date))

                # get effort
                effort = work_item.fields.get(
                    'Microsoft.VSTS.Scheduling.Effort')
                remaning_effort += effort if effort else 0

                not_done_count += 1

        # get sprint start date to make comparisons
        iteration = self._get_current_sprint()
        first_date = iteration['first_date']
        release_date = iteration['release_date']

        # get number of worked days
        today = datetime.date.today()
        total_days = (today - first_date).days

        if total_days > 0 and done_count > 0:
            # get average
            average = done_count / total_days

            # calculate projected date
            days_left = not_done_count / average
            projected_date = today + datetime.timedelta(
                days=math.ceil(days_left))
        else:
            projected_date = 'Indefinite'

        # calculate increased scope by matching created date with sprint start
        increased_scope = 0
        for created_date in created_dates:
            # give a little bit of tolerance
            threshold = datetime.timedelta(days=env.increased_scope_threshold)
            if created_date > str(first_date + threshold):
                increased_scope += 1

        results = {
            'done': done_count,
            'total': done_count + not_done_count,
            'completed': done_count / (done_count + not_done_count),
            'projected_date': projected_date,
            'release_date': release_date,
            'increased_scope': increased_scope,
            'completed_effort': completed_effort,
            'remaning_effort': remaning_effort,
            'total_effort': completed_effort + remaning_effort
        }

        return results

    async def _get_tasks(self):
        task_map = {}

        # gather a call for each collaborator
        results = await asyncio.gather(*[
            self._get_tasks_by_user(colaborator)
            for colaborator in self._colaborators.keys()
        ])

        # merge all results into a single sorted task map
        for collaborator, tasks in results:
            tasks = sorted(tasks, key=lambda task: task.id)
            task_map[collaborator] = tasks

        return task_map

    def get_tasks(self):
        return asyncio.run(self._get_tasks())

    def get_total_effort(self):
        # this is hardcoded since it's very project specific for us.
        # the current epic is defined under the query id
        qid = env.epic_items_query_id
        results = self._wit_client.query_by_id(qid).work_item_relations
        work_items = [
            self._get_work_item(int(res.target.id)) for res in results
        ]

        # get current sprint
        iteration = self._get_current_sprint()
        current_iteration = iteration['path']

        epic_remaining_effort = 0
        epic_completed_effort = 0
        sprint_remaining_effort = 0
        sprint_completed_effort = 0
        for work_item in work_items:
            wtype = work_item.fields.get('System.WorkItemType')
            if wtype in PARENT_TYPES:
                state = work_item.fields.get('System.State')
                effort = int(
                    work_item.fields.get('Microsoft.VSTS.Scheduling.Effort',
                                         0))
                remaining_work = int(
                    work_item.fields.get(
                        'Microsoft.VSTS.Scheduling.RemainingWork', 0))
                if state == 'Done':
                    # for done items, effort is considered completed
                    epic_completed_effort += effort

                    iteration_path = work_item.fields.get(
                        'System.IterationPath')
                    if iteration_path == current_iteration:
                        sprint_completed_effort += effort
                else:
                    # for not done items, remaining work is considered
                    burndown = effort - remaining_work

                    # add the burndown to completed effort
                    if remaining_work > 0:
                        sprint_completed_effort += burndown
                        epic_completed_effort += burndown

                    # check if remaining work exists, add effort if not
                    iteration_path = work_item.fields.get(
                        'System.IterationPath')
                    delta = effort if remaining_work == 0 else remaining_work
                    epic_remaining_effort += delta
                    if iteration_path == current_iteration:
                        # for the sprint metric, check the iteration path
                        sprint_remaining_effort += delta

        # get start and finish dates of the epic
        epic = next((item for item in work_items
                     if item.fields.get('System.WorkItemType') == 'Epic'),
                    None)
        start_date = epic.fields.get('Microsoft.VSTS.Scheduling.StartDate')
        delivery_date = epic.fields.get('Microsoft.VSTS.Scheduling.TargetDate')

        # find num of collaborators where developer=true
        developers = [
            colaborator for colaborator in self._colaborators.keys()
            if self._colaborators[colaborator]['developer']
        ]
        num_developers = len(developers)

        # calculate total remaining effort
        if start_date and delivery_date:
            delivery_date = force_format_timestamp(delivery_date)
            today = datetime.date.today()
            remaining_weeks = (delivery_date - today).days / 7
            remaining_work_days = int(
                remaining_weeks * (env.work_days_per_week * num_developers))
        else:
            raise Exception('Epic has no start or delivery date')

        # calculate sprint velocity
        sprint_start_date = iteration['first_date']
        sprint_delivery_date = iteration['release_date']
        sprint_work_days = (sprint_delivery_date - sprint_start_date).days + 1
        sprint_total_weeks = sprint_work_days / 7
        sprint_capacity = int(sprint_total_weeks *
                              (env.work_days_per_week * num_developers))

        # calculate totals
        epic_total_effort = epic_completed_effort + epic_remaining_effort
        sprint_total_effort = sprint_completed_effort + sprint_remaining_effort
        return {
            'epic_remaining_effort': epic_remaining_effort,
            'epic_total_effort': epic_total_effort,
            'epic_completed_effort': epic_completed_effort,
            'epic_percentage_effort':
            epic_completed_effort / epic_total_effort,
            'sprint_total_effort': sprint_total_effort,
            'sprint_completed_effort': sprint_completed_effort,
            'sprint_percentage_effort':
            sprint_completed_effort / sprint_total_effort,
            'remaining_work_days': remaining_work_days,
            'epic_velocity_percentage':
            epic_remaining_effort / remaining_work_days,
            'work_days_per_week': env.work_days_per_week,
            'num_developers': num_developers,
            'sprint_capacity': sprint_capacity,
        }
