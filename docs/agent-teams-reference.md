# Agent Teams — Master Reference Guide

> Source: https://code.claude.com/docs/en/agent-teams  
> Last reviewed: 2026-04-11  
> Status: Experimental (enabled by default in this project)

---

## Table of Contents

1. [What Are Agent Teams?](#1-what-are-agent-teams)
2. [Enabling Agent Teams](#2-enabling-agent-teams)
3. [When to Use Agent Teams vs. Subagents](#3-when-to-use-agent-teams-vs-subagents)
4. [Architecture](#4-architecture)
5. [Starting a Team](#5-starting-a-team)
6. [Controlling the Team](#6-controlling-the-team)
7. [Task Management](#7-task-management)
8. [Communication Between Agents](#8-communication-between-agents)
9. [Permissions & Models](#9-permissions--models)
10. [Hooks for Quality Gates](#10-hooks-for-quality-gates)
11. [Token Costs](#11-token-costs)
12. [Best Practices](#12-best-practices)
13. [Use Case Patterns](#13-use-case-patterns)
14. [Limitations](#14-limitations)
15. [Troubleshooting](#15-troubleshooting)

---

## 1. What Are Agent Teams?

Agent teams let you coordinate **multiple independent Claude Code instances** working in parallel. One session acts as the **team lead** — it creates the team, spawns teammates, coordinates work, and synthesizes results. Each **teammate** is a fully independent Claude session with its own context window.

Unlike subagents (which only report back to the main agent), teammates can **message each other directly**, claim tasks autonomously, and work without constant supervision from the lead.

---

## 2. Enabling Agent Teams

Agent teams are **disabled by default**. Enable them in [settings.json](.claude/settings.local.json):

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

Or set it as a shell environment variable before launching Claude Code:

```bash
export CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1
claude
```

**Minimum version required:** Claude Code v2.1.32+. Check with `claude --version`.

---

## 3. When to Use Agent Teams vs. Subagents

| Dimension | Subagents | Agent Teams |
|:---|:---|:---|
| **Context window** | Own window; results return to caller | Own window; fully independent |
| **Communication** | Report results back to main agent only | Teammates message each other directly |
| **Coordination** | Main agent manages everything | Shared task list; self-coordination |
| **Best for** | Focused tasks where only result matters | Complex work requiring discussion/collaboration |
| **Token cost** | Lower — results summarized back | Higher — each teammate is a separate Claude instance |

### Use subagents when:
- You need quick, focused workers that report back
- Tasks are sequential or interdependent
- Work involves the same files
- Token cost is a primary concern

### Use agent teams when:
- Tasks are genuinely independent and parallelizable
- Teammates need to share findings and challenge each other
- Work spans multiple layers (frontend, backend, tests)
- Parallel exploration accelerates discovery (debugging, research, review)

---

## 4. Architecture

| Component | Role |
|:---|:---|
| **Team lead** | Main Claude Code session; creates team, spawns teammates, coordinates work |
| **Teammates** | Separate Claude Code instances; work on assigned tasks |
| **Task list** | Shared list of work items teammates claim and complete |
| **Mailbox** | Messaging system for inter-agent communication |

### Storage locations

- **Team config:** `~/.claude/teams/{team-name}/config.json`
- **Task lists:** `~/.claude/tasks/{team-name}/`

> **Do not hand-edit the team config.** It holds runtime state (session IDs, tmux pane IDs) and is overwritten on every state update.

### Context each teammate loads at spawn

- `CLAUDE.md` files from the working directory
- MCP servers from project and user settings
- Skills from project and user settings
- The spawn prompt from the lead
- **NOT** the lead's conversation history

---

## 5. Starting a Team

Tell Claude what you want in natural language. Be explicit about the team structure:

```text
Create an agent team with 3 teammates to analyze this API redesign:
- One focused on backwards compatibility
- One on performance impact
- One playing devil's advocate
```

Claude will:
1. Create a shared task list
2. Spawn each teammate with its role as context
3. Coordinate work and synthesize findings
4. Attempt team cleanup when done

### Display modes

| Mode | Description | Requirement |
|:---|:---|:---|
| `auto` (default) | Split panes if already in tmux, otherwise in-process | None |
| `in-process` | All teammates in your main terminal; Shift+Down to cycle | Any terminal |
| `tmux` | Each teammate in its own split pane | tmux or iTerm2 |

Override display mode globally in `~/.claude.json`:

```json
{
  "teammateMode": "in-process"
}
```

Or for a single session:

```bash
claude --teammate-mode in-process
```

> **Note for this project (Windows/VS Code):** Split-pane mode is NOT supported in VS Code's integrated terminal or Windows Terminal. Use `in-process` mode.

---

## 6. Controlling the Team

### Cycle through teammates (in-process mode)

- **Shift+Down** — cycle to next teammate
- **Enter** — view a teammate's session
- **Escape** — interrupt a teammate's current turn
- **Ctrl+T** — toggle the shared task list

### Require plan approval before implementation

```text
Spawn an architect teammate to refactor the authentication module.
Require plan approval before they make any changes.
```

Flow:
1. Teammate works in read-only plan mode
2. Sends plan approval request to lead
3. Lead reviews and approves or rejects with feedback
4. If rejected, teammate revises and resubmits
5. Once approved, teammate exits plan mode and begins implementation

Steer the lead's approval criteria in your prompt:
```text
Only approve plans that include test coverage. Reject plans that modify the database schema.
```

### Shut down a teammate

```text
Ask the researcher teammate to shut down.
```

The lead sends a shutdown request. The teammate can approve (exits gracefully) or reject with explanation.

### Clean up the entire team

```text
Clean up the team.
```

> **Always use the lead to run cleanup.** Teammates should never run cleanup — their team context may not resolve correctly and can leave resources in inconsistent state.

Cleanup fails if active teammates are still running. Shut them down first.

---

## 7. Task Management

### Task states
- `pending` — not yet started
- `in_progress` — claimed by a teammate
- `completed` — finished

### Task claiming
- **Lead assigns:** tell the lead which task goes to which teammate
- **Self-claim:** after finishing a task, a teammate automatically picks up the next unassigned, unblocked task

Task claiming uses **file locking** to prevent race conditions.

### Task dependencies

Tasks can depend on other tasks. A pending task with unresolved dependencies cannot be claimed until blockers are completed. The system unblocks tasks automatically when dependencies resolve.

### Share task list across sessions

```bash
CLAUDE_CODE_TASK_LIST_ID=my-project claude
```

This stores the task list in `~/.claude/tasks/my-project/`.

---

## 8. Communication Between Agents

### Messaging types

| Type | Description | When to use |
|:---|:---|:---|
| `message` | Send to one specific teammate | Most communication |
| `broadcast` | Send to all teammates simultaneously | Announcements; use sparingly (costs scale with team size) |

### How messages work
- Messages are delivered **automatically** — the lead does not need to poll
- Teammates notify the lead **automatically** when they finish (idle notification)
- Any teammate can message any other by name

### Predictable teammate names

To reference teammates in later prompts, specify names at spawn:

```text
Spawn a teammate named "security-reviewer" to audit src/auth/.
Spawn a teammate named "test-writer" to write tests for the same module.
```

---

## 9. Permissions & Models

### Permissions
- All teammates start with the **lead's permission settings**
- If the lead runs `--dangerously-skip-permissions`, all teammates do too
- You can change individual teammate permission modes **after spawning**, but not at spawn time

### Specifying models

```text
Create a team with 4 teammates to refactor these modules in parallel.
Use Sonnet for each teammate.
```

> **Cost tip:** Use Sonnet for teammates. It balances capability and cost well for coordination tasks. Reserve Opus for the lead or complex reasoning tasks.

### Subagent definitions as teammate roles

Define a role once and reuse it across teams:

```text
Spawn a teammate using the security-reviewer agent type to audit the auth module.
```

The teammate honors that definition's `tools` allowlist and `model`. The definition body is **appended** to the teammate's system prompt (not replacing it). Team coordination tools (`SendMessage`, task management) are always available even when `tools` restricts others.

> **Note:** `skills` and `mcpServers` in subagent definition frontmatter are **not applied** when running as a teammate. Teammates load these from project and user settings instead.

---

## 10. Hooks for Quality Gates

Hooks enforce rules automatically when teammates finish work or tasks are created/completed.

### Available team hooks

| Hook | When it fires | Can block? |
|:---|:---|:---|
| `TeammateIdle` | Teammate about to go idle | Yes — exit 2 keeps them working |
| `TaskCreated` | Task being created via TaskCreate tool | Yes — exit 2 prevents creation |
| `TaskCompleted` | Task being marked complete | Yes — exit 2 prevents completion |

### Exit code behavior

| Exit code | Behavior |
|:---|:---|
| `0` | Success; action proceeds |
| `2` | **Blocking** — stderr is fed back to the model; action blocked |
| Other | Non-blocking error; stderr shown in transcript only |

### Example: Prevent idle if uncommitted changes remain

```bash
#!/bin/bash
if [ $(git status --porcelain | wc -l) -gt 0 ]; then
  echo "Uncommitted changes remain. Commit or stash before going idle." >&2
  exit 2
fi
exit 0
```

Hook input for `TeammateIdle`:
```json
{
  "hook_event_name": "TeammateIdle",
  "teammate_name": "reviewer",
  "team_name": "my-project",
  "session_id": "abc123",
  "cwd": "/path/to/project"
}
```

### Example: Require tests to pass before task completion

```bash
#!/bin/bash
if ! npm test > /dev/null 2>&1; then
  echo "Tests must pass before marking task complete." >&2
  exit 2
fi
exit 0
```

### Example: Enforce task naming convention

```bash
#!/bin/bash
INPUT=$(cat)
SUBJECT=$(echo "$INPUT" | jq -r '.task_subject')

if ! echo "$SUBJECT" | grep -qE '^[A-Z]'; then
  jq -n '{"decision": "block", "reason": "Task subject must start with uppercase letter"}'
  exit 0
fi
exit 0
```

### Configuring hooks in settings.json

```json
{
  "hooks": {
    "TeammateIdle": [
      { "type": "command", "command": "~/.claude/hooks/check-pending-work.sh" }
    ],
    "TaskCreated": [
      { "type": "command", "command": "~/.claude/hooks/validate-task.sh" }
    ],
    "TaskCompleted": [
      { "type": "command", "command": "~/.claude/hooks/verify-completion.sh" }
    ]
  }
}
```

---

## 11. Token Costs

Each teammate = its own context window = independent token consumption.

**Cost scales linearly with team size.**

### Cost reduction strategies

| Strategy | Impact |
|:---|:---|
| Use Sonnet for teammates (not Opus) | High |
| Keep team size small (3–5 teammates) | High |
| Keep spawn prompts focused | Medium |
| Clean up teams when done (idle teammates still consume tokens) | Medium |
| Use subagents instead for simple delegation | High |

### Rule of thumb
- **3–5 teammates** is the sweet spot for most workflows
- **5–6 tasks per teammate** keeps everyone productive without thrashing
- More than 5 teammates rarely outperforms 3 focused ones

---

## 12. Best Practices

### Give teammates enough context in the spawn prompt

Teammates don't inherit the lead's conversation history. Include everything they need:

```text
Spawn a security reviewer teammate with the prompt:
"Review src/auth/ for security vulnerabilities.
Focus on token handling, session management, and input validation.
The app uses JWT tokens stored in httpOnly cookies.
Report findings with severity ratings (critical/high/medium/low)."
```

### Size tasks appropriately

| Size | Problem |
|:---|:---|
| Too small | Coordination overhead exceeds benefit |
| Too large | Long runs without check-ins; risk of wasted effort |
| Just right | Self-contained unit producing a clear deliverable (one function, one test file, one review) |

If the lead isn't creating enough tasks, ask it to split work into smaller pieces.

### Avoid file conflicts

Two teammates editing the same file = overwrites. Structure work so each teammate owns a distinct set of files.

### Monitor and steer

Don't let the team run unattended for too long. Check in, redirect failing approaches, and synthesize findings as they arrive.

### Start with research tasks when new to teams

Research and review (PR review, library investigation, bug investigation) have clear boundaries and don't risk merge conflicts. Use these to learn team behavior before attempting parallel implementation.

### Wait for teammates before the lead acts

If the lead starts implementing instead of delegating:
```text
Wait for your teammates to complete their tasks before proceeding.
```

### Use CLAUDE.md for shared context

`CLAUDE.md` is read by every teammate from their working directory. Use it to provide project-specific guidance that applies to all agents without repeating it in every spawn prompt.

---

## 13. Use Case Patterns

### Pattern 1: Parallel code review

```text
Create an agent team to review PR #142. Spawn three reviewers:
- One focused on security implications
- One checking performance impact
- One validating test coverage
Have them each review and report findings.
```

Best for: comprehensive review where multiple independent lenses are needed.

### Pattern 2: Competing hypotheses debugging

```text
Users report the app exits after one message instead of staying connected.
Spawn 5 agent teammates to investigate different hypotheses.
Have them talk to each other to try to disprove each other's theories,
like a scientific debate. Update the findings doc with whatever consensus emerges.
```

Best for: root cause analysis where anchoring on the first plausible theory is a risk.

### Pattern 3: Parallel module implementation

```text
Create a team with 4 teammates to implement these 4 independent modules in parallel.
Each teammate owns one module completely. No shared files.
Use Sonnet for each teammate.
```

Best for: greenfield feature work where modules have clear boundaries.

### Pattern 4: Cross-layer changes

```text
Create a team to implement the new user notification feature:
- One teammate handles the backend API endpoint
- One handles the frontend React component
- One writes the integration tests
They should coordinate via the task list and message each other when their piece is ready.
```

Best for: features that span multiple layers, each with a clear owner.

### Pattern 5: Multi-perspective design exploration

```text
I'm designing a CLI tool for tracking TODO comments across the codebase.
Create an agent team: one on UX, one on technical architecture, one as devil's advocate.
Have them explore from different angles and converge on a design.
```

Best for: early design decisions where diverse perspectives reduce blind spots.

---

## 14. Limitations

| Limitation | Impact | Workaround |
|:---|:---|:---|
| No session resumption for in-process teammates | `/resume` and `/rewind` don't restore teammates | Tell lead to spawn new teammates after resuming |
| Task status can lag | Stuck tasks block dependents | Check if work is done; manually update status or nudge teammate |
| Slow shutdown | Teammates finish current request before stopping | Wait; don't force-kill |
| One team per session | Can't run two teams from same lead | Clean up before starting a new team |
| No nested teams | Teammates can't spawn their own teams | Restructure work for the lead to manage all teammates |
| Lead is fixed | Can't promote a teammate to lead | Create a new session to be the lead |
| Permissions set at spawn | Can't set per-teammate modes at spawn time | Change individually after spawning |
| Split panes not supported in VS Code terminal, Windows Terminal, or Ghostty | — | Use `in-process` mode (works everywhere) |

---

## 15. Troubleshooting

### Teammates not appearing

1. In in-process mode, press **Shift+Down** — they may already be running
2. Check task complexity — Claude only spawns teams for tasks that warrant it
3. Verify `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` is set
4. For split-pane mode: `which tmux` to confirm tmux is in PATH

### Too many permission prompts

Pre-approve common operations in permission settings **before** spawning teammates to reduce interruptions.

### Teammates stopping on errors

Press Shift+Down to view their output, then either give additional instructions directly or spawn a replacement.

### Lead finishes before all work is done

```text
Keep going — not all tasks are complete yet.
```
Or proactively: include "wait for all teammates to finish before proceeding" in the initial prompt.

### Orphaned tmux sessions after team ends

```bash
tmux ls
tmux kill-session -t <session-name>
```

### Task stuck in pending with completed dependencies

Tell the lead:
```text
Task X looks complete. Please update its status and unblock dependent tasks.
```

---

## Quick Reference Card

```text
ENABLE:        Set CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 in settings.json
START:         "Create an agent team with N teammates to..."
CYCLE:         Shift+Down (in-process mode)
TASK LIST:     Ctrl+T
INTERRUPT:     Escape (in a teammate's session)
ASSIGN:        "Tell the researcher teammate to..."
PLAN MODE:     "Spawn X with plan approval required"
SHUTDOWN:      "Ask the X teammate to shut down"
CLEANUP:       "Clean up the team" (always via lead)

STORAGE:
  Team config: ~/.claude/teams/{name}/config.json  (do not edit)
  Task list:   ~/.claude/tasks/{name}/

DISPLAY MODE:  Set teammateMode in ~/.claude.json
               Options: auto | in-process | tmux
               Windows/VS Code: use in-process

HOOKS:
  TeammateIdle  — exit 2 to keep working
  TaskCreated   — exit 2 to block creation
  TaskCompleted — exit 2 to block completion

COST TIP:      Use Sonnet for teammates; 3–5 teammates is the sweet spot
```

---

*This guide was compiled from the official Claude Code documentation for use as a persistent reference in future agent team conversations.*
