# Televops
Dailying on Telegram, but not without Azure DevOps.

# Dependencies
```bash
pip install -r requirements.txt
```

It's recommended to use a [virtual environment](https://virtualenv.pypa.io/en/latest/) to isolate dependencies.

# Collaborators

Create a `collaborators.json` file in the root directory (alongside `televops.py`) and add the list of collaborators from Azure Devops. Example:

```json
{
    "Jon Doe": {
        "name": "Jon Doe",
        "developer": true
    },
    "Joana d'Arc": {
        "name": "Joana d'Arc",
        "developer": true
    },
    "Leonardo da Vinci": {
        "name": "Leonardo da Vinci",
        "developer": false
    }
}
```

The `developer` field is used to calculate the effort of the sprint, epic and capacity. If true, the person will be counted as a developer. The effort values will be calculated using the number of working days multiplied by the number of developers.

The number of working days is hardcoded in the `devops_client.py` file under the `WORK_DAYS_PER_WEEK` constant.

# Work Items

These are very specific requirements that fit our needs, we only ever work on one epic, distributing the backlog into child features. For this bot to work, your work items must follow the following structure:

```
Epic
├── Feature
|  ├── Product Backlog Item / Bug
|  ├── ├── Task
```

Epics must have the `Start Date` and `Target Date` fields set, Features have no specific requirements, Product Backlog Items and Bugs must have the `Effort` field set if you want the capacity and effort measures to be calculated. Tasks have no specific requirements. Bugs must be treated as Product Backlog Items, not Tasks.

# Queries

Some of the functions require an Azure Devops Query to fetch the data. The queries can be built using the Azure Devops Query Builder. After building the queries, you will need to save their query ids and add them to the `.env` file. This is a way to allow for easier parametrizing of the work items, such as which epic is being worked on, without the need of hardcoding these values. These are the required queries:

> SPRINT_ITEMS_QUERY_ID
```sql
SELECT
    [System.Id],
    [System.WorkItemType],
    [System.Title],
    [System.AssignedTo],
    [System.State],
    [System.Tags],
    [System.CreatedDate],
    [Microsoft.VSTS.Common.ClosedDate]
FROM workitems
WHERE
    [System.TeamProject] = @project
    AND [System.WorkItemType] IN ('Product Backlog Item', 'Bug')
    AND [System.IterationPath] UNDER @currentIteration('[YOUR PROJECT]\\YOUR TEAM <id:your-team-id>')
```

> EPIC_ITEMS_QUERY_ID
```sql
SELECT
    [System.Id],
    [System.WorkItemType],
    [System.Title],
    [System.AssignedTo],
    [System.State]
FROM workitemLinks
WHERE
    (
        [Source].[System.Id] = YOUR_EPIC_ID
    )
    AND (
        [System.Links.LinkType] = 'System.LinkTypes.Hierarchy-Forward'
    )
    AND (
        [Target].[System.WorkItemType] IN ('Product Backlog Item', 'Bug')
    )
ORDER BY [System.Id]
MODE (Recursive)
```

The queries are used to fetch work items from the current sprint and work items from the epic you team are working on. Replace the place holders with the correct values.

Once you have the queries build and their ids saved, your `.env` file should look like this:

```env
SPRINT_ITEMS_QUERY_ID=<your-sprint-items-query-id>
EPIC_ITEMS_QUERY_ID=<your-epic-items-query-id>
```

# Tokens

Two authentication tokens are required. The first is used to authenticate with Azure Devops. The second is used to authenticate with Telegram.
Add them to the `.env` file.

```env
TELEGRAM_TOKEN=<your-telegram-token>
DEVOPS_TOKEN=<your-azure-devops-token>
```

# Example environment file

```env
TELEGRAM_TOKEN=<your-telegram-token>
DEVOPS_TOKEN=<your-azure-devops-token>
SPRINT_ITEMS_QUERY_ID=<your-sprint-items-query-id>
EPIC_ITEMS_QUERY_ID=<your-epic-items-query-id>
```

# Usage
1. Add the bot to the channel
1. Make it admin
1. Type in `/daily`

## Example Response

```
2021-06-18 13:16:04.850248
Welcome to today's Yfrt's Televops Daily Meeting!

Current iteration:
├── Sprint Stories/Bugs: 1/5 (20.00%)
├── Effort
│   ├── Sprint Progress: 4/31 work days completed (12.90%)
│   ├── Epic Progress: 15/185 work days completed (8.11%)
│   ├── Capacity: 203/222 work days remaining (91.28%)
│   ├── Work Days Per Week: 4
│   ├── Developers: 2
├── Increased Scope: 2
├── Projected Sprint Delivery Date: 2021-06-29/2021-07-01
├── Epic Delivery Date: 2021-12-13

Jon Doe is working on:
├── 2059. Fake User Story - (2 work days)
│   ├── 2119. Do fake task - (In Progress)

Joana d'Arc is working on:
No tasks in progress.

Leonardo da Vinci is working on:
├── 1902. Non-developer User Story 
│   ├── 1908. Do fake task 1 - (Done)
│   ├── 1909. Do fake task 2 - (In Progress)

Please, type in your current status. Don't forget to include what you're doing, what you plan to do, and if you have any impediments!
```

## Response Structure

+ Sprint Stories/Bugs: completed/total stories + bugs (percentage)
+ Effort:
    + **Sprint Progress**: completed/total work days (percentage)
    + **Epic Progress**: completed/total work days (percentage)
    + **Capacity**: remaining/total work days (percentage)
    + **Work Days Per Week**: amount of work days per week set in the code as a constant
    + **Developers**: number of collaborators set as developers in the `collaborators.json` file.
+ **Increased Scope**: number of stories/bugs added to the sprint as intruders, that is, after sprint planning and during the sprint.
+ **Projected Sprint Delivery Date**: the date the sprint will be completed according to stories/bugs being closed. This is an estimation that approximates the average velocity of the sprint. When no stories/bugs are closed, projected date will appear as `Indefinite`.
+ **Epic Delivery Date**: the date the epic will be completed. Set under the Epic's `Target Date` field.
+ **\<COLLABORATOR\> is working on**: a three style structure that displays the stories/bugs the collaborator is working on, the effort of the stories/bugs, and all the child tasks. `In Progress` work items are always displayed, while `Done` work items are only displayed if those were completed in the last 24 hours. Stories/bugs without set efforts will be displayed without the effort.