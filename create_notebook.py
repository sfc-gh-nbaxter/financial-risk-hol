import json
import uuid

cells = []

def _split(source):
    lines = source.split("\n")
    return [line + "\n" if i < len(lines) - 1 else line for i, line in enumerate(lines)]

def _id():
    return uuid.uuid4().hex[:8]

def md(source, name=None):
    meta = {}
    if name:
        meta["name"] = name
    cells.append({"cell_type": "markdown", "id": _id(), "metadata": meta, "source": _split(source)})

def sql(source, name=None):
    meta = {"language": "sql"}
    if name:
        meta["name"] = name
    cells.append({"cell_type": "code", "id": _id(), "execution_count": None, "metadata": meta, "outputs": [], "source": _split(source)})

# =============================================================================
# TITLE
# =============================================================================
md("""# Financial Services Risk Management — Hands-On Lab

| Detail | Value |
|---|---|
| **Duration** | ~120 minutes |
| **Prerequisites** | Snowflake account (Enterprise or [30-day trial](https://signup.snowflake.com/)) |
| **Warehouse** | SMALL, auto-suspend 60 s |

### Contents

| Step | Topic | Snowflake Features |
|:---:|---|---|
| **1** | Enable Cortex Code | Cross-Region Inference, Cortex Code |
| **2** | Setup Infrastructure | Database, Schemas, Virtual Warehouse, RBAC |
| **3** | Ingest & Transform Data | VARIANT, OBJECT_CONSTRUCT, LATERAL FLATTEN, Dynamic Tables |
| **🤖** | **Cortex Code Challenge** | **Build a Streamlit app from a prompt** |
| **4** | Security & Governance | Dynamic Data Masking, Row Access Policies |
| **5** | FinOps & Cost Management | Resource Monitors, Budgets, AI Cost Tracking |
| **6** | Time Travel & Cloning | Zero-Copy Clone, AT(OFFSET), UNDROP |
| **7** | Unstructured Data | Internal Stages, Directory Tables |
| **8** | Market Data Enrichment | Synthetic Market Data, Data Enrichment via JOINs |
| **9** | Cortex AI Functions | AI_CLASSIFY, AI_SENTIMENT, AI_EXTRACT, SUMMARIZE |
| **10** | Snowflake Intelligence | Semantic Views, Cortex Search, Cortex Agent |
| **11** | Cleanup | DROP objects |

---

### Data Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        RISK_HOL  (Database)                        │
├──────────────┬──────────────┬───────────────┬───────────────────────┤
│  RAW_DATA    │  ANALYTICS   │  GOVERNANCE   │  UNSTRUCTURED         │
│  (Schema)    │  (Schema)    │  (Schema)     │  (Schema)             │
│              │              │               │                       │
│ counterpar-  │ risk_events  │ email_mask    │ risk_documents_stage  │
│   ties       │  (Dynamic    │ phone_mask    │   (Internal Stage +   │
│              │   Table)     │  (Masking     │    Directory Table)   │
│ risk_events  │              │   Policies)   │                       │
│   _raw       │ risk_summary │               │ document_catalogue    │
│  (VARIANT    │  (Dynamic    │ risk_severity │                       │
│   JSON)      │   Table)     │   _policy     │                       │
│              │              │  (Row Access  │                       │
│              │              │   Policy)     │                       │
└──────┬───────┴──────▲───────┴───────────────┴───────────────────────┘
       │              │
       │   ┌──────────┴──────────┐
       └──►│   Dynamic Tables    │
           │   (Automated ELT)   │
           │                     │
           │  risk_events_raw    │
           │    ──[LAG 1 min]──► │  risk_events
           │    ──[LAG 2 min]──► │  risk_summary
           └─────────────────────┘

┌──────────────────────┐    ┌──────────────────────┐
│  Market Data         │    │  Streamlit in         │
│  (Synthetic rates    │    │  Snowflake            │
│   & spreads)         │◄──►│  (Risk Dashboard)     │
└──────────────────────┘    └──────────────────────┘

┌──────────────────────┐
│  Cortex AI Functions │
│  CLASSIFY, SENTIMENT │
│  EXTRACT, SUMMARIZE  │
└──────────────────────┘

Roles:  RISK_ADMIN  ──►  RISK_ANALYST  ──►  RISK_AUDITOR
        (full access)    (masked PII)      (HIGH/CRITICAL only)

Warehouse:  RISK_WH  (SMALL, auto-suspend 60s)
```""", name="Title & Contents")

# =============================================================================
# STEP 1 — CORTEX CODE PREREQUISITES
# =============================================================================
md("""---
## 1 · Enable Cortex Code

**Cortex Code** is Snowflake's AI coding agent — it can write SQL, build Streamlit apps, create notebooks, and answer questions about your account. It is available in Snowsight and as a CLI.

**Prerequisite:** Cross-region inference must be enabled so Cortex Code can access the required LLMs.""", name="1 · Enable Cortex Code")

md("""### 1.1 — Enable Cross-Region Inference
This allows Snowflake to route AI model requests to regions where the models are available. Required for Cortex Code (and all Cortex AI features).""", name="1.1 Cross-Region Inference")

sql("""USE ROLE accountadmin;

ALTER ACCOUNT SET CORTEX_ENABLED_CROSS_REGION = 'ANY_REGION';""", name="1.1 Enable Cross-Region")

md("""### 1.2 — Verify Cross-Region Inference""", name="1.2 Verify")

sql("""SHOW PARAMETERS LIKE 'CORTEX_ENABLED_CROSS_REGION' IN ACCOUNT;""", name="1.2 Show Parameter")

md("""### 1.3 — Open Cortex Code
You can now access Cortex Code in Snowsight:

1. Click the **Cortex Code** icon (sparkle ✦) in the left navigation bar — or press **Cmd + J** (Mac) / **Ctrl + J** (Windows)
2. Cortex Code opens as a side panel and is context-aware of the notebook you have open
3. You can ask it natural-language questions, generate SQL, or build entire applications

> **Tip:** We will use Cortex Code later in this lab to build a Streamlit risk dashboard from a single prompt.""", name="1.3 Open Cortex Code")

# =============================================================================
# STEP 2 — SETUP
# =============================================================================
md("""---
## 2 · Setup Infrastructure""", name="2 · Setup Infrastructure")

md("""### 2.1 — Create Database & Schemas
Snowflake **databases** are the top-level container for all objects. **Schemas** organise tables, views, and policies into logical groups.""", name="2.1 Create DB & Schemas")

sql("""USE ROLE sysadmin;

CREATE OR REPLACE DATABASE risk_hol
    COMMENT = 'Financial Services Risk Management Hands-On Lab';

CREATE OR REPLACE SCHEMA risk_hol.raw_data
    COMMENT = 'Raw ingested data (landing zone)';

CREATE OR REPLACE SCHEMA risk_hol.analytics
    COMMENT = 'Analytical views and transformed data';

CREATE OR REPLACE SCHEMA risk_hol.governance
    COMMENT = 'Masking policies, row-access policies';

CREATE OR REPLACE SCHEMA risk_hol.unstructured
    COMMENT = 'Unstructured document storage and processing';""", name="2.1 Run Create DB")

md("""### 2.2 — Create a Virtual Warehouse
A **Virtual Warehouse** provides compute for queries. Key settings:
- `WAREHOUSE_SIZE` — controls compute power (XSMALL → 6XLARGE)
- `AUTO_SUSPEND` — shuts down after N seconds of idle (saves credits)
- `AUTO_RESUME` — wakes automatically on the next query""", name="2.2 Create Warehouse")

sql("""CREATE OR REPLACE WAREHOUSE risk_wh
    WAREHOUSE_SIZE = 'SMALL'
    AUTO_SUSPEND  = 60
    AUTO_RESUME   = TRUE
    INITIALLY_SUSPENDED = TRUE
    COMMENT = 'Compute warehouse for Risk HOL';""", name="2.2 Run Create WH")

sql("""USE WAREHOUSE risk_wh;
USE DATABASE  risk_hol;
USE SCHEMA    raw_data;""", name="2.2b Set Context")

md("""### 2.3 — Role-Based Access Control (RBAC)
Snowflake enforces access through **roles**. We create a three-tier hierarchy:

| Role | Purpose |
|---|---|
| `risk_admin` | Full access — owns all objects |
| `risk_analyst` | Read analytics, PII is masked |
| `risk_auditor` | Read-only, sees only HIGH / CRITICAL events |""", name="2.3 RBAC Roles")

sql("""USE ROLE securityadmin;

-- Create the role hierarchy
CREATE ROLE IF NOT EXISTS risk_admin
    COMMENT = 'Admin role for the Risk HOL';

CREATE ROLE IF NOT EXISTS risk_analyst
    COMMENT = 'Analyst role — analytics only, no PII';

CREATE ROLE IF NOT EXISTS risk_auditor
    COMMENT = 'Auditor role — read-only, limited rows';

GRANT ROLE risk_admin   TO ROLE sysadmin;
GRANT ROLE risk_analyst TO ROLE risk_admin;
GRANT ROLE risk_auditor TO ROLE risk_admin;""", name="2.3 Create Roles")

md("""### 2.3b — Grant Privileges
Grant each role the minimum privileges it needs on the database, schemas, and warehouse.""", name="2.3b Grant Privileges")

sql("""-- Database & schema access
GRANT USAGE ON DATABASE risk_hol TO ROLE risk_admin;
GRANT USAGE ON DATABASE risk_hol TO ROLE risk_analyst;
GRANT USAGE ON DATABASE risk_hol TO ROLE risk_auditor;

GRANT USAGE ON ALL SCHEMAS IN DATABASE risk_hol TO ROLE risk_admin;
GRANT USAGE ON ALL SCHEMAS IN DATABASE risk_hol TO ROLE risk_analyst;
GRANT USAGE ON ALL SCHEMAS IN DATABASE risk_hol TO ROLE risk_auditor;

GRANT ALL ON SCHEMA risk_hol.raw_data       TO ROLE risk_admin;
GRANT ALL ON SCHEMA risk_hol.analytics      TO ROLE risk_admin;
GRANT ALL ON SCHEMA risk_hol.governance     TO ROLE risk_admin;
GRANT ALL ON SCHEMA risk_hol.unstructured   TO ROLE risk_admin;

-- Future grants so new objects are automatically accessible
GRANT SELECT ON FUTURE TABLES IN SCHEMA risk_hol.analytics TO ROLE risk_analyst;
GRANT SELECT ON FUTURE VIEWS  IN SCHEMA risk_hol.analytics TO ROLE risk_analyst;
GRANT SELECT ON FUTURE VIEWS  IN SCHEMA risk_hol.analytics TO ROLE risk_auditor;""", name="2.3b Grants DB & Schema")

sql("""-- Warehouse & account-level privileges
USE ROLE accountadmin;

GRANT USAGE ON WAREHOUSE risk_wh TO ROLE risk_admin;
GRANT USAGE ON WAREHOUSE risk_wh TO ROLE risk_analyst;
GRANT USAGE ON WAREHOUSE risk_wh TO ROLE risk_auditor;

GRANT APPLY MASKING POLICY    ON ACCOUNT TO ROLE risk_admin;
GRANT APPLY ROW ACCESS POLICY ON ACCOUNT TO ROLE risk_admin;""", name="2.3b Grants WH & Account")

sql("""-- Set working context
USE ROLE      risk_admin;
USE WAREHOUSE risk_wh;
USE DATABASE  risk_hol;

SELECT 'Setup complete' AS status;""", name="2.3b Set Working Context")

md("""### 2.4 — Verify Setup
Use `SHOW` commands to confirm the objects exist.""", name="2.4 Verify Setup")

sql("""SHOW SCHEMAS IN DATABASE risk_hol;""", name="2.4 Show Schemas")

sql("""SHOW WAREHOUSES LIKE 'RISK%';""", name="2.4 Show Warehouses")

sql("""SHOW ROLES LIKE 'RISK%';""", name="2.4 Show Roles")
# =============================================================================
# STEP 3 — SEMI-STRUCTURED DATA
# =============================================================================
md("""---
## 3 · Ingest & Transform Semi-Structured Data""", name="3 · Ingest & Transform")

md("""### 3.1 — Create the Counterparties Table
Use `GENERATOR` to produce 500 synthetic rows and `ARRAY_CONSTRUCT` to pick random values — no CSV files needed.""", name="3.1 Counterparties")

sql("""USE ROLE      risk_admin;
USE DATABASE  risk_hol;
USE SCHEMA    raw_data;
USE WAREHOUSE risk_wh;

CREATE OR REPLACE TABLE counterparties (
    counterparty_id   VARCHAR(10)  PRIMARY KEY,
    legal_name        VARCHAR(200),
    country           VARCHAR(50),
    sector            VARCHAR(50),
    credit_rating     VARCHAR(5),
    lei               VARCHAR(20),
    pii_contact_email VARCHAR(100),
    pii_phone         VARCHAR(30),
    onboarding_date   DATE,
    is_active         BOOLEAN DEFAULT TRUE
);""", name="3.1a Create Table")

sql("""INSERT INTO counterparties
SELECT
    'CP' || LPAD(SEQ4()::VARCHAR, 6, '0'),

    ARRAY_CONSTRUCT(
        'Meridian Capital','Atlas Holdings','Vanguard Finance',
        'Pinnacle Investments','Sterling Bank','Oceanic Securities',
        'Northern Trust Corp','Pacific Ventures','Eagle Trading',
        'Falcon Asset Mgmt'
    )[UNIFORM(0, 9, RANDOM())]::VARCHAR
        || ' ' || UNIFORM(1, 999, RANDOM())::VARCHAR,

    ARRAY_CONSTRUCT('US','UK','DE','JP','SG','CH','AU','CA','FR','BR')
        [UNIFORM(0, 9, RANDOM())]::VARCHAR,

    ARRAY_CONSTRUCT('Banking','Insurance','Asset Management','Hedge Fund',
        'Private Equity','Pension Fund','Sovereign Wealth')
        [UNIFORM(0, 6, RANDOM())]::VARCHAR,

    ARRAY_CONSTRUCT('AAA','AA+','AA','AA-','A+','A','A-','BBB+','BBB','BBB-','BB+','BB')
        [UNIFORM(0, 11, RANDOM())]::VARCHAR,

    UPPER(SUBSTRING(MD5(RANDOM()::VARCHAR), 1, 20)),

    'contact' || SEQ4() || '@'
        || ARRAY_CONSTRUCT('meridian.com','atlas.io','vanguard.net','sterling.co.uk')
           [UNIFORM(0, 3, RANDOM())]::VARCHAR,

    '+' || UNIFORM(1, 9, RANDOM())::VARCHAR
        || LPAD(UNIFORM(100000000, 999999999, RANDOM())::VARCHAR, 9, '0'),

    DATEADD('day', -UNIFORM(30, 3650, RANDOM()), CURRENT_DATE()),
    TRUE
FROM TABLE(GENERATOR(ROWCOUNT => 500));""", name="3.1b Insert Data")

md("""### 3.2 — Load Semi-Structured JSON into VARIANT
Snowflake's **VARIANT** type stores JSON, Avro, Parquet, or XML natively. `OBJECT_CONSTRUCT` builds JSON objects; `ARRAY_CONSTRUCT` builds arrays — all inside a single INSERT.""", name="3.2 JSON into VARIANT")

sql("""CREATE OR REPLACE TABLE risk_events_raw (
    event_id     VARCHAR(20) PRIMARY KEY,
    ingestion_ts TIMESTAMP   DEFAULT CURRENT_TIMESTAMP(),
    payload      VARIANT
);""", name="3.2a Create Table")

sql("""INSERT INTO risk_events_raw (event_id, payload)
SELECT
    'EVT' || LPAD(SEQ4()::VARCHAR, 10, '0'),
    OBJECT_CONSTRUCT(
        'event_type',
            ARRAY_CONSTRUCT('CREDIT','MARKET','OPERATIONAL','LIQUIDITY','COUNTERPARTY')
            [UNIFORM(0, 4, RANDOM())]::VARCHAR,
        'event_date',
            DATEADD('day', -UNIFORM(1, 730, RANDOM()), CURRENT_DATE())::VARCHAR,
        'counterparty_id',
            'CP' || LPAD(UNIFORM(0, 499, RANDOM())::VARCHAR, 6, '0'),
        'exposure_usd',
            ROUND(UNIFORM(10000, 50000000, RANDOM())::FLOAT, 2),
        'currency',
            ARRAY_CONSTRUCT('USD','EUR','GBP','JPY','CHF')
            [UNIFORM(0, 4, RANDOM())]::VARCHAR,
        'risk_score',
            ROUND(UNIFORM(1, 100, RANDOM())::FLOAT, 1),
        'region',
            ARRAY_CONSTRUCT('AMERICAS','EMEA','APAC')
            [UNIFORM(0, 2, RANDOM())]::VARCHAR,
        'description',
            ARRAY_CONSTRUCT(
                'Limit breach on trading book',
                'Margin call trigger event',
                'System outage in settlement',
                'Failed trade reconciliation',
                'VaR exceedance detected',
                'Collateral shortfall',
                'Regulatory capital threshold',
                'Counterparty downgrade alert'
            )[UNIFORM(0, 7, RANDOM())]::VARCHAR,
        'severity',
            ARRAY_CONSTRUCT('LOW','MEDIUM','HIGH','CRITICAL')
            [UNIFORM(0, 3, RANDOM())]::VARCHAR,
        'status',
            ARRAY_CONSTRUCT('OPEN','INVESTIGATING','MITIGATED','CLOSED')
            [UNIFORM(0, 3, RANDOM())]::VARCHAR,
        'mitigation_actions',
            ARRAY_CONSTRUCT(
                OBJECT_CONSTRUCT(
                    'action',   'Increase collateral',
                    'owner',    'Risk Ops',
                    'deadline', DATEADD('day', UNIFORM(1, 30, RANDOM()), CURRENT_DATE())::VARCHAR
                ),
                OBJECT_CONSTRUCT(
                    'action',   'Reduce exposure',
                    'owner',    'Trading Desk',
                    'deadline', DATEADD('day', UNIFORM(1, 14, RANDOM()), CURRENT_DATE())::VARCHAR
                )
            )
    )
FROM TABLE(GENERATOR(ROWCOUNT => 10000));""", name="3.2b Insert JSON")

md("""### 3.3 — Query VARIANT with Colon Notation
Access JSON fields directly using **colon notation** (`payload:field`) and cast to SQL types with `::STRING`, `::DATE`, etc.""", name="3.3 Query VARIANT")

sql("""SELECT
    event_id,
    payload:event_type::STRING       AS event_type,
    payload:event_date::DATE         AS event_date,
    payload:counterparty_id::STRING  AS counterparty_id,
    payload:exposure_usd::NUMBER(15,2) AS exposure_usd,
    payload:risk_score::FLOAT        AS risk_score,
    payload:severity::STRING         AS severity,
    payload:status::STRING           AS status
FROM risk_events_raw
LIMIT 20;""", name="3.3 Colon Notation")

md("""### 3.3b — LATERAL FLATTEN for Nested Arrays
`LATERAL FLATTEN` explodes a nested JSON array into rows — one row per array element. This is how you parse repeated structures like `mitigation_actions`.""", name="3.3b LATERAL FLATTEN")

sql("""SELECT
    r.event_id,
    r.payload:event_type::STRING  AS event_type,
    f.value:action::STRING        AS action,
    f.value:owner::STRING         AS owner,
    f.value:deadline::DATE        AS deadline
FROM risk_events_raw r,
    LATERAL FLATTEN(INPUT => r.payload:mitigation_actions) f
LIMIT 20;""", name="3.3b Flatten Query")

md("""### 3.4 — Dynamic Tables (Automated ELT)
**Dynamic Tables** continuously transform data as the source changes — no orchestrator or scheduled tasks required. The `LAG` parameter sets the maximum acceptable staleness.""", name="3.4 Dynamic Tables")

sql("""CREATE OR REPLACE DYNAMIC TABLE analytics.risk_events
    LAG       = '1 minute'
    WAREHOUSE = risk_wh
AS
SELECT
    r.event_id,
    r.payload:event_type::STRING       AS event_type,
    r.payload:event_date::DATE         AS event_date,
    r.payload:counterparty_id::STRING  AS counterparty_id,
    r.payload:exposure_usd::NUMBER(15,2) AS exposure_usd,
    r.payload:currency::STRING         AS currency,
    r.payload:risk_score::FLOAT        AS risk_score,
    r.payload:region::STRING           AS region,
    r.payload:description::STRING      AS description,
    r.payload:severity::STRING         AS severity,
    r.payload:status::STRING           AS status
FROM raw_data.risk_events_raw r;""", name="3.4a DT risk_events")

md("""### 3.4b — Summary Dynamic Table (Chained Pipeline)
Dynamic Tables can reference other Dynamic Tables. Snowflake automatically builds a refresh DAG. View it in **Data > Databases > Dynamic Tables > Graph**.""", name="3.4b Summary DT")

sql("""CREATE OR REPLACE DYNAMIC TABLE analytics.risk_summary
    LAG       = '2 minutes'
    WAREHOUSE = risk_wh
AS
SELECT
    re.event_type,
    re.severity,
    re.region,
    DATE_TRUNC('MONTH', re.event_date) AS month,
    COUNT(*)                           AS event_count,
    SUM(re.exposure_usd)               AS total_exposure,
    ROUND(AVG(re.risk_score), 1)       AS avg_risk_score,
    COUNT(CASE WHEN re.status = 'OPEN' THEN 1 END) AS open_events
FROM analytics.risk_events re
GROUP BY re.event_type, re.severity, re.region, DATE_TRUNC('MONTH', re.event_date);""", name="3.4b DT risk_summary")

md("""### 3.5 — Verify Dynamic Tables""", name="3.5 Verify DTs")

sql("""SELECT * FROM analytics.risk_events LIMIT 10;""", name="3.5a Query Events")

sql("""SELECT * FROM analytics.risk_summary ORDER BY month DESC LIMIT 20;""", name="3.5b Query Summary")

# =============================================================================
# STEP 3.5 — BUILD A STREAMLIT APP WITH CORTEX CODE
# =============================================================================
md("""---
## 🤖 Cortex Code Challenge — Build a Risk Dashboard with AI

Now that the data pipeline is running, let's use **Cortex Code** to build a **Streamlit in Snowflake** app — entirely from a natural-language prompt.

### Instructions
1. Open **Cortex Code** — click the ✦ icon in the left sidebar (or **Cmd/Ctrl + J**)
2. Copy and paste the prompt below into the Cortex Code chat
3. Review the generated code, then click **Accept** to create the app
4. Click **Run** to launch the app in Snowsight

### Prompt

```
Create a Streamlit in Snowflake app called RISK_DASHBOARD in the RISK_HOL.ANALYTICS schema
that connects to the RISK_HOL.ANALYTICS.RISK_SUMMARY dynamic table using warehouse RISK_WH
and role RISK_ADMIN.

The app should have:

1. A title "Risk Exposure Dashboard" with a subtitle showing today's date
2. A sidebar with three dropdown filters:
   - Region (AMERICAS, EMEA, APAC, or All)
   - Severity (LOW, MEDIUM, HIGH, CRITICAL, or All)
   - Event Type (CREDIT, MARKET, OPERATIONAL, LIQUIDITY, COUNTERPARTY, or All)
3. A row of four KPI metric cards at the top showing:
   - Total Events
   - Total Exposure (formatted as $X.XM or $X.XB)
   - Average Risk Score
   - Open Events
4. A bar chart showing Total Exposure by Event Type using Altair
5. A line chart showing Event Count by Month using Altair
6. A heatmap or grouped bar chart showing Event Count by Severity and Region
7. A data table at the bottom with the filtered data

Use st.columns for layout, st.metric for KPIs, and Altair for all charts.
Apply the filters from the sidebar to all visuals and metrics.
Use @st.cache_data with a TTL of 60 seconds for the data query.
```

> **What just happened?** Cortex Code read your prompt, understood the database schema, and generated a complete Streamlit app with interactive filters, KPI cards, and Altair charts — deployed directly in Snowflake with no local environment needed.""", name="🤖 Cortex Code Challenge")

# =============================================================================
# STEP 4 — SECURITY
# =============================================================================
md("""---
## 4 · Security & Governance""", name="4 · Security & Governance")

md("""### 4.1 — Dynamic Data Masking
**Masking policies** replace sensitive column values at query time based on the caller's role. The policy is attached to a column — no application code changes needed.""", name="4.1 Data Masking")

sql("""USE ROLE     risk_admin;
USE DATABASE risk_hol;
USE SCHEMA   governance;""", name="4.1 Set Context")

sql("""CREATE OR REPLACE MASKING POLICY email_mask
    AS (val STRING) RETURNS STRING ->
    CASE
        WHEN CURRENT_ROLE() IN ('RISK_ADMIN', 'ACCOUNTADMIN', 'SYSADMIN')
            THEN val
        ELSE REGEXP_REPLACE(val, '.+@', '****@')
    END;""", name="4.1a Email Mask")

sql("""CREATE OR REPLACE MASKING POLICY phone_mask
    AS (val STRING) RETURNS STRING ->
    CASE
        WHEN CURRENT_ROLE() IN ('RISK_ADMIN', 'ACCOUNTADMIN', 'SYSADMIN')
            THEN val
        ELSE CONCAT('***-***-', RIGHT(val, 4))
    END;""", name="4.1b Phone Mask")

md("""### 4.1b — Apply Masking Policies to Columns
Attach each policy to its target column with `ALTER TABLE ... SET MASKING POLICY`.""", name="4.1b Apply Policies")

sql("""ALTER TABLE raw_data.counterparties
    MODIFY COLUMN pii_contact_email
    SET MASKING POLICY governance.email_mask;

ALTER TABLE raw_data.counterparties
    MODIFY COLUMN pii_phone
    SET MASKING POLICY governance.phone_mask;""", name="4.1b Apply to Columns")

md("""### 4.2 — Test Masking: Admin View (Unmasked)
As `risk_admin`, you see the real PII values.""", name="4.2 Admin View")

sql("""USE ROLE risk_admin;

SELECT counterparty_id, legal_name, pii_contact_email, pii_phone
FROM raw_data.counterparties
LIMIT 5;""", name="4.2 Query as Admin")

md("""### 4.2b — Test Masking: Analyst View (Masked)
As `risk_analyst`, email and phone are automatically redacted.""", name="4.2b Analyst View")

sql("""GRANT SELECT ON TABLE raw_data.counterparties TO ROLE risk_analyst;

USE ROLE risk_analyst;

SELECT counterparty_id, legal_name, pii_contact_email, pii_phone
FROM raw_data.counterparties
LIMIT 5;""", name="4.2b Query as Analyst")

sql("""USE ROLE risk_admin;""", name="4.2c Reset Role")

md("""### 4.3 — Row Access Policy (Row-Level Security)
A **Row Access Policy** filters rows at query time based on the caller's role. This policy limits visibility by event severity:

| Role | Sees |
|---|---|
| `risk_admin` | All rows |
| `risk_analyst` | Everything except CRITICAL |
| `risk_auditor` | HIGH and CRITICAL only |""", name="4.3 Row Access Policy")

sql("""CREATE OR REPLACE ROW ACCESS POLICY governance.risk_severity_policy
    AS (severity STRING) RETURNS BOOLEAN ->
    CASE
        WHEN CURRENT_ROLE() IN ('RISK_ADMIN', 'ACCOUNTADMIN', 'SYSADMIN')
            THEN TRUE
        WHEN CURRENT_ROLE() = 'RISK_ANALYST' AND severity != 'CRITICAL'
            THEN TRUE
        WHEN CURRENT_ROLE() = 'RISK_AUDITOR' AND severity IN ('CRITICAL', 'HIGH')
            THEN TRUE
        ELSE FALSE
    END;""", name="4.3a Create RAP")

sql("""ALTER DYNAMIC TABLE analytics.risk_events
    ADD ROW ACCESS POLICY governance.risk_severity_policy ON (severity);""", name="4.3b Apply RAP")

md("""### 4.3b — Test RLS: Auditor View
The auditor should only see HIGH and CRITICAL severity events.""", name="4.3b Auditor View")

sql("""GRANT SELECT ON DYNAMIC TABLE analytics.risk_events TO ROLE risk_auditor;

USE ROLE risk_auditor;

SELECT severity, COUNT(*) AS event_count
FROM analytics.risk_events
GROUP BY severity;""", name="4.3c Query as Auditor")

sql("""USE ROLE risk_admin;""", name="4.3d Reset Role")

# =============================================================================
# STEP 5 — FINOPS & COST MANAGEMENT
# =============================================================================
md("""---
## 5 · FinOps & Cost Management

Snowflake provides three layers of cost governance:

| Layer | Scope | Key Feature |
|---|---|---|
| **Resource Monitors** | Warehouse credit quotas | Notify / suspend when thresholds are reached |
| **Budgets** | Account or custom object groups | Monthly spend limits with forecasting-based alerts |
| **ACCOUNT_USAGE views** | Historical reporting | Warehouse credits, serverless metering, Cortex AI tokens |

In financial services, tight cost controls are essential for regulatory compliance and operational discipline.""", name="5 · FinOps & Cost Management")

md("""### 5.1 — Resource Monitor
A **Resource Monitor** sets a credit quota on one or more warehouses. When usage reaches a threshold, Snowflake can notify administrators or suspend the warehouse automatically. Only `ACCOUNTADMIN` can create resource monitors.

| Trigger | Action |
|---|---|
| 75% of quota | Send notification |
| 100% of quota | Suspend warehouse (finish running queries) |
| 110% of quota | Suspend immediately (cancel running queries) |""", name="5.1 Resource Monitor")

sql("""USE ROLE accountadmin;

CREATE OR REPLACE RESOURCE MONITOR risk_wh_monitor
    WITH CREDIT_QUOTA = 10
    FREQUENCY = MONTHLY
    START_TIMESTAMP = IMMEDIATELY
    TRIGGERS ON 75 PERCENT DO NOTIFY
             ON 100 PERCENT DO SUSPEND
             ON 110 PERCENT DO SUSPEND_IMMEDIATE;

ALTER WAREHOUSE risk_wh SET RESOURCE_MONITOR = risk_wh_monitor;""", name="5.1a Create Monitor")

sql("""SHOW RESOURCE MONITORS LIKE 'RISK%';""", name="5.1b Verify Monitor")

md("""### 5.2 — Warehouse Credit Usage
The `SNOWFLAKE.ACCOUNT_USAGE` schema provides 365 days of historical data with ~45-minute latency. `WAREHOUSE_METERING_HISTORY` tracks compute credits consumed by each warehouse per hour.""", name="5.2 Warehouse Credits")

sql("""SELECT
    warehouse_name,
    DATE_TRUNC('DAY', start_time)        AS usage_date,
    SUM(credits_used)                    AS total_credits,
    SUM(credits_used_compute)            AS compute_credits,
    SUM(credits_used_cloud_services)     AS cloud_credits
FROM snowflake.account_usage.warehouse_metering_history
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY warehouse_name, usage_date
ORDER BY usage_date DESC, total_credits DESC;""", name="5.2 Query WH Credits")

md("""### 5.3 — Cortex AI Consumption
Cortex AI Functions (AI_CLASSIFY, AI_SENTIMENT, etc.) are billed per token. Two views help track this spend:

| View | Granularity | Key Columns |
|---|---|---|
| `METERING_DAILY_HISTORY` | Daily totals by service type | `SERVICE_TYPE`, `CREDITS_USED` |
| `CORTEX_AI_FUNCTIONS_USAGE_HISTORY` | Per-query detail | `FUNCTION_NAME`, `MODEL_NAME`, `CREDITS`, `TOKENS` |

> **Tip:** Run these queries after completing Step 9 (Cortex AI Functions) to see the actual cost of the AI calls you made in this lab.""", name="5.3 Cortex AI Costs")

sql("""SELECT
    service_type,
    DATE_TRUNC('DAY', usage_date)   AS day,
    SUM(credits_used)               AS total_credits
FROM snowflake.account_usage.metering_daily_history
WHERE service_type IN ('AI_SERVICES', 'CORTEX_CODE_CLI', 'CORTEX_CODE_SNOWSIGHT')
  AND usage_date >= DATEADD('day', -30, CURRENT_DATE())
GROUP BY service_type, day
ORDER BY day DESC, total_credits DESC;""", name="5.3a AI Daily Credits")

sql("""SELECT
    DATE_TRUNC('DAY', start_time)   AS usage_date,
    function_name,
    model_name,
    SUM(credits)                    AS total_credits,
    SUM(tokens)                     AS total_tokens,
    COUNT(DISTINCT query_id)        AS query_count
FROM snowflake.account_usage.cortex_ai_functions_usage_history
WHERE start_time >= DATEADD('day', -7, CURRENT_TIMESTAMP())
GROUP BY usage_date, function_name, model_name
ORDER BY usage_date DESC, total_credits DESC;""", name="5.3b AI Per-Function Detail")

md("""### 5.4 — Budgets (Overview)
**Budgets** are Snowflake's modern cost governance layer. Unlike resource monitors (warehouse-only), budgets cover **all** credit-consuming services — including serverless features like Dynamic Tables, Cortex AI, and Snowpipe. Budgets use time-series forecasting to alert you *before* you exceed your monthly limit.

> **Note:** If the budget is already activated, the ACTIVATE call will return a `BUDGET_ALREADY_ACTIVATED` error — this is safe to ignore.""", name="5.4 Budgets")

sql("""-- Activate account budget (ignore error if already activated)
CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!ACTIVATE();""", name="5.4a Activate Budget")

sql("""CALL SNOWFLAKE.LOCAL.ACCOUNT_ROOT_BUDGET!SET_SPENDING_LIMIT(500);""", name="5.4b Set Limit")

md("""### 5.5 — Reset Context""", name="5.5 Reset Context")

sql("""USE ROLE risk_admin;
USE WAREHOUSE risk_wh;""", name="5.5 Reset Context SQL")

# =============================================================================
# STEP 6 — TIME TRAVEL & CLONING
# =============================================================================
md("""---
## 6 · Time Travel & Zero-Copy Cloning""", name="6 · Time Travel & Cloning")

md("""### 6.1 — Zero-Copy Clone
`CLONE` creates an instant, metadata-only copy of a table (or database/schema). No data is physically duplicated — storage is shared until one side diverges.""", name="6.1 Zero-Copy Clone")

sql("""USE ROLE risk_admin;

CREATE OR REPLACE TABLE raw_data.counterparties_dev
    CLONE raw_data.counterparties;

SELECT 'PRODUCTION' AS source, COUNT(*) AS row_count FROM raw_data.counterparties
UNION ALL
SELECT 'DEV CLONE'  AS source, COUNT(*) AS row_count FROM raw_data.counterparties_dev;""", name="6.1 Clone Table")

md("""### 6.2 — Simulate an Accidental Update
Oops — someone ran an UPDATE without a WHERE clause.""", name="6.2 Accidental Update")

sql("""UPDATE raw_data.counterparties
SET is_active = FALSE;

SELECT COUNT(*) AS active_count
FROM raw_data.counterparties
WHERE is_active = TRUE;""", name="6.2 Bad UPDATE")

md("""### 6.3 — Recover with Time Travel
**Time Travel** lets you query or restore data as it existed at any point within the retention window (1 day on trial, up to 90 days on Enterprise). Use `AT(OFFSET => -N)` where N is seconds in the past.""", name="6.3 Time Travel")

sql("""SELECT
    (SELECT COUNT(*) FROM raw_data.counterparties WHERE is_active = TRUE)
        AS current_active,
    (SELECT COUNT(*) FROM raw_data.counterparties AT(OFFSET => -60*5) WHERE is_active = TRUE)
        AS five_min_ago_active;""", name="6.3a Compare Data")

sql("""CREATE OR REPLACE TABLE raw_data.counterparties
    AS SELECT * FROM raw_data.counterparties AT(OFFSET => -60*5);

SELECT COUNT(*) AS active_count
FROM raw_data.counterparties
WHERE is_active = TRUE;""", name="6.3b Restore Table")

md("""### 6.4 — UNDROP
`UNDROP` recovers a dropped table, schema, or database within the Time Travel retention window — no backup restore needed.""", name="6.4 UNDROP")

sql("""DROP TABLE raw_data.counterparties_dev;""", name="6.4a Drop Table")

sql("""UNDROP TABLE raw_data.counterparties_dev;

SELECT COUNT(*) AS row_count FROM raw_data.counterparties_dev;""", name="6.4b Undrop Table")

sql("""-- Final cleanup of the dev clone
DROP TABLE raw_data.counterparties_dev;""", name="6.4c Cleanup Clone")

# =============================================================================
# STEP 7 — UNSTRUCTURED DATA
# =============================================================================
md("""---
## 7 · Unstructured Data""", name="7 · Unstructured Data")

md("""### 7.1 — Internal Stage with Directory Table
An **Internal Stage** stores files (PDFs, images, CSVs, etc.) inside Snowflake. Enabling `DIRECTORY` adds an auto-populated metadata catalogue you can query with SQL.""", name="7.1 Internal Stage")

sql("""USE SCHEMA unstructured;

CREATE OR REPLACE STAGE risk_documents_stage
    DIRECTORY = (ENABLE = TRUE)
    COMMENT   = 'Internal stage for regulatory and risk report documents';""", name="7.1 Create Stage")

md("""### 7.2 — Document Catalogue (Simulated)
In production, upload files via `PUT` or the Snowsight UI and query `DIRECTORY(@stage)`. Here we simulate a catalogue table for six typical risk management documents.""", name="7.2 Document Catalogue")

sql("""CREATE OR REPLACE TABLE document_catalogue (
    doc_id       VARCHAR(10)  PRIMARY KEY,
    file_name    VARCHAR(200),
    doc_type     VARCHAR(50),
    department   VARCHAR(50),
    upload_date  DATE,
    file_size_kb NUMBER,
    summary      VARCHAR(500)
);

INSERT INTO document_catalogue VALUES
    ('DOC001', 'Q4_2025_VaR_Report.pdf',          'Risk Report',       'Market Risk',
        '2025-12-15', 2450, 'Quarterly Value-at-Risk report covering equity, FX, and rates portfolios'),
    ('DOC002', 'Basel_III_Capital_Adequacy.pdf',   'Regulatory Filing', 'Compliance',
        '2025-11-30', 5800, 'Basel III capital adequacy submission for the supervisory authority'),
    ('DOC003', 'Operational_Risk_Incident_Log.pdf','Incident Report',   'Operational Risk',
        '2026-01-10', 1200, 'Monthly operational risk incident log and loss event summary'),
    ('DOC004', 'Counterparty_Credit_Review.pdf',   'Credit Report',     'Credit Risk',
        '2026-02-01', 3400, 'Annual counterparty credit worthiness review and rating assessment'),
    ('DOC005', 'Stress_Test_Results_2025.pdf',     'Stress Test',       'Enterprise Risk',
        '2025-12-20', 7800, 'Annual stress test results under adverse and severely adverse scenarios'),
    ('DOC006', 'AML_SAR_Filing_Template.pdf',      'Compliance',        'Financial Crime',
        '2026-01-15',  890, 'Suspicious Activity Report template and filing guidance');""", name="7.2a Create & Load")

sql("""SELECT doc_type, COUNT(*) AS doc_count, SUM(file_size_kb) AS total_size_kb
FROM document_catalogue
GROUP BY doc_type
ORDER BY doc_count DESC;""", name="7.2b Query Catalogue")

# =============================================================================
# STEP 8 — MARKET DATA ENRICHMENT
# =============================================================================
md("""---
## 8 · Market Data Enrichment""", name="8 · Market Data")

md("""### 8.1 — Acquire Data from Snowflake Marketplace
The **Snowflake Marketplace** provides instant access to live, governed datasets from hundreds of providers — no ETL, no file transfers. For financial services, **FactSet** offers free sample datasets including portfolio analytics, sector attribution, and holdings data.

**To install FactSet Analytics (sample):**
1. Navigate to **Data Products > Marketplace** in the left sidebar
2. Search for **"FactSet Analytics"** and select **FactSet Analytics (sample)** (Free)
3. Click **Get** → accept the terms → assign to the `RISK_HOL` database or create a new database
4. The shared database appears immediately — no data is copied; it's a live secure share

> **Marketplace URL:** [FactSet Analytics (sample)](https://app.snowflake.com/marketplace/listing/GZT0ZGCQ51UP/factset-factset-analytics-sample)

The dataset includes:

| Table | Description |
|---|---|
| `CHARACTERISTICS` | Security-level fundamental characteristics and derived analytics |
| `EQ_SECTOR_ATTRIBUTION` | Equity sector-level performance attribution |
| `FI_SECTOR_ATTRIBUTION` | Fixed income sector attribution |
| `FI_SECTOR_EXPOSURES` | Fixed income sector exposures |
| `HOLDINGS` | Portfolio holdings with weights and valuations |""", name="8.1 Marketplace Acquisition")

sql("""-- After installing the FactSet listing, query the equity sector attribution
-- If you have not yet installed the listing, this query will fail — that's OK, continue to 8.2
SELECT *
FROM FACTSET_ANALYTICS__SAMPLE.FDS.EQ_SECTOR_ATTRIBUTION
WHERE ACCT = 'OFFICIAL_PR_EQ_ACWI_X_US'
  AND LEVEL = '3'
LIMIT 20;""", name="8.1b Query FactSet Data")

md("""### 8.2 — Generate Synthetic Market Data (Fallback)
If you were unable to install the FactSet listing (e.g. on a trial account without Marketplace access), we generate a self-contained reference dataset of daily interest rates, FX rates, and CDS spreads using `GENERATOR`.""", name="8.2 Synthetic Market Data")

sql("""USE ROLE risk_admin;
USE SCHEMA analytics;

CREATE OR REPLACE TABLE market_data AS
WITH date_spine AS (
    SELECT DATEADD('day', -SEQ4(), CURRENT_DATE()) AS market_date
    FROM TABLE(GENERATOR(ROWCOUNT => 730))
)
SELECT
    d.market_date,
    ROUND(3.5 + (UNIFORM(-100, 100, RANDOM())::FLOAT / 1000), 4) AS fed_funds_rate,
    ROUND(1.05 + (UNIFORM(-500, 500, RANDOM())::FLOAT / 10000), 4) AS eur_usd_rate,
    ROUND(0.78 + (UNIFORM(-300, 300, RANDOM())::FLOAT / 10000), 4) AS gbp_usd_rate,
    ROUND(148.0 + (UNIFORM(-500, 500, RANDOM())::FLOAT / 100), 2) AS usd_jpy_rate,
    ROUND(50 + UNIFORM(-20, 80, RANDOM())::FLOAT, 1) AS cds_spread_bps
FROM date_spine d;""", name="8.2a Create Market Data")

sql("""SELECT * FROM analytics.market_data ORDER BY market_date DESC LIMIT 10;""", name="8.2b Preview Market Data")

md("""### 8.3 — Enrich Risk Events with Market Context
Join internal risk events with market data to see what conditions prevailed on the day each event occurred. This is how you would combine Marketplace data (or synthetic data) with your own tables.""", name="8.3 Enrich Data")

sql("""CREATE OR REPLACE VIEW analytics.risk_with_market_context AS
SELECT
    re.event_id,
    re.event_date,
    re.event_type,
    re.severity,
    re.exposure_usd,
    re.region,
    md.fed_funds_rate,
    md.eur_usd_rate,
    md.cds_spread_bps
FROM analytics.risk_events re
LEFT JOIN analytics.market_data md
    ON re.event_date = md.market_date;""", name="8.3a Enriched View")

sql("""SELECT event_type, severity,
    ROUND(AVG(exposure_usd), 0) AS avg_exposure,
    ROUND(AVG(fed_funds_rate), 4) AS avg_fed_rate,
    ROUND(AVG(cds_spread_bps), 1) AS avg_cds_spread
FROM analytics.risk_with_market_context
WHERE event_date >= DATEADD('month', -6, CURRENT_DATE())
GROUP BY event_type, severity
ORDER BY avg_exposure DESC
LIMIT 15;""", name="8.3b Query Enriched Data")

# =============================================================================
# STEP 9 — CORTEX AI FUNCTIONS
# =============================================================================
md("""---
## 9 · Cortex AI Functions

**Cortex AI Functions** let you run LLM-powered analytics directly in SQL — no Python, no external APIs, and your data never leaves Snowflake. In this step we apply four functions to the risk event descriptions.

| Function | Purpose | Output |
|---|---|---|
| `AI_CLASSIFY` | Categorise text into predefined labels | Label (VARCHAR) |
| `AI_SENTIMENT` | Score sentiment from -1 (negative) to +1 (positive) | FLOAT |
| `AI_EXTRACT` | Extract structured fields from free text | OBJECT (JSON) |
| `SUMMARIZE` | Condense long text into a shorter summary | VARCHAR |""", name="9 · Cortex AI Functions")

md("""### 9.1 — AI_CLASSIFY: Categorise Risk Events
`AI_CLASSIFY` assigns one of your predefined labels to each piece of text. Here we classify each risk event description into a regulatory category.""", name="9.1 AI_CLASSIFY")

sql("""SELECT
    event_id,
    description,
    SNOWFLAKE.CORTEX.AI_CLASSIFY(
        description,
        ['Market Risk', 'Credit Risk', 'Operational Risk', 'Liquidity Risk', 'Compliance']
    ):label::STRING AS ai_category
FROM analytics.risk_events
LIMIT 10;""", name="9.1 Classify Query")

md("""### 9.2 — AI_SENTIMENT: Score Event Severity Tone
`AI_SENTIMENT` returns a sentiment classification for each text input. Risk event descriptions should skew negative — let's verify.""", name="9.2 AI_SENTIMENT")

sql("""SELECT
    event_id,
    description,
    severity,
    SNOWFLAKE.CORTEX.AI_SENTIMENT(description):categories[0]:sentiment::STRING AS sentiment
FROM analytics.risk_events
LIMIT 10;""", name="9.2 Sentiment Query")

sql("""SELECT
    severity,
    COUNT(*) AS event_count,
    COUNT_IF(SNOWFLAKE.CORTEX.AI_SENTIMENT(description):categories[0]:sentiment::STRING = 'negative') AS negative_count,
    ROUND(negative_count / event_count * 100, 1) AS pct_negative
FROM analytics.risk_events
WHERE event_date >= DATEADD('month', -3, CURRENT_DATE())
GROUP BY severity
ORDER BY pct_negative DESC;""", name="9.2b Sentiment by Severity")

md("""### 9.3 — AI_EXTRACT: Pull Structured Data from Text
`AI_EXTRACT` extracts specific fields from unstructured text and returns them as a JSON object. Here we extract the **affected_system** and **trigger** from each event description.""", name="9.3 AI_EXTRACT")

sql("""SELECT
    event_id,
    description,
    SNOWFLAKE.CORTEX.AI_EXTRACT(
        description,
        ['affected_system', 'trigger']
    ) AS extracted,
    extracted:affected_system::STRING AS affected_system,
    extracted:trigger::STRING AS trigger
FROM analytics.risk_events
LIMIT 10;""", name="9.3 Extract Query")

md("""### 9.4 — SUMMARIZE: Summarise Risk Events
`SUMMARIZE` condenses text. While individual descriptions are already short, the function shines when you combine multiple rows using `LISTAGG` and summarise them into a single narrative.""", name="9.4 SUMMARIZE")

sql("""WITH recent_critical AS (
    SELECT LISTAGG(description, '. ') WITHIN GROUP (ORDER BY event_date DESC) AS all_descriptions
    FROM analytics.risk_events
    WHERE severity = 'CRITICAL'
        AND event_date >= DATEADD('month', -1, CURRENT_DATE())
)
SELECT SNOWFLAKE.CORTEX.SUMMARIZE(all_descriptions) AS critical_events_summary
FROM recent_critical;""", name="9.4 Summarise Query")

# =============================================================================
# STEP 10 — SNOWFLAKE INTELLIGENCE
# =============================================================================
md("""---
## 10 · Snowflake Intelligence

**Snowflake Intelligence** combines structured data, unstructured documents, and external web knowledge into a single conversational AI agent. In this step we build all three components:

| Component | Purpose | Snowflake Feature |
|---|---|---|
| Semantic View | Natural-language queries over risk metrics | Cortex Analyst |
| Cortex Search Service | Semantic search over risk documents | Cortex Search (RAG) |
| Cortex Agent | Orchestrates all tools into one assistant | Cortex Agent + Snowflake Intelligence |

The agent will be able to answer questions like *"What is our total exposure by region?"*, *"Find documents about Basel III"*, and *"What are the latest capital requirements?"* — all from a single chat interface.""", name="10 · Snowflake Intelligence")

md("""### 10.1 — Create a Semantic View
A **Semantic View** defines business-friendly dimensions and metrics over your tables. Cortex Analyst uses it to convert natural language into SQL. We also add **verified queries** — pre-validated question/SQL pairs that improve accuracy and serve as onboarding suggestions.""", name="10.1 Semantic View")

sql("""USE ROLE risk_admin;
USE WAREHOUSE risk_wh;

CREATE OR REPLACE SEMANTIC VIEW risk_hol.analytics.risk_exposure_sv

  TABLES (
    risk_summary AS risk_hol.analytics.risk_summary
      PRIMARY KEY (event_type, severity, region, month)
      COMMENT = 'Monthly risk event aggregations by type, severity, and region'
  )

  DIMENSIONS (
    risk_summary.event_type_dim AS event_type
      WITH SYNONYMS = ('risk type', 'category')
      COMMENT = 'Type of risk event: CREDIT, MARKET, OPERATIONAL, LIQUIDITY, or COUNTERPARTY',
    risk_summary.severity_dim AS severity
      WITH SYNONYMS = ('risk level', 'priority')
      COMMENT = 'Severity level: LOW, MEDIUM, HIGH, or CRITICAL',
    risk_summary.region_dim AS region
      COMMENT = 'Geographic region: AMERICAS, EMEA, or APAC',
    risk_summary.month_dim AS month
      COMMENT = 'Month of the risk events (DATE truncated to first of month)'
  )

  METRICS (
    risk_summary.total_events AS SUM(event_count)
      COMMENT = 'Total number of risk events',
    risk_summary.total_exposure_usd AS SUM(total_exposure)
      WITH SYNONYMS = ('exposure', 'total exposure', 'financial exposure')
      COMMENT = 'Total financial exposure in USD',
    risk_summary.avg_risk_score AS AVG(avg_risk_score)
      COMMENT = 'Average risk score on a scale of 1-100',
    risk_summary.total_open_events AS SUM(open_events)
      WITH SYNONYMS = ('open events', 'unresolved events')
      COMMENT = 'Number of events still in OPEN status'
  )

  COMMENT = 'Semantic view for risk exposure analysis'

  AI_VERIFIED_QUERIES (
    exposure_by_region AS (
      QUESTION 'What is the total exposure by region?'
      VERIFIED_AT 1714780800
      ONBOARDING_QUESTION TRUE
      VERIFIED_BY '(STEWARD = risk_admin)'
      SQL 'SELECT region, SUM(total_exposure) AS total_exposure_usd FROM risk_hol.analytics.risk_summary GROUP BY region ORDER BY total_exposure_usd DESC'
    ),
    critical_events_by_type AS (
      QUESTION 'How many critical events do we have by event type?'
      VERIFIED_AT 1714780800
      ONBOARDING_QUESTION TRUE
      VERIFIED_BY '(STEWARD = risk_admin)'
      SQL 'SELECT event_type, SUM(event_count) AS critical_events FROM risk_hol.analytics.risk_summary WHERE severity = ''CRITICAL'' GROUP BY event_type ORDER BY critical_events DESC'
    ),
    monthly_trend AS (
      QUESTION 'Show me the monthly trend of total exposure'
      VERIFIED_AT 1714780800
      ONBOARDING_QUESTION TRUE
      VERIFIED_BY '(STEWARD = risk_admin)'
      SQL 'SELECT month, SUM(total_exposure) AS total_exposure_usd FROM risk_hol.analytics.risk_summary GROUP BY month ORDER BY month'
    ),
    open_events_by_severity AS (
      QUESTION 'Which severity level has the most open events?'
      VERIFIED_AT 1714780800
      VERIFIED_BY '(STEWARD = risk_admin)'
      SQL 'SELECT severity, SUM(open_events) AS total_open FROM risk_hol.analytics.risk_summary GROUP BY severity ORDER BY total_open DESC'
    ),
    highest_risk_region AS (
      QUESTION 'Which region has the highest average risk score?'
      VERIFIED_AT 1714780800
      VERIFIED_BY '(STEWARD = risk_admin)'
      SQL 'SELECT region, ROUND(AVG(avg_risk_score), 1) AS avg_score FROM risk_hol.analytics.risk_summary GROUP BY region ORDER BY avg_score DESC LIMIT 1'
    ),
    operational_risk_emea AS (
      QUESTION 'What is the total exposure for operational risk events in EMEA?'
      VERIFIED_AT 1714780800
      VERIFIED_BY '(STEWARD = risk_admin)'
      SQL 'SELECT SUM(total_exposure) AS operational_exposure_emea FROM risk_hol.analytics.risk_summary WHERE event_type = ''OPERATIONAL'' AND region = ''EMEA'''
    )
  );""", name="10.1a Create Semantic View")

sql("""SHOW SEMANTIC VIEWS IN SCHEMA risk_hol.analytics;""", name="10.1b Verify Semantic View")

md("""### 10.2 — Create Cortex Search Service
A **Cortex Search Service** indexes unstructured text for semantic search and retrieval-augmented generation (RAG). We index the `summary` column of our document catalogue so the agent can find relevant risk documents.""", name="10.2 Cortex Search")

sql("""CREATE OR REPLACE CORTEX SEARCH SERVICE risk_hol.unstructured.risk_docs_search
    ON summary
    ATTRIBUTES doc_type, department
    WAREHOUSE = risk_wh
    TARGET_LAG = '1 hour'
AS (
    SELECT doc_id, file_name, doc_type, department, upload_date, summary
    FROM risk_hol.unstructured.document_catalogue
);""", name="10.2a Create Search Service")

sql("""SELECT PARSE_JSON(
  SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
    'risk_hol.unstructured.risk_docs_search',
    '{
      "query": "capital adequacy regulatory filing",
      "columns": ["file_name", "doc_type", "summary"],
      "limit": 3
    }'
  )
)['results'] AS search_results;""", name="10.2b Test Search")

md("""### 10.3 — Create Cortex Agent
The **Cortex Agent** orchestrates multiple tools — structured data (Cortex Analyst), document search (Cortex Search), web search, and charting — into a single conversational interface accessible via Snowflake Intelligence.""", name="10.3 Cortex Agent")

sql("""CREATE OR REPLACE AGENT risk_hol.analytics.risk_intelligence_agent
    COMMENT = 'Risk management agent for Snowflake Intelligence'
    FROM SPECIFICATION
    $$
    models:
      orchestration: auto

    instructions:
      system: "You are a financial risk management assistant for a global bank. Answer questions about risk events, exposure, severity, and regulatory documents. Use the structured data tool for quantitative questions about risk metrics. Use the document search tool for policy and regulatory document questions. Use web search for external regulatory updates or market context."
      sample_questions:
        - question: "What is our total exposure by region?"
        - question: "How many critical events do we have by event type?"
        - question: "Show me the monthly trend of total exposure"
        - question: "What regulatory documents do we have about Basel III?"
        - question: "What are the latest Basel IV capital requirements?"
        - question: "Which region has the highest average risk score?"
        - question: "Find documents related to stress testing"
        - question: "What is our operational risk exposure in EMEA?"

    tools:
      - tool_spec:
          type: "cortex_analyst_text_to_sql"
          name: "risk_data_analyst"
          description: "Queries structured risk event data including exposure amounts, event counts, risk scores, and open events. Covers dimensions: event type (CREDIT, MARKET, OPERATIONAL, LIQUIDITY, COUNTERPARTY), severity (LOW, MEDIUM, HIGH, CRITICAL), region (AMERICAS, EMEA, APAC), and month. Use for quantitative questions about risk metrics."
      - tool_spec:
          type: "cortex_search"
          name: "risk_document_search"
          description: "Searches internal risk management documents including VaR reports, Basel III filings, incident logs, credit reviews, stress test results, and AML templates. Use for questions about policies, procedures, regulatory filings, or specific document contents."
      - tool_spec:
          type: "web_search"
          name: "web_search"
          description: "Searches the public web for external regulatory updates, Basel committee publications, market news, or industry context not available in internal data."
      - tool_spec:
          type: "data_to_chart"
          name: "data_to_chart"
          description: "Generates visualizations from query results. Use when the user asks to show trends, comparisons, or distributions visually."

    tool_resources:
      risk_data_analyst:
        semantic_view: "risk_hol.analytics.risk_exposure_sv"
      risk_document_search:
        name: "risk_hol.unstructured.risk_docs_search"
        max_results: "5"
        title_column: "file_name"
        id_column: "doc_id"
    $$;""", name="10.3a Create Agent")

md("""### 10.4 — Try it in Snowflake Intelligence

Your agent is now live. Access it via **AI & ML > Agents** in Snowsight, or go to `https://ai.snowflake.com`.

**Sample questions to try:**

| Tool | Question |
|---|---|
| Cortex Analyst | *What is the total exposure by region?* |
| Cortex Analyst | *How many critical events by event type?* |
| Cortex Analyst | *Show me the monthly trend of total exposure* |
| Cortex Analyst | *Which severity level has the most open events?* |
| Cortex Analyst | *What is operational risk exposure in EMEA?* |
| Cortex Search | *What regulatory documents do we have about Basel III?* |
| Cortex Search | *Find documents related to stress testing* |
| Cortex Search | *What does our AML filing template cover?* |
| Web Search | *What are the latest Basel IV capital requirements?* |
| Web Search | *What is the current Fed Funds rate?* |
| Combined | *Compare our CRITICAL exposure to industry benchmarks* |""", name="10.4 Try It")

# =============================================================================
# STEP 11 — CLEANUP
# =============================================================================
md("""---
## 11 · Cleanup (Optional)
Drop the lab schemas, warehouse, and custom roles. The **NOTEBOOKS** schema is preserved so this notebook remains available.""", name="11 · Cleanup")

sql("""USE ROLE accountadmin;

DROP AGENT IF EXISTS risk_hol.analytics.risk_intelligence_agent;
DROP CORTEX SEARCH SERVICE IF EXISTS risk_hol.unstructured.risk_docs_search;
DROP SEMANTIC VIEW IF EXISTS risk_hol.analytics.risk_exposure_sv;
DROP RESOURCE MONITOR IF EXISTS risk_wh_monitor;
DROP SCHEMA IF EXISTS risk_hol.raw_data;
DROP SCHEMA IF EXISTS risk_hol.analytics;
DROP SCHEMA IF EXISTS risk_hol.governance;
DROP SCHEMA IF EXISTS risk_hol.unstructured;
DROP WAREHOUSE IF EXISTS risk_wh;
DROP ROLE      IF EXISTS risk_admin;
DROP ROLE      IF EXISTS risk_analyst;
DROP ROLE      IF EXISTS risk_auditor;

SELECT 'Cleanup complete — notebook preserved' AS status;""", name="11 Drop Lab Objects")

# =============================================================================
# WRITE NOTEBOOK
# =============================================================================
notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "SQL", "language": "sql", "name": "sql"},
        "language_info": {"name": "sql"}
    },
    "nbformat": 4,
    "nbformat_minor": 5
}

with open("/Users/nbaxter/Downloads/financial-risk-hol/scripts/risk_hol_workbook.ipynb", "w") as f:
    json.dump(notebook, f, indent=1)

md_count = sum(1 for c in cells if c["cell_type"] == "markdown")
code_count = sum(1 for c in cells if c["cell_type"] == "code")
print(f"Notebook written: {len(cells)} cells ({md_count} markdown, {code_count} SQL)")
