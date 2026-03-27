# Amoeba AI v2 Design Specification

## 1. v2 Vision Summary
Amoeba AI v2 evolves the system from a "safe reporter" (v1) to an "enterprise intelligence platform". It introduces a **Semantic Intelligence Layer** to decouple users from database schemas and a **Visual Report Builder** to allow self-service without raw SQL. 

**Core Value Prop:** "Intelligence without Risk."
CIOs trust it because:
1.  **Zero Data Leakage:** AI never touches the raw DB; it only sees approved "Reports".
2.  **Deterministic SQL:** All queries are constructed by a rigid logic engine, not an LLM.
3.  **Role-Based Security:** Strict separation between Admin (who maps data) and User (who consumes it).

---

## 2. High-Level System Architecture

The v2 architecture introduces a clear separation of concerns into three distinct layers, ensuring that the "Intelligence" (LLM) is sandboxed from the "Data" (DB).

```mermaid
graph TD
    subgraph "Client Isolator (Tenant Context)"
        User[End User (Chat)] --> |Natural Language| Gateway[API Gateway / Rate Limiter]
        Admin[Client Admin (ACP)] --> |Config & Builder| Gateway
    end

    Gateway --> |"Show me sales"| IntelLayer[Layer 3: Natural Language Analytics (LLM)]
    Gateway --> |"Build Report"| Builder[Layer 2: Visual Report Builder]

    subgraph "Trust Boundary - NO LLM ALLOWED"
        Builder --> |Generates Safe SQL| Registry[Report Registry (v2)]
        IntelLayer --> |"Execute Report: Sales_Q3"| Registry
        
        Registry --> |Managed SQL| FastPath[FastPath Engine (v1 Core)]
        
        subgraph "Layer 1: Semantic Intelligence"
            SemanticModel[Semantic Metadata Store]
            SchemaDisc[Schema Discovery Service]
        end
        
        Builder -.-> |Validates against| SemanticModel
    end

    subgraph "Data Layer (Private)"
        FastPath --> |Read-Only SQL| ClientDB[(Client ERP Database)]
    end

    %% Legend
    style User fill:#e1f5fe,stroke:#01579b
    style Admin fill:#e8f5e9,stroke:#1b5e20
    style ClientDB fill:#ffebee,stroke:#b71c1c
    style Registry fill:#fff9c4,stroke:#fbc02d
```

### Data Flow & Trust Boundaries
1.  **User Request:** Enters via Chat UI.
2.  **Intent Resolution:** System determines if request is "Navigational", "Reporting", or "Analytics".
3.  **Analytics (Layer 3):** If user asks "Why?", the LLM analyzes *outputs* from existing reports. It *cannot* issue new SQL.
4.  **Execution (FastPath):** When a report is needed, the `Report Registry` retrieves the pre-validated SQL template.
5.  **Data Access:** The `FastPath Engine` executes the SQL against `ClientDB`. **Crucially, this is the exact same engine as v1.**
6.  **Response:** Data is returned to the user (as chart, text, or Excel).

---

## 3. Layer 1: Semantic Intelligence (v2.1)

The Semantic Layer is the dictionary that translates "Business Logic" to "Database Schema". It prevents the mess of raw column names.

### Capabilities
-   **Column Aliasing:** Map `T001_CUST_NME` -> `Customer Name`.
-   **Synonyms:** Tag `revenue` with ["sales", "turnover", "income"].
-   **Date Resolution:** Define which column represents the "business date" for a table (e.g., `inv_date` not `created_at`).

### Data Model
Metadata is stored in a new Postgres table `semantic_metadata`, keyed by `(client_id, table_name, column_name)`.

```json
{
  "client_id": 101,
  "table": "sales_orders",
  "column": "total_amt",
  "label": "Total Revenue",
  "description": "Sum of all line items including tax",
  "synonyms": ["sales", "deal size"],
  "format": "currency",
  "is_pii": false
}
```

### Safety
-   **Admin-Only:** Only Client Admins can define these mappings in the ACP.
-   **No Hallucinations:** The Builder UI *only* shows columns that have defined Semantic Metadata. Raw columns are hidden by default.

---

## 4. Layer 2: Visual Report Builder (v2.2)

A no-code interface replacing the v1 "Register Report" flow.

### Workflow
1.  **Select Base Object:** User picks a "Business Entity" (e.g., "Invoices") defined in Layer 1.
2.  **Select Columns:** User checks boxes for "Invoice #", "Customer", "Total".
3.  **Add Filters:** "Status = Paid".
4.  **Join Data (Strict):**
    -   System shows *only* tables with **foreign keys** discovered during onboarding.
    -   User cannot type `ON a.id = b.id`. They simply click "Include Customer Details".
    -   System auto-generates the `LEFT JOIN`.
5.  **Save:** Saved to `Report Registry` with a deterministic SQL query.

### SQL Generation Safety
-   **Hidden:** Users never see the generated SQL.
-   **Deterministic:** The builder uses a template engine (e.g., Jinja2 or a query builder lib) to construct SQL.
-   **Validated:** Before saving, the system performs an `EXPLAIN` to ensure query validity.

---

## 5. Layer 3: Natural Language Analytics (v2.3)

This layer enables "Chat with your Data", but *strictly* scoped to registered reports.

### "Why did sales drop?" Implementation
1.  **Intent:** LLM identifies "Reasoning" intent over "Report: Sales Trend".
2.  **Data Fetch:** System executes "Sales Trend" report via FastPath (Limit: 500 rows).
3.  **Analysis:** The *result set* (JSON) is passed to the LLM context.
    -   *Prompt:* "Analyze this dataset. Identify columns driving the decrease in 'Total Revenue' between May and June."
4.  **Response:** LLM generates a text explanation and suggests a chart config.

### Hallucination Prevention
-   **Grounding:** The prompt includes "base your answer ONLY on the provided data context."
-   **Citations:** Every claim must reference a row/column from the report.

---

## 6. Roles & Permission Model

| Role | Access Scope | Can Modify | Can Execute |
| :--- | :--- | :--- | :--- |
| **Super Admin** (Amoeba) | System-wide | Global Config, Client Onboarding | All Debug |
| **Client Admin** (ERP Owner) | Tenant-wide | Semantic Layer, Report Builder, User Mgmt | All Reports |
| **End User** (Staff) | Assigned Reports | Personal Preferences | Assigned Reports |

*Rule: End Users can never define new SQL or change Semantic mappings.*

---

## 7. Safety & Governance Extensions

-   **Semantic Audit Logs:** Track "Who asked for 'Revenue'?" instead of just raw SQL logs.
-   **Misuse Detection:**
    -   heuristic: >10 failed report attempts in 1 minute.
    -   action: Temp-lock user and notify Client Admin.
-   **Feature Flags:**
    -   `ENABLE_V2_BUILDER`: Gradual rollout.
    -   `ENABLE_LLM_ANALYTICS`: Opt-in for conservative clients.

---

## 8. Migration Strategy (v1 -> v2)

**Strategy: "The Thin Varnish"**
v2 is built *around* v1.

1.  **Semantic Initialization:** Run a script to auto-generate Layer 1 metadata from existing v1 `discover_tables` schema. (e.g. `customer_name` -> "Customer Name").
2.  **Report Migration:** Existing v1 reports (simple `SELECT *`) are tagged as "Legacy". They continue to work via FastPath.
3.  **Upgrade:** Admin uses the new Builder to open a "Legacy" report. The Builder attempts to reverse-engineer it into the UI. If too complex, it remains "Read-Only SQL".

**Rollback:**
Since v2 writes to new tables (`semantic_metadata`) and reads from existing (`report_registry`), disabling v2 flags instantly reverts the UI to v1 mode without data loss.

---
