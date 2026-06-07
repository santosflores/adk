# Summary

This agent is in charge of finding job posts related to a specific query. The user can share a position name and the agent will:

0) User shares a position name
1) Search across three different providers: Ashby, Greenhouse, Lever
2) Join the results of the three providers
3) Create evidence inside a DB to track posts

Work Plan:

* Make the agent to loop the conversation until a position is given (Used DynamicWorkflows)
  * Done, the decision made is creating a workflow that implements a while loop, the agent doesn't allow to move into the next step until the input requirement is met
* Fanout 3 agents to search the job board providers
* Use an agent to stitch the results into a single file
