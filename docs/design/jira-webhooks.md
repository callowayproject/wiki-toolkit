# Jira webhook events
- A Jira issue and its properties belong to a single snapshot.
- Each comment is its own snapshot.
- https://developer.atlassian.com/cloud/jira/platform/webhooks/

## Issues
- file name is `{issue-key}.md`
- Issue webhooks
    - created (`jira:issue_created`)
    - updated (`jira:issue_updated`)
    - deleted (`jira:issue_deleted`)
- Issue property webhooks
    - created or updated (`issue_property_set`)
    - deleted (`issue_property_deleted`)

  ```markdown
  # Main order flow broken

  id: 10002
  key: ED-1
  url: https://your-domain.atlassian.net/rest/api/3/issue/10002
  assignee: Pat Smith
  created: 2026-07-10T08:00:00-05:00
  updated: 2026-07-20T16:00:00-05:00

  ## Description
  Fix the order flow

  ## Acceptance criteria
  ...
  ```

  ## Issue Comments
  
- file name is `{issue-key}-comment-{comment-id}.md`
- Comment webhooks
    - created (`comment_created`)
    - updated (`comment_updated`)
    - deleted (`comment_deleted`)
  
```markdown
id: 10000
url:https://your-domain.atlassian.net/rest/api/3/issue/10010/comment/10000
author: Pat Smith
created: 2026-07-20T16:00:00-05:00

Lorem ipsum dolor sit amet, consectetur adipiscing elit. Pellentesque eget venenatis elit. Duis eu justo eget augue iaculis fermentum. Sed semper quam laoreet nisi egestas at posuere augue semper.
