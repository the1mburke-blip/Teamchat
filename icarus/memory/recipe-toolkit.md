# Recipe toolkit (icarus-composer): build a new tool out of tools you already have

Source of truth for the plugin lives on the owner's PC at Icarus-Harness/recipes/ (README.md there is the same text).
Read this before telling the owner that a tool is missing.

## The idea (the hammer)
You have the handle. You have the head. Neither one is a hammer yet.
A **recipe** is how you put them together. You take what one tool gives you, feed it to the next,
and the whole chain becomes a new tool you can run by name.

If a job needs a tool you don't have, check your tools first. The job can often be done by chaining
two or three of them. Build the recipe, run it, keep it.

## What you do, in order
1. Look at your tool list. Pick the tools (and built-in parts, below) that cover the job between them.
2. Write one small JSON file describing the chain. This is the "put it together" step, and it is yours to do.
3. Save it in the recipes folder (`recipesDir`, set for icarus-composer in the harness config).
   It must end in `.json`. New or edited files work immediately. No restart, no reload.
4. Run `recipe_list`. Your recipe appears with its parameters. If it was rejected, the reason is shown. Fix it and list again.
5. Run `recipe_run` with `{ "name": "<recipe name>", "params": { ... } }`.

## Two tools
- `recipe_list`: shows every valid recipe and why any file was rejected.
- `recipe_run`: runs one recipe.

## Recipe format
```json
{
  "name": "error_summary",
  "description": "Count ERROR lines in a log file",
  "parameters": { "file": { "type": "string" } },
  "output": "ERROR lines in {{file}}: {{n}}",
  "steps": [
    { "tool": "read", "args": { "file_path": "{{file}}" }, "as": "log", "quiet": true },
    { "use": "lines", "args": { "text": "{{log}}", "contains": "ERROR" }, "as": "errs", "quiet": true },
    { "use": "count", "args": { "value": "{{errs}}" }, "as": "n" }
  ]
}
```
Read it as: read the file (tool one), keep only the ERROR lines (a built-in part), count them (another part).
Three pieces, one new tool.

- `name`: lowercase letters, digits and `_`, 2 to 40 characters. `description`: up to 200 characters.
- `parameters`: up to 8. Each is `string`, `number` or `boolean`, with an optional `default`.
- `steps`: 1 to 12. Each step has exactly one of `tool` (a tool you already have) or `use` (a built-in part), plus `args`.
- `as`: keep this step's result under a name. Later steps use `{{name}}` or `{{name.path.to.field}}`.
  A whole `"{{name}}"` keeps its type (list, object, number). Inside longer text it becomes text.
- `when`: `{ "value": "{{x}}", "op": "contains", "to": "y" }` runs the step only if true.
  ops: equals, not_equals, contains, not_contains, matches, exists, not_empty, gt, lt.
- `quiet: true` hides a step's output. `continueOnError: true` keeps going after a failure.
- `output`: return only this text instead of every step. Best for saving tokens.

## Built-in parts (`"use"`)
Parts work on data only. They cannot touch files, the network or a shell.
- `json_parse {text}`, `json_get {from, path}` (path like `items.0.name`)
- `regex_extract {text, pattern, flags?, group?, all?}`
- `lines {text, contains?, not_contains?, head?, tail?}`
- `csv_parse {text, header?}`, `join {items, sep?}`, `count {value}`
- `assert {value, op, to?, message?}`: stops the recipe with your message if the check fails. Use it to detect a blocker early.

## Rules that never change
- Every tool step goes through the same policy gate as if you called the tool yourself. If the gate refuses a step, the recipe stops there. A recipe adds no authority.
- A recipe cannot call another recipe, `run_code`, `plugin_manager`, `icarus_supervisor_spawn`, `workflow` or `ralph`.
- In shell steps (`bash`, `pwsh`), a substituted value containing `; & | ` $ < >` or a newline is refused.
- Limits: 1500 characters per step result, 6000 in total, 60 recipes, 20 KB each.
- Tool names vary. Check your real tool list and use the exact names you have.

## If the job still can't be done
Say exactly what is missing (which tool or part you would need) and tell the owner. Do not try to load code.
That is outside recipes by design.

## Report honestly
A recipe you wrote and ran yourself is PARTIAL until it is adjudicated. Do not call it PASS.
