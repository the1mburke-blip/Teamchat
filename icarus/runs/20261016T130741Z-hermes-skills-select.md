# Hermes skills selection (OpenRouter free, call 3 of day)

model requested: nvidia/nemotron-3-super-120b-a12b:free
when: 20261016T130741Z

status: HTTP 200
model returned: nvidia/nemotron-3-super-120b-a12b:free
finish_reason: stop

1. cronjob - Icarus needs a scheduler to run hourly repo/team-task supervision.  
2. memory - Icarus requires persistent memory to retain state across runs.  
3. github - Icarus must interact with GitHub repositories for supervision and work.  
4. systematic-debugging - Icarus verifies other agents' claims against tool logs, needing debugging skills.  
5. requesting-code-review - Icarus enforces approval gates, requiring code review requests.  
6. codebase-inspection - Icarus inspects repos to supervise tasks and enforce budgets.  
7. delegation - Icarus may delegate tasks to other agents as part of supervision.  
8. kanban - Icarus uses kanban to track team-task status and evidence reporting.  
9. web - Icarus needs web access for Shopify via Composio/MCP and free-model quota failover.  
10. safe - Icarus relies on safe toolset to enforce hard stops and allowlists.
