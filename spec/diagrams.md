# Context Engineer — Mermaid Diagrams

## 1. Three-Level Hierarchy (System Architecture)

```mermaid
graph TD
    ROOT["<b>ROOT</b><br/>Engagement Context"]
    ROOT --- RC1[".context-root<br/><i>engagement name</i>"]
    ROOT --- RC2["AGENT.md<br/><i>entity details</i>"]
    ROOT --- RC3[".claude/tools/<br/><i>global tools</i>"]
    ROOT --- RC4["requirements.txt<br/><i>global deps</i>"]

    ROOT ==> CLASS1["<b>CLASS: treasury/</b>"]
    ROOT ==> CLASS2["<b>CLASS: reporting/</b>"]
    ROOT ==> CLASS3["<b>CLASS: collections/</b>"]

    CLASS1 --- CC1[".class.yaml<br/><i>orchestration manifest</i>"]
    CLASS1 --- CC2["AGENT.md<br/><i>class context for agents</i>"]
    CLASS1 --- CC4["tools/<br/><i>class-shared tools</i>"]

    CLASS1 ==> TASK1["<b>TASK: monthly-bank-fees/</b>"]
    CLASS1 ==> TASK2["<b>TASK: zba-entries/</b>"]
    CLASS1 ==> TASK3["<b>TASK: bank-reconciliation/</b>"]

    TASK1 --- TC1["SKILL.md<br/><i>operating manual</i>"]
    TASK1 --- TC2["learned.md<br/><i>accumulated patterns</i>"]
    TASK1 --- TC3["status.yaml<br/><i>execution state</i>"]
    TASK1 --- TC4["tools/<br/><i>task-specific scripts</i>"]
    TASK1 --- TC5["periods/<br/><i>date-keyed work folders</i>"]

    TC5 --- P1["2026-03/"]
    P1 --- PD["data/"]
    P1 --- PW["workpapers/"]
    P1 --- PR["review-notes/"]

    style ROOT fill:#4a90d9,color:#fff,stroke:#2c5f8a
    style CLASS1 fill:#7cb342,color:#fff,stroke:#558b2f
    style CLASS2 fill:#7cb342,color:#fff,stroke:#558b2f
    style CLASS3 fill:#7cb342,color:#fff,stroke:#558b2f
    style TASK1 fill:#ff8f00,color:#fff,stroke:#e65100
    style TASK2 fill:#ff8f00,color:#fff,stroke:#e65100
    style TASK3 fill:#ff8f00,color:#fff,stroke:#e65100
```

---

## 2. Task Status State Machine

```mermaid
stateDiagram-v2
    [*] --> not_started

    not_started --> in_progress : /start begins executing

    in_progress --> in_progress : Idempotent (crash recovery)
    in_progress --> review_ready : /start completes — draft ready
    in_progress --> blocked : /start fails

    review_ready --> in_progress : Human rejects draft (via /start)
    review_ready --> done : /done confirms & captures learnings

    done --> [*]

    blocked --> not_started : Human says "retry" (via /start)
    blocked --> abandoned : Human says "abandon" (via /start)

    abandoned --> [*]

    note right of review_ready
        Draft ready for review.
        Clears issues[].
        Can be rejected → in_progress.
    end note

    note right of done
        Terminal state.
        Clears issues[].
        check-periods.py resets
        to not_started when
        next anchor arrives.
    end note

    note right of abandoned
        Terminal state.
        Records reason in issues[].
        check-periods.py resets
        to not_started when
        next anchor arrives.
    end note

    note left of blocked
        Agent reports what failed
        in issues[]. Human decides
        retry or abandon.
    end note
```

---

## 3. Class Status Computation

```mermaid
stateDiagram-v2
    [*] --> not_started : All enabled tasks are not_started

    not_started --> in_progress : Any task moves beyond not_started

    in_progress --> done : All enabled tasks done or abandoned

    done --> not_started : Task statuses reset by<br/>check-periods.py (class status re-derived)

    note right of in_progress
        A task in blocked, in_progress,
        or review_ready keeps the
        class in_progress.
        Computed on the fly by /status
        from task status.yaml files.
        Not persisted to disk.
    end note

    note right of done
        No period field at class level —
        tasks may have different
        period formats.
        check-periods.py evaluates
        each task independently
        against its anchor.
    end note
```

---

## 4. Context Inheritance (Data Flow Down)

```mermaid
flowchart TB
    subgraph ROOT_CTX ["Root Context"]
        ENG["AGENT.md (root)<br/><i>entity, fiscal year, materiality, systems</i>"]
    end

    subgraph CLASS_CTX ["Class Context"]
        AGENT["AGENT.md (class)<br/><i>domain concepts, conventions</i>"]
        CLASSYAML[".class.yaml<br/><i>manifest, task list, phase order</i>"]
    end

    subgraph TASK_CTX ["Task Context"]
        SKILL["SKILL.md<br/><i>procedure, data sources, validation</i>"]
        LEARNED["learned.md<br/><i>patterns, edge cases, history</i>"]
        STATUS["status.yaml<br/><i>current period state</i>"]
    end

    ENG -->|"Always loaded"| AGENT
    ENG -.->|"Orchestrator only"| CLASSYAML

    AGENT -->|"Task agents get class AGENT.md<br/>(not .class.yaml)"| SKILL
    AGENT --> LEARNED
    AGENT --> STATUS

    CLASSYAML -.->|"Orchestrator only<br/>(future state)"| ORCH["Orchestrator Agent"]

    subgraph LOAD ["load-context.py"]
        LR["--level root<br/>root/AGENT.md"]
        LC["--level class<br/>root/AGENT.md → class/AGENT.md"]
        LT["--level task<br/>root/AGENT.md → class/AGENT.md →<br/>SKILL.md + learned.md + status.yaml"]
    end

    style ROOT_CTX fill:#e3f2fd,stroke:#1565c0
    style CLASS_CTX fill:#e8f5e9,stroke:#2e7d32
    style TASK_CTX fill:#fff3e0,stroke:#e65100
    style LOAD fill:#f3e5f5,stroke:#7b1fa2
```

---

## 5. MVP Workflow (Human as Orchestrator)

```mermaid
sequenceDiagram
    participant H as Human
    participant A as Agent
    participant FS as Filesystem
    participant S as Scripts

    H->>A: /status (from class directory)
    A->>FS: Read task status.yaml files
    FS-->>A: Compute rollup on the fly
    A-->>H: "2/3 done, 1 blocked in treasury"

    H->>A: "Work on monthly bank fees"
    A->>FS: Navigate to treasury/monthly-bank-fees/

    H->>A: /start
    Note over A: Step 0: Read status.yaml, route
    A->>S: set-status.py in_progress
    S->>FS: Validate transition, write status.yaml
    A->>S: install-deps.py
    S->>FS: Install requirements top-down
    A->>S: init-period.py 2026-03
    Note over S,FS: Checks status is in_progress,<br/>creates period dir.
    S->>FS: Create periods/2026-03/{data,workpapers,review-notes}
    A->>S: load-context.py --level task
    S->>FS: Read root/AGENT.md → class/AGENT.md → SKILL.md + learned.md + status.yaml
    S-->>A: Assembled context

    A->>FS: Read data, run tools, produce draft
    A->>FS: Write draft to workpapers/
    A->>S: set-status.py review_ready
    S->>FS: Write status.yaml (review_ready)
    A-->>H: "Draft ready for review"

    H->>H: Reviews draft
    H->>A: /done
    A->>S: set-status.py done
    S->>FS: Write status.yaml (done), clear issues[]
    A->>FS: Update learned.md (structured delta)
    A->>FS: git commit (skill owns the commit)
    A->>S: archive-period.py (upload to Google Drive)
    A-->>H: "Captured. Ready for next task."
```

---

## 6. Future State: Orchestrator Workflow

```mermaid
sequenceDiagram
    participant H as Human
    participant O as Orchestrator
    participant SA1 as Sub-Agent 1
    participant SA2 as Sub-Agent 2
    participant SA3 as Sub-Agent 3
    participant FS as Filesystem

    H->>O: "Run the close"
    O->>FS: load-context.py --level class --orchestrator
    FS-->>O: root/AGENT.md → class/AGENT.md → .class.yaml (with manifest)

    Note over O: Phase 1: order=1 tasks<br/>(parallel execution)

    par Phase 1 — Parallel
        O->>SA1: Launch: monthly-bank-fees
        SA1->>FS: load-context.py --level task
        SA1->>FS: Execute → produce draft
        SA1->>FS: set-status.py review_ready
        SA1-->>O: Complete

        O->>SA2: Launch: zba-entries
        SA2->>FS: load-context.py --level task
        SA2->>FS: Execute → produce draft
        SA2->>FS: set-status.py review_ready
        SA2-->>O: Complete
    end

    O->>FS: Read workpapers, compare against learned.md
    O->>FS: Write review-notes/ for each task
    O->>FS: set-status.py done (for each reviewed task)

    Note over O: Phase 2: order=2 tasks<br/>(only after ALL phase 1 complete)

    O->>SA3: Launch: bank-reconciliation
    SA3->>FS: load-context.py --level task
    SA3->>FS: Execute → produce reconciliation
    SA3->>FS: set-status.py review_ready
    SA3-->>O: Complete

    O->>FS: Review + set-status.py done
    O-->>H: "Treasury close complete.<br/>3 tasks executed. Ready for sign-off."
```

---

## 7. Script Composition (Skills → Scripts)

```mermaid
flowchart LR
    subgraph SKILLS ["Skills"]
        ONBOARD["/onboard"]
        START["/start"]
        DONE["/done"]
        STAT["/status"]
    end

    subgraph SCRIPTS ["Scripts"]
        LC["load-context.py"]
        ID["install-deps.py"]
        SS["set-status.py"]
        IC["init-class.py"]
        IP["init-period.py"]
        IT["init-task.py"]
        AP["archive-period.py"]
    end

    subgraph INFRA ["Infrastructure"]
        CP["check-periods.py<br/><i>(cron — writes status.yaml directly)</i>"]
    end

    ONBOARD --> LC
    ONBOARD --> IC
    ONBOARD --> ID
    ONBOARD --> IP
    ONBOARD --> IT
    ONBOARD --> SS

    START --> LC
    START --> ID
    START --> SS
    START --> IP

    DONE --> SS
    DONE --> AP

    STAT -.->|"reads task status.yaml files"| FS["Filesystem"]

    style SKILLS fill:#e8eaf6,stroke:#283593
    style SCRIPTS fill:#fce4ec,stroke:#b71c1c
    style INFRA fill:#fff9c4,stroke:#f9a825
```

---

## 8. Tool Inheritance (Resolution Order)

```mermaid
flowchart TB
    G["<b>Global</b><br/>.claude/tools/<br/><i>je_formatter.py, pdf_parser.py</i>"]
    C["<b>Class</b><br/>treasury/tools/<br/><i>chase_parser.py</i>"]
    T["<b>Task</b><br/>monthly-bank-fees/tools/<br/><i>fee_categorizer.py</i>"]

    G -->|"inherited by"| C
    C -->|"inherited by"| T

    T -.->|"shadows same-name<br/>tools from higher levels"| C
    C -.->|"shadows same-name<br/>tools from higher levels"| G

    RESOLVE["Resolution: task > class > global<br/><i>load-context.py outputs tool paths in priority order</i>"]

    style G fill:#4a90d9,color:#fff
    style C fill:#7cb342,color:#fff
    style T fill:#ff8f00,color:#fff
    style RESOLVE fill:#fff,stroke:#333,stroke-dasharray: 5 5
```

---

## 9. Blocked Recovery Flow

```mermaid
flowchart TD
    START["Task executing<br/>(in_progress)"] --> FAIL{"Execution<br/>fails?"}
    FAIL -->|No| REVIEW["status: review_ready<br/>Draft ready for review"]
    FAIL -->|Yes| BLOCKED["status: blocked<br/>Record reason in issues[]"]

    BLOCKED --> HUMAN{"Human<br/>investigates<br/>(via /start)"}
    HUMAN -->|"Retry"| RESET["status: not_started<br/>Clear issues[]"]
    HUMAN -->|"Abandon"| ABANDON["status: abandoned<br/>Record reason in issues[]"]

    RESET --> RERUN["/start again<br/>Fresh attempt"]
    RERUN --> START

    REVIEW --> REVIEWDEC{"Human<br/>reviews draft"}
    REVIEWDEC -->|"Approve"| CONFIRM["/done confirms<br/>Capture learnings"]
    REVIEWDEC -->|"Reject"| REJECT["status: in_progress<br/>(via /start — re-execute)"]
    REJECT --> START

    CONFIRM --> DONE["status: done<br/>Clear issues[]"]

    ABANDON --> TERMINAL["Terminal state<br/>New period can begin"]
    DONE --> TERMINAL

    TERMINAL --> PERIODRESET["check-periods.py<br/>(cron — resets to not_started<br/>when next anchor arrives)"]

    style BLOCKED fill:#ef5350,color:#fff
    style REVIEW fill:#ffa726,color:#fff
    style DONE fill:#66bb6a,color:#fff
    style ABANDON fill:#bdbdbd,color:#333
    style TERMINAL fill:#42a5f5,color:#fff
    style REJECT fill:#ffa726,color:#fff
```
