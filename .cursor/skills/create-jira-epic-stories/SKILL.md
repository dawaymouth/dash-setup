---
name: create-jira-epic-stories
description: Generates and creates Jira tickets from a project plan or feature specification. Structures work into an Epic and User Stories following the INVEST principle, then creates tickets via the Jira MCP. Use when the user provides a project plan, requirements document, or feature spec and requests creation of Jira tickets, epics, or user stories.
---

# Create Jira Epic + Stories

## Prerequisites

- Jira MCP server is active and accessible.
- User has provided a project plan or feature description.
- Target Jira Project Key (e.g. `PROJ`) is known—ask if not provided.

## Workflow

### Step 1: Analyze and structure

1. Read the provided project plan thoroughly.
2. Identify the overarching goal or feature → this becomes the **Epic**.
3. Break the Epic into discrete, manageable user-facing pieces → these become **User Stories**.

### Step 2: Create the Epic

Use the Jira MCP tool (e.g. `create_issue`) to create the Epic first.

- **Project**: Provided Project Key.
- **Issue Type**: Epic.
- **Summary**: Clear, concise title for the overall feature.
- **Description**: High-level overview of the plan, business value, and scope.

Capture the returned Epic Issue Key (e.g. `PROJ-101`); it is required to link stories.

### Step 3: Draft User Stories (INVEST)

Before creating each story via the API, ensure it adheres to INVEST:

| Letter | Principle | Check |
|--------|-----------|--------|
| **I** | Independent | Can be worked on without blocking dependencies on other stories. |
| **N** | Negotiable | Describes "what" and "why"; "how" is left to the developer. |
| **V** | Valuable | Delivers clear value to the end-user or business. |
| **E** | Estimable | Enough context and clear acceptance criteria to be sized. |
| **S** | Small | Scope completable in a single sprint; break down if too large. |
| **T** | Testable | Clear, binary Acceptance Criteria verifiable by QA or automation. |

### Step 4: Story description format

Use this structure for every User Story description:

```markdown
**User Story:**
> As a [Role/Persona], I want to [Action/Feature] so that [Value/Benefit/Reason].

**Context:**
[Brief 1–2 sentence background on how this fits into the larger plan.]

**Acceptance Criteria:**
- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3
```

Use clear bullet points or Given/When/Then where appropriate.

### Step 5: Create stories via Jira MCP

1. For each drafted story, call the Jira MCP `create_issue` (or equivalent) tool.
2. **Link to Epic**: Set the parent Epic using the `parent` field, `customfield_10014` (Epic Link), or the instance’s standard epic relationship parameter—use the Epic Key from Step 2.
3. After all issues are created, output a summary table: Issue Key, Type, Summary, and link to the Epic.

## Response format

After successful creation, respond with:

```markdown
I have successfully created the Jira tickets based on your project plan.

**Epic:**
* [PROJ-101] Feature: New User Onboarding

**User Stories:**
* [PROJ-102] Story: Email Verification Step
* [PROJ-103] Story: Profile Setup Wizard
* [PROJ-104] Story: Welcome Tooltip Tour

Let me know if you would like to refine any of the acceptance criteria!
```

Replace issue keys and titles with the actual created tickets.
