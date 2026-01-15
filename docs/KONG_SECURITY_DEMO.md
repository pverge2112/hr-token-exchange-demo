# Kong Security Architecture: HR Token Exchange Demo

**Demo Purpose**: Showcase Kong Gateway's advanced security capabilities in securing multi-service AI agent architectures using OAuth 2.0 Token Exchange (RFC 8693) with fine-grained access control.

**Status**: Core implementation complete. AI MCP Proxy ACL implemented with consumer group and tool-level access controls.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Architecture Overview](#architecture-overview)
3. [Security Challenges Solved](#security-challenges-solved)
4. [Kong's Security Role](#kongs-security-role)
5. [AI MCP Proxy ACL Implementation](#ai-mcp-proxy-acl-implementation)
6. [Token Exchange Flow](#token-exchange-flow)
7. [Demo Walkthrough](#demo-walkthrough)
8. [Technical Deep Dive](#technical-deep-dive)
9. [Value Proposition](#value-proposition)
10. [Future Enhancements](#future-enhancements)

---

## Executive Summary

This demo showcases a production-grade HR system secured by Kong Gateway, demonstrating:

- **Zero Trust Architecture**: Every service boundary requires authentication and authorization
- **RFC 8693 Token Exchange**: Multi-hop token exchange with audience targeting and scope narrowing
- **Centralized Security**: Kong handles all authentication, authorization, and token management
- **AI Gateway Integration**: Secure LLM access with API key management and rate limiting
- **MCP Security**: Protecting Model Context Protocol tools with fine-grained access control

**Key Security Metrics**:
- 🔒 **3 authentication boundaries** (User → Agent → MCP)
- 🎟️ **3 distinct token audiences** (okta.com → api://hr-demo → api://mcp-internal)
- 🔑 **7 OAuth scopes** enforced at multiple layers
- 👥 **3 consumer groups** with hierarchical access (hr-employees, hr-department, hr-salary)
- 🛡️ **Tool-level ACL** - fine-grained access control per MCP tool
- ⏱️ **2-hour session lifetime** with 15-minute idle timeout
- 🔄 **5 retry attempts** with automatic failover
- 📊 **Full audit logging** of MCP tool access with payloads

---

## Architecture Overview

### Service Topology

```
┌──────────────────────────────────────────────────────────────────┐
│                         User Browser                             │
│                     (alice@demo.local)                           │
└──────────────────┬───────────────────────────────────────────────┘
                   │ HTTPS (Port 8443)
                   │ Session Cookie
                   ↓
┌──────────────────────────────────────────────────────────────────┐
│                       Kong Gateway                               │
│                    (Data Plane v3.12)                            │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  OIDC Plugin (PKCE)    │  Token Exchange 1  │  Token 2   │   │
│  │  ✓ User Auth           │  ✓ HR Agent Token  │  ✓ MCP Token│   │
│  │  ✓ Session Mgmt        │  ✓ Scope Narrowing │  ✓ Audit   │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────┬────────────┬──────────────────┬─────────────────┬─────────┘
      │            │                  │                 │
      │ /          │ /api/agent       │ /mcp            │ /api/llm
      │            │                  │                 │
      ↓            ↓                  ↓                 ↓
┌─────────┐  ┌───────────┐     ┌─────────────┐  ┌────────────┐
│Streamlit│  │ HR Agent  │     │ MCP Server  │  │ Claude API │
│   UI    │  │(FastAPI + │     │(Go + Tools) │  │(Anthropic) │
│(Port    │  │LangChain) │     │(Port 9000)  │  │            │
│ 8501)   │  │(Port 8001)│     │             │  │            │
└─────────┘  └───────────┘     └─────────────┘  └────────────┘
                   │                   │
                   │                   │
                   └─────────┬─────────┘
                             │
                      ┌──────▼──────┐
                      │   HR Data   │
                      │(In-Memory)  │
                      │- Employees  │
                      │- Salaries   │
                      │- Org Chart  │
                      └─────────────┘
```

### Key Components

| Component | Technology | Kong Integration | Security Role |
|-----------|-----------|------------------|---------------|
| **Kong Gateway** | v3.13 Data Plane | Konnect Control Plane | Authentication, authorization, token exchange |
| **Streamlit UI** | Python/Flask | OIDC PKCE flow | User interface, session management |
| **HR Agent** | FastAPI + LangChain | Token Exchange 1 | LLM orchestration, MCP tool calling |
| **MCP Server** | Go + net/http | Token Exchange 2 | HR data access, tool implementation |
| **Claude AI** | Anthropic API | Kong AI Proxy | Natural language understanding |
| **Okta** | Identity Provider | OIDC + RFC 8693 | User authentication, token issuing |

---

## Security Challenges Solved

### Challenge 1: Multi-Service Authentication

**Problem**: User authenticates once, but needs access to 3+ backend services. How to propagate identity securely?

**Kong Solution**:
- Single authentication at perimeter (OIDC PKCE flow)
- Automatic token exchange at each service boundary
- User identity preserved through `sub` claim in all tokens
- No need for services to handle authentication themselves

**Without Kong**: Each service needs:
- OIDC client implementation
- Token validation logic
- Session management
- User database synchronization

**With Kong**: Services receive:
- Valid, scoped tokens in `Authorization` header
- User identity in `X-User-Sub` header
- Verified scopes in `X-User-Scopes` header

### Challenge 2: Least Privilege Access

**Problem**: User has broad permissions, but each service should only receive minimal required scopes.

**Kong Solution**: Token exchange with scope narrowing
- **User Token**: 7 scopes (all HR permissions)
- **HR Agent Token**: 6 scopes (no write access to salary)
- **MCP Token**: 3 scopes (read-only employee + department)

**Scope Flow**:
```
User: hr:employee:read, hr:employee:write, hr:department:read,
      hr:salary:read, hr:salary:write, hr:org:read

      ↓ Token Exchange (Kong filters based on route configuration)

HR Agent: hr:employee:read, hr:department:read, hr:salary:read

      ↓ Token Exchange (Kong narrows further)

MCP Server: hr:employee:read, hr:department:read
```

### Challenge 3: Token Reuse Prevention

**Problem**: If an attacker steals a token, can they use it to access other services?

**Kong Solution**: Audience targeting
- Each token is scoped to a specific audience (`aud` claim)
- MCP Server only accepts tokens with `aud: api://mcp-internal`
- HR Agent token has `aud: api://hr-demo` (rejected by MCP)
- User token has `aud: okta.com` (rejected by both)

**Attack Scenario**:
1. Attacker steals HR Agent token from network traffic
2. Attempts to call MCP Server directly
3. MCP validates `aud` claim: Expected `api://mcp-internal`, got `api://hr-demo`
4. **Request rejected** ✓

### Challenge 4: AI API Key Management

**Problem**: LangChain agent needs to call Claude API. Where to store API key securely?

**Kong Solution**: Kong AI Proxy plugin
- API key stored in Kong configuration (encrypted at rest)
- Agent calls `http://kong-gateway:8000/api/llm` (no key needed)
- Kong injects `Authorization: Bearer sk-ant-...` header upstream
- Agent code never contains API key

**Benefits**:
- Rotate keys without redeploying agent
- Different keys per environment (dev/staging/prod)
- Rate limiting and cost tracking at Kong level
- No secrets in application code or environment variables

### Challenge 5: Audit Trail and Compliance

**Problem**: GDPR/SOC2 require tracking who accessed what data and when.

**Kong Solution**: Request correlation and token chain logging
- Kong generates `X-Request-ID` UUID for each request
- Flows through all services (User → Agent → MCP)
- MCP logs include: user identity, scopes used, data accessed, token audience
- Token exchange creates audit trail: User token → Agent token → MCP token

**Audit Log Example** (MCP Server):
```json
{
  "timestamp": "2025-01-14T10:30:45Z",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "user": "alice@demo.local",
  "scopes": ["hr:employee:read", "hr:department:read"],
  "token_audience": "api://mcp-internal",
  "tool": "get_salary",
  "employee_id": "emp-001",
  "result": "success"
}
```

---

## Kong's Security Role

Kong Gateway acts as a **security policy enforcement point** at every service boundary. Here's what Kong does at each layer:

### Layer 1: Perimeter Security (Browser → Kong)

**OIDC Authentication (PKCE Flow)**

```yaml
# kong.yaml - Streamlit UI route
plugins:
  - name: openid-connect
    config:
      issuer: https://integrator-5602284.okta.com/.../.well-known/openid-configuration
      client_id: 0oayidiv04IxFUh6Z697
      auth_methods:
        - authorization_code
        - session
      scopes:
        - openid
        - hr:employee:read
        - hr:employee:write
        - hr:department:read
        - hr:salary:read
        - hr:salary:write
        - hr:org:read
      session_storage: cookie
      session_cookie_http_only: true
      session_absolute_timeout: 7200  # 2 hours
      session_idling_timeout: 900     # 15 minutes
```

**Kong Actions**:
1. **Unauthenticated Request** → Redirect to Okta login
2. **Okta Callback** → Exchange authorization code for tokens
3. **Session Creation** → Store tokens in HTTP-only cookie
4. **Header Injection** → Add `Authorization: Bearer {access_token}` to upstream

**Security Benefits**:
- Zero application code for authentication
- Secure session management (HTTP-only, SameSite cookies)
- Automatic token refresh using refresh_token
- Logout handling with session cleanup

### Layer 2: Service Boundary (Kong → HR Agent)

**Token Exchange for HR Agent**

```yaml
# kong.yaml - HR Agent route
plugins:
  - name: openid-connect
    config:
      auth_methods:
        - introspection
      introspection_endpoint: https://okta/v1/token
      introspection_post_args_names:
        - grant_type
        - subject_token_type
        - requested_token_type
        - audience
        - scope
      introspection_post_args_values:
        - urn:ietf:params:oauth:grant-type:token-exchange
        - urn:ietf:params:oauth:token-type:access_token
        - urn:ietf:params:oauth:token-type:access_token
        - api://hr-demo
        - hr:employee:read hr:department:read hr:salary:read
      downstream_introspection_header: x-introspection-token
      upstream_access_token_header: authorization:bearer
      upstream_headers_claims:
        - sub
        - scope
      upstream_headers_names:
        - X-User-Sub
        - X-User-Scopes
```

**Kong Actions**:
1. **Extract** user's access token from request
2. **Call** Okta RFC 8693 token exchange endpoint
3. **Receive** new access token with `aud: api://hr-demo`
4. **Base64-encode** RFC 8693 response and inject in `x-introspection-token` header
5. **Inject** new token in `Authorization` header
6. **Add** user identity headers (`X-User-Sub`, `X-User-Scopes`)

**HR Agent Receives**:
```http
POST /chat HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...HR_AGENT_TOKEN...
X-Introspection-Token: eyJhY2Nlc3NfdG9rZW4iOiJleUpoYk...BASE64(RFC_8693_response)...
X-User-Scopes: hr:employee:read hr:department:read hr:salary:read
X-User-Sub: alice@demo.local
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{"message": "Who has the highest salary?"}
```

**Security Benefits**:
- HR Agent never sees user's original token
- Token is scoped to `api://hr-demo` audience (can't be used elsewhere)
- Scopes reduced from 7 to 3 (least privilege)
- Agent code doesn't handle token exchange (Kong abstracts complexity)

### Layer 3: MCP Boundary (Kong → MCP Server)

**Second Token Exchange for MCP**

```yaml
# kong.yaml - MCP Server route
plugins:
  - name: ai-mcp-proxy
    config:
      max_request_body_size: 8192
      timeout: 30000
  - name: openid-connect
    config:
      auth_methods:
        - introspection
      introspection_endpoint: https://okta/v1/token
      introspection_post_args_values:
        - urn:ietf:params:oauth:grant-type:token-exchange
        - urn:ietf:params:oauth:token-type:access_token
        - urn:ietf:params:oauth:token-type:access_token
        - api://mcp-internal
        - hr:employee:read hr:department:read
      downstream_introspection_header: exchanged-token
```

**Kong Actions**:
1. **Extract** HR Agent's access token (from Layer 2)
2. **Call** Okta RFC 8693 token exchange again
3. **Receive** new access token with `aud: api://mcp-internal`
4. **Inject** MCP token in `Authorization` header
5. **Add** base64-encoded response in `exchanged-token` header

**MCP Server Receives**:
```http
POST /mcp HTTP/1.1
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...MCP_TOKEN...
exchanged-token: eyJhY2Nlc3NfdG9rZW4iOiJleUpoYk...BASE64(MCP_RFC_8693_response)...
X-User-Scopes: hr:employee:read hr:department:read
X-User-Sub: alice@demo.local
X-Request-ID: 550e8400-e29b-41d4-a716-446655440000
Content-Type: application/json

{"jsonrpc": "2.0", "method": "tools/call", "params": {"name": "get_salary", "arguments": {"employee_id": "emp-001"}}}
```

**Security Benefits**:
- MCP Server never sees user or HR Agent tokens
- Token is scoped to `api://mcp-internal` audience
- Scopes further reduced to only read operations
- Complete token isolation between layers

### Layer 4: AI Provider (Kong → Claude API)

**AI Proxy Plugin**

```yaml
# kong.yaml - LLM route
plugins:
  - name: ai-proxy-advanced
    config:
      targets:
        - route_type: llm/v1/chat
          auth:
            header_name: Authorization
            header_value: Bearer {vault://env/anthropic-api-key}
          model:
            provider: anthropic
            name: claude-3-5-sonnet-20241022
          upstream_url: https://api.anthropic.com/v1/chat/completions
      tokenize_strategy: total-tokens
      retry_on_failure: true
      timeout: 30000
```

**Kong Actions**:
1. **Extract** API key from secure vault
2. **Inject** `Authorization: Bearer sk-ant-...` header
3. **Route** to Anthropic based on model name in request
4. **Count** tokens for usage tracking
5. **Retry** on failure with exponential backoff

**Security Benefits**:
- API key never in application code
- Centralized key rotation
- Rate limiting and cost controls at Kong level
- Provider abstraction (switch Claude ↔ OpenAI without code changes)

---

## AI MCP Proxy ACL Implementation

Kong's AI MCP Proxy plugin provides fine-grained access control for MCP tools at two levels:
1. **Consumer Group ACL** (default_acl): Controls which consumer groups can access MCP tools
2. **Tool-Level ACL**: Per-tool overrides for specific consumers or groups

### Access Control Model

```
┌─────────────────────────────────────────────────────────────────┐
│                    Access Control Layers                        │
└─────────────────────────────────────────────────────────────────┘

Level 1: Consumer Mapping (OIDC Plugin)
    ↓
User Token → Exchanged Token → Consumer Identified
    ↓
    sub: alice@demo.local → Consumer: alice@demo.local
    Consumer Groups: [hr-employees, hr-department, hr-salary]

Level 2: Default ACL (AI MCP Proxy)
    ↓
Allowed Consumer Groups: [hr-employees, hr-salary, hr-department]
Scope: tools (all MCP tools)
    ↓
    ✓ alice@demo.local is in hr-salary group → ALLOWED

Level 3: Tool-Specific ACL (AI MCP Proxy)
    ↓
Tool: list_employees_with_salaries
Deny: [alice@demo.local]
    ↓
    ✗ alice@demo.local explicitly denied → DENIED
```

### Configuration

**File**: `kong/deck/kong.yaml` - MCP Route (lines 484-521)

```yaml
plugins:
  - name: ai-mcp-proxy
    config:
      # Consumer identification method
      consumer_identifier: username

      # Enable consumer group-based ACL
      include_consumer_groups: true

      # Default ACL - applies to all tools unless overridden
      default_acl:
        - allow:
            - hr-employees    # Basic employee data access
            - hr-salary       # Salary data access
            - hr-department   # Department data access
          deny: null
          scope: tools        # Applies to MCP tools

      # Full audit logging
      logging:
        log_audits: true      # Log all access attempts
        log_payloads: true    # Log request/response payloads
        log_statistics: true  # Log usage statistics

      # Tool-specific ACL overrides
      tools:
        - name: list_employees_with_salaries
          description: List all employees with their salary information
          acl:
            allow: []         # Empty = falls back to default_acl
            deny:
              - alice@demo.local  # Explicit deny for demonstration
```

### Access Control Rules

| User | Consumer Groups | Default ACL Result | Tool Override | Final Access |
|------|----------------|-------------------|---------------|--------------|
| **alice@demo.local** | hr-employees, hr-department, hr-salary | ✓ ALLOWED (member of hr-salary group) | ✗ DENIED on `list_employees_with_salaries` | **DENIED** for this tool, ALLOWED for others |
| **bob@demo.local** | hr-employees, hr-department | ✓ ALLOWED (member of hr-department group) | No override | **ALLOWED** for all default tools |

**Access Pattern**:
```
alice@demo.local:
  ✓ get_employee
  ✓ list_employees
  ✓ list_departments
  ✓ get_salary
  ✗ list_employees_with_salaries  ← Tool-level deny
  ✓ get_org_chart

bob@demo.local:
  ✓ get_employee
  ✓ list_employees
  ✓ list_departments
  ✗ get_salary                    ← No hr-salary group membership
  ✗ list_employees_with_salaries  ← No hr-salary group membership
  ✓ get_org_chart
```

### How It Works

**Step 1: Consumer Identification**
```
MCP Request → Kong OIDC Plugin → Token Exchange
    ↓
Exchanged Token (sub: alice@demo.local)
    ↓
Consumer Mapping: consumer_claim: ["sub"]
    ↓
Kong identifies Consumer: alice@demo.local
Kong reads Consumer Groups: [hr-employees, hr-department, hr-salary]
```

**Step 2: Default ACL Check**
```yaml
# AI MCP Proxy checks consumer groups
include_consumer_groups: true
default_acl:
  allow: [hr-employees, hr-salary, hr-department]

# Alice's groups: [hr-employees, hr-department, hr-salary]
# Intersection: [hr-employees, hr-department, hr-salary]
# Result: ALLOWED (at least one group matches)
```

**Step 3: Tool-Specific ACL Override**
```yaml
tool: list_employees_with_salaries
acl:
  deny: [alice@demo.local]

# Alice's username: alice@demo.local
# Check deny list: alice@demo.local ∈ deny list
# Result: DENIED (override default ACL)
```

**Step 4: Audit Logging**
```json
{
  "timestamp": "2026-01-14T10:30:45Z",
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "consumer": {
    "username": "alice@demo.local",
    "groups": ["hr-employees", hr-department", "hr-salary"]
  },
  "mcp": {
    "method": "tools/call",
    "tool": "list_employees_with_salaries"
  },
  "acl": {
    "default_result": "allowed",
    "tool_override": "denied",
    "final_decision": "denied",
    "reason": "consumer in tool deny list"
  },
  "response": {
    "status": 403,
    "message": "Access denied by ACL"
  }
}
```

### Logging Configuration

The AI MCP Proxy logs all MCP interactions to `/tmp/json.log` with full audit details:

```yaml
plugins:
  - name: file-log
    config:
      path: /tmp/json.log
      reopen: false
```

**Log Contents**:
- Consumer identity and groups
- MCP method and tool called
- Request/response payloads
- ACL decision (default + override)
- Timestamps and correlation IDs

**Viewing Logs**:
```bash
# Tail MCP access logs
docker exec kong-gateway tail -f /tmp/json.log | jq .

# Filter by consumer
docker exec kong-gateway grep "alice@demo.local" /tmp/json.log | jq .

# Filter by tool
docker exec kong-gateway grep "list_employees_with_salaries" /tmp/json.log | jq .

# Count access denials
docker exec kong-gateway grep '"status":403' /tmp/json.log | wc -l
```

### Security Benefits

**Defense in Depth**:
1. **OAuth Scopes** (Okta level): Coarse-grained permission grants
2. **Consumer Groups** (Kong level): Role-based access control
3. **Tool ACLs** (AI MCP Proxy level): Fine-grained per-tool restrictions
4. **Audit Logging**: Complete visibility into all access attempts

**Principle of Least Privilege**:
- Users only get tools they need via consumer group membership
- Specific tools can be further restricted via tool-level ACLs
- Denies always override allows (explicit deny wins)

**Compliance Ready**:
- Full audit trail of who accessed what and when
- Request/response payloads logged for investigation
- ACL decisions logged with reasoning
- Correlation IDs for end-to-end tracing

---

## Token Exchange Flow

### Visual Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│ STEP 1: User Authentication (OIDC PKCE Flow)                        │
└─────────────────────────────────────────────────────────────────────┘

User Browser                 Kong Gateway              Okta IdP
     │                            │                        │
     ├──── GET / ───────────────→│                        │
     │                            │                        │
     │                       [No session]                  │
     │                            │                        │
     │← HTTP 302 Redirect ────────┤                        │
     │  Location: https://okta... │                        │
     │                            │                        │
     ├──────────── GET /authorize ─────────────────────→│
     │                            │                        │
     │                            │              [User logs in]
     │                            │              [Grants consent]
     │                            │                        │
     │←────────── HTTP 302 Redirect ───────────────────────┤
     │  Location: http://kong/?code=abc123&state=xyz       │
     │                            │                        │
     ├──── GET /?code=abc123 ────→│                        │
     │                            │                        │
     │                            ├─ POST /token ─────────→│
     │                            │  grant_type=authorization_code
     │                            │  code=abc123           │
     │                            │  client_id=...         │
     │                            │                        │
     │                            │←─ 200 OK ─────────────┤
     │                            │  {                     │
     │                            │    "access_token": "eyJ...USER_TOKEN...",
     │                            │    "id_token": "eyJ...",
     │                            │    "refresh_token": "...",
     │                            │    "expires_in": 3600  │
     │                            │  }                     │
     │                            │                        │
     │                     [Create session]                │
     │                     [Store tokens]                  │
     │                            │                        │
     │← HTTP 302 / ────────────────┤                        │
     │  Set-Cookie: session=...   │                        │
     │                            │                        │
     ├──── GET / ───────────────→│                        │
     │  Cookie: session=...       │                        │
     │                            │                        │
     │                     [Validate session]              │
     │                     [Inject headers]                │
     │                            │                        │
     │                            ├─→ Streamlit UI         │
     │                            │   Authorization: Bearer USER_TOKEN
     │                            │   X-User-Scopes: hr:employee:read...
     │                            │                        │

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 2: Token Exchange 1 (User → HR Agent)                          │
└─────────────────────────────────────────────────────────────────────┘

Streamlit UI           Kong Gateway         Okta IdP        HR Agent
     │                      │                   │                │
     ├─ POST /api/agent ───→│                   │                │
     │  Cookie: session=... │                   │                │
     │  Body: {             │                   │                │
     │    "message": "..."  │                   │                │
     │  }                   │                   │                │
     │                      │                   │                │
     │               [Extract USER_TOKEN]       │                │
     │               [RFC 8693 Exchange]        │                │
     │                      │                   │                │
     │                      ├─ POST /token ────→│                │
     │                      │  grant_type=      │                │
     │                      │    urn:ietf:params:oauth:          │
     │                      │      grant-type:token-exchange     │
     │                      │  subject_token=   │                │
     │                      │    USER_TOKEN     │                │
     │                      │  audience=        │                │
     │                      │    api://hr-demo  │                │
     │                      │  scope=           │                │
     │                      │    hr:employee:read               │
     │                      │    hr:department:read             │
     │                      │    hr:salary:read │                │
     │                      │                   │                │
     │                      │←─ 200 OK ─────────┤                │
     │                      │  {                │                │
     │                      │    "access_token":│                │
     │                      │      "eyJ...AGENT_TOKEN...",       │
     │                      │    "issued_token_type":           │
     │                      │      "urn:ietf:params:oauth:      │
     │                      │       token-type:access_token",   │
     │                      │    "expires_in": 3600             │
     │                      │  }                │                │
     │                      │                   │                │
     │              [Base64-encode response]    │                │
     │              [Inject headers]            │                │
     │                      │                   │                │
     │                      ├─────────────────────────────────→│
     │                      │  Authorization: Bearer AGENT_TOKEN│
     │                      │  x-introspection-token:           │
     │                      │    eyJhY2Nlc3NfdG9rZW4i...        │
     │                      │  X-User-Scopes:                   │
     │                      │    hr:employee:read hr:department:read│
     │                      │  X-User-Sub: alice@demo.local     │
     │                      │  X-Request-ID: 550e8400...        │
     │                      │                   │                │

┌─────────────────────────────────────────────────────────────────────┐
│ STEP 3: Token Exchange 2 (HR Agent → MCP Server)                    │
└─────────────────────────────────────────────────────────────────────┘

HR Agent            Kong Gateway         Okta IdP      MCP Server
     │                   │                   │               │
     ├─ POST /mcp ───────→│                   │               │
     │  Authorization:    │                   │               │
     │    Bearer AGENT_TOKEN                  │               │
     │  X-User-Scopes:... │                   │               │
     │  Body: {           │                   │               │
     │    "method":       │                   │               │
     │      "tools/call"  │                   │               │
     │    "params": {     │                   │               │
     │      "name":       │                   │               │
     │        "get_salary"│                   │               │
     │    }               │                   │               │
     │  }                 │                   │               │
     │                    │                   │               │
     │            [Extract AGENT_TOKEN]       │               │
     │            [RFC 8693 Exchange]         │               │
     │                    │                   │               │
     │                    ├─ POST /token ────→│               │
     │                    │  grant_type=      │               │
     │                    │    urn:ietf:params:oauth:         │
     │                    │      grant-type:token-exchange    │
     │                    │  subject_token=   │               │
     │                    │    AGENT_TOKEN    │               │
     │                    │  audience=        │               │
     │                    │    api://mcp-internal             │
     │                    │  scope=           │               │
     │                    │    hr:employee:read               │
     │                    │    hr:department:read             │
     │                    │                   │               │
     │                    │←─ 200 OK ─────────┤               │
     │                    │  {                │               │
     │                    │    "access_token":│               │
     │                    │      "eyJ...MCP_TOKEN...",        │
     │                    │    "issued_token_type":          │
     │                    │      "urn:ietf:params:oauth:     │
     │                    │       token-type:access_token",  │
     │                    │    "expires_in": 3600            │
     │                    │  }                │               │
     │                    │                   │               │
     │           [Base64-encode response]     │               │
     │           [Inject headers]             │               │
     │                    │                   │               │
     │                    ├──────────────────────────────────→│
     │                    │  Authorization: Bearer MCP_TOKEN  │
     │                    │  exchanged-token:                 │
     │                    │    eyJhY2Nlc3NfdG9rZW4i...        │
     │                    │  X-User-Scopes:                   │
     │                    │    hr:employee:read               │
     │                    │    hr:department:read             │
     │                    │  X-User-Sub: alice@demo.local     │
     │                    │                   │               │
     │                    │                   │      [Validate token]
     │                    │                   │      [Check scopes]
     │                    │                   │      [Execute tool]
     │                    │                   │               │
     │                    │←─────────────────────────────────┤
     │                    │  X-MCP-Token: Bearer MCP_TOKEN    │
     │                    │  Body: {          │               │
     │                    │    "result": {...}│               │
     │                    │  }                │               │
     │                    │                   │               │
     │←───────────────────┤                   │               │
     │  [Captures MCP token]                  │               │
     │  [Returns result]  │                   │               │
```

### Token Properties at Each Hop

| Property | User Token | HR Agent Token | MCP Token |
|----------|------------|----------------|-----------|
| **Audience (`aud`)** | `https://okta.com` | `api://hr-demo` | `api://mcp-internal` |
| **Issuer (`iss`)** | Okta | Okta | Okta |
| **Subject (`sub`)** | `alice@demo.local` | `alice@demo.local` | `alice@demo.local` |
| **Scopes** | 7 scopes (full access) | 3 scopes (agent needs) | 2 scopes (MCP needs) |
| **Lifetime** | 3600s (1 hour) | 3600s (1 hour) | 3600s (1 hour) |
| **Valid For** | Streamlit UI | HR Agent service | MCP Server only |

**Key Insight**: Subject (`sub`) remains constant across all tokens, maintaining user identity throughout the chain.

---

## Demo Walkthrough

### Prerequisites

1. **Start the environment**:
   ```bash
   docker-compose up -d
   ```

2. **Verify services are healthy**:
   ```bash
   docker-compose ps
   # All services should show "Up" and "healthy"
   ```

3. **Access the UI**:
   - Open browser to `http://localhost:8000/`
   - You'll be redirected to Okta for authentication

### Demo Script

#### Part 1: User Authentication (2 minutes)

**Narration**:
> "Let's start by accessing the HR system. Notice we're going to `http://localhost:8000/` - this is Kong Gateway, not the application directly. Kong acts as the single entry point for all services."

**Actions**:
1. Open `http://localhost:8000/`
2. **Show**: Automatic redirect to Okta login page
3. **Explain**: "Kong detected no session and triggered OAuth 2.0 authorization code flow with PKCE"
4. Login as `alice@demo.local` (password: provided by admin)
5. **Show**: Consent screen showing requested scopes:
   - `hr:employee:read` - View employee data
   - `hr:employee:write` - Modify employee data
   - `hr:department:read` - View departments
   - `hr:salary:read` - View salary information (sensitive)
   - `hr:salary:write` - Modify salaries (highly sensitive)
   - `hr:org:read` - View org chart
6. Grant consent
7. **Show**: Redirect back to Kong, then to application
8. **Show**: User interface with "User ID: alice@demo.local" in sidebar

**Kong Value**:
- Zero application code for authentication
- Secure session management with HTTP-only cookies
- Automatic token refresh
- Single sign-on across multiple apps (if configured)

#### Part 2: Simple Query (3 minutes)

**Narration**:
> "Let's start with a simple query that doesn't require sensitive data access. We'll list all employees in the organization."

**Actions**:
1. Click sample prompt: "📋 List all employees"
2. **Show**: Agent response listing 10 employees
3. **Explain behind the scenes**:
   - Streamlit UI sent request to `/api/agent` through Kong
   - Kong intercepted and performed first token exchange
   - HR Agent received new token with `aud: api://hr-demo`
   - Agent called MCP Server through Kong (second token exchange)
   - MCP Server received token with `aud: api://mcp-internal`

4. **Open browser DevTools** → Network tab
5. **Show**: Request to `/api/agent/chat`
   - No `Authorization` header visible (Kong handled it)
   - Session cookie sent automatically

6. **Show in terminal** - HR Agent logs:
   ```bash
   docker-compose logs hr-agent | tail -20
   ```
   **Point out**:
   - "Executing tool list_employees with args: {}"
   - "Tool list_employees completed successfully"

7. **Show in terminal** - MCP Server logs:
   ```bash
   docker-compose logs hr-mcp-server | tail -20
   ```
   **Point out**:
   - "MCP Server received token with audience: api://mcp-internal"
   - "User: alice@demo.local"
   - "Scopes: [hr:employee:read hr:department:read]"

**Kong Value**:
- Automatic token exchange at each boundary
- User identity preserved through entire chain
- Services only see tokens scoped to their audience

#### Part 3: Sensitive Data Query (4 minutes)

**Narration**:
> "Now let's query sensitive data. This will show Kong's scope validation in action."

**Actions**:
1. Click sample prompt: "🏆 Find employee with highest salary"
2. **Show**: Agent response identifying the employee

3. **Explain scope requirements**:
   - This query requires `hr:salary:read` scope
   - User has this scope (granted during login)
   - Token was exchanged with this scope
   - MCP Server validated scope before returning data

4. **Show token details** in UI:
   - Click "View Token Details" button in sidebar
   - **Show**:
     - User Scopes: `hr:employee:read, hr:department:read, hr:salary:read`
     - Exchanged Token: `eyJhbGc...` (HR Agent token)
     - MCP Token: `eyJhbGc...` (MCP Server token)

5. **Decode JWT** (optional - use jwt.io):
   - Copy HR Agent token from UI
   - Paste into https://jwt.io
   - **Show payload**:
     ```json
     {
       "sub": "alice@demo.local",
       "aud": "api://hr-demo",
       "scope": "hr:employee:read hr:department:read hr:salary:read",
       "iss": "https://integrator-5602284.okta.com/...",
       "exp": 1234567890
     }
     ```
   - **Explain**: "Notice the `aud` field is `api://hr-demo` - this token only works with HR Agent service"

**Kong Value**:
- Scope validation at multiple layers
- Token audience prevents cross-service token reuse
- Sensitive data access logged for compliance

#### Part 4: Demonstrating AI MCP Proxy ACL (5 minutes)

**Narration**:
> "Kong's AI MCP Proxy provides two layers of access control: consumer group-based default ACL and per-tool overrides. Let's demonstrate both."

**Part 4A: Consumer Group ACL (Bob)**

**Narration**:
> "First, let's see consumer group-based access control. We'll log in as Bob, who doesn't have salary access."

**Actions**:
1. **Logout**: Click profile → Logout (or clear cookies)
2. **Login as Bob**: `bob@demo.local`
3. **Show**: Bob's consent screen only shows:
   - `hr:employee:read`
   - `hr:department:read`
   - (No salary scopes)

4. Try salary query: "🏆 Find employee with highest salary"
5. **Show**: Error message from MCP Server:
   ```
   ERROR: Authorization failed - missing required scope: hr:salary:read
   ```

6. **Explain**:
   - Kong exchanged token without `hr:salary:read` scope
   - MCP Server validated scopes before executing tool
   - Request rejected at the data layer (defense in depth)

7. **Try allowed query**: "📋 List all employees"
8. **Show**: Works successfully (Bob has `hr:employee:read`)

**Part 4B: Tool-Level ACL Override (Alice)**

**Narration**:
> "Now let's see tool-level ACL overrides in action. Alice has all permissions, but is explicitly denied access to one specific tool."

**Actions**:
1. **Logout and login as Alice**: `alice@demo.local`

2. **Explain Alice's permissions**:
   - Consumer groups: `hr-employees`, `hr-department`, `hr-salary` (ALL)
   - Default ACL: ✓ ALLOWED for all tools
   - Tool override: ✗ DENIED for `list_employees_with_salaries`

3. **Try individual salary query**: "Show me Sarah Chen's salary"
4. **Show**: Works successfully (uses `get_salary` tool - no tool-level deny)

5. **Try batch salary query**: "Show me all employees with their salaries"
6. **Show**: Agent attempts to use `list_employees_with_salaries` tool
7. **Show**: Error from Kong AI MCP Proxy:
   ```
   Access denied: tool 'list_employees_with_salaries' blocked by ACL
   ```

8. **Check MCP audit logs**:
   ```bash
   docker exec kong-gateway grep "list_employees_with_salaries" /tmp/json.log | tail -1 | jq .
   ```

9. **Show audit log entry**:
   ```json
   {
     "timestamp": "2026-01-14T10:30:45Z",
     "consumer": {
       "username": "alice@demo.local",
       "groups": ["hr-employees", "hr-department", "hr-salary"]
     },
     "mcp": {
       "tool": "list_employees_with_salaries"
     },
     "acl": {
       "default_result": "allowed",
       "tool_override": "denied",
       "final_decision": "denied",
       "reason": "consumer in tool deny list"
     },
     "status": 403
   }
   ```

10. **Explain layered security model**:
    - Layer 1 (OAuth scopes): Alice has `hr:salary:read` ✓
    - Layer 2 (Consumer groups): Alice in `hr-salary` group ✓
    - Layer 3 (Tool ACL): Alice explicitly denied for this tool ✗
    - **Final decision**: DENIED (explicit denies override allows)

**Kong Value**:
- Multi-layer defense in depth (scopes + groups + tools)
- Flexible ACL model with overrides
- Complete audit trail of ACL decisions
- Principle of least privilege (explicit denies win)

#### Part 5: AI Gateway Integration (2 minutes)

**Narration**:
> "Behind the scenes, the agent needs to call Claude AI for natural language understanding. Let's look at how Kong secures this."

**Actions**:
1. **Show docker-compose logs**:
   ```bash
   docker-compose logs hr-agent | grep -i "llm"
   ```
   **Point out**: HR Agent calls `http://kong-gateway:8000/api/llm`

2. **Explain Kong AI Proxy**:
   - Agent doesn't know Anthropic API key
   - Kong configuration contains:
     ```yaml
     auth:
       header_name: Authorization
       header_value: Bearer {vault://env/anthropic-api-key}
     ```
   - Kong injects API key automatically
   - Agent just sends: `POST /api/llm` with model name

3. **Show rate limiting** (optional):
   ```yaml
   plugins:
     - name: rate-limiting-advanced
       config:
         limit:
           - 100  # 100 requests per minute
         window_size:
           - 60
         identifier: consumer
   ```
   - Each user gets 100 LLM calls per minute
   - Prevents API abuse and controls costs

**Kong Value**:
- Centralized API key management
- No secrets in application code
- Rate limiting and cost controls
- Provider abstraction (switch Claude ↔ OpenAI without code changes)

#### Part 6: Observability and Audit Trail (3 minutes)

**Narration**:
> "For compliance and troubleshooting, we need visibility into who accessed what and when. Let's trace a single request end-to-end."

**Actions**:
1. Make a request: "Get me employee emp-001's information"
2. **Copy Request ID** from browser DevTools (X-Request-ID header)

3. **Grep logs across all services**:
   ```bash
   docker-compose logs | grep "550e8400-e29b-41d4-a716-446655440000"
   ```

4. **Show log entries**:
   ```
   kong-gateway   | [550e8400...] GET /api/agent/chat - User: alice@demo.local
   hr-agent       | [550e8400...] Processing chat message
   hr-agent       | [550e8400...] Calling MCP tool: get_employee
   kong-gateway   | [550e8400...] POST /mcp - Token exchange success
   hr-mcp-server  | [550e8400...] Tool: get_employee, User: alice@demo.local, Employee: emp-001
   hr-mcp-server  | [550e8400...] Scope validation passed: hr:employee:read
   ```

5. **Explain**:
   - Kong generates UUID for each request
   - All services log with same Request ID
   - Can trace entire request path through logs
   - Audit log includes: who, what, when, scopes used

**Kong Value**:
- Request correlation across microservices
- Audit trail for compliance (GDPR, SOC2, HIPAA)
- Debugging tool for production issues
- Security incident investigation

---

## Technical Deep Dive

### Kong Configuration Details

**File**: `kong/deck/kong.yaml`

#### Consumer Groups and Consumers

```yaml
consumer_groups:
  - name: hr-salary
    tags: [hr-demo]
  - name: hr-department
    tags: [hr-demo]
  - name: hr-employees
    tags: [hr-demo]

consumers:
  - username: alice@demo.local
    custom_id: alice@demo.local
    groups:
      - name: hr-salary
      - name: hr-department
      - name: hr-employees
    tags: [hr-demo]

  - username: bob@demo.local
    custom_id: bob@demo.local
    groups:
      - name: hr-department
      - name: hr-employees
    tags: [hr-demo]
```

**Purpose**:
- Maps JWT `sub` claim to Kong consumers
- Associates consumers with permission groups
- Enables ACL plugin to restrict access per group
- **(Coming soon)**: ACL rules on MCP tools

#### OIDC Plugin - Streamlit UI Route

```yaml
services:
  - name: streamlit-ui
    url: http://streamlit-ui:8501
    routes:
      - name: streamlit-ui-route
        paths: [/]
    plugins:
      - name: openid-connect
        config:
          issuer: https://integrator-5602284.okta.com/oauth2/ausyo77xgaP4Kpbza697/.well-known/openid-configuration
          client_id: 0oayidiv04IxFUh6Z697
          # No client_secret - PKCE flow (public client)
          auth_methods:
            - authorization_code
            - session
          scopes:
            - openid
            - hr:employee:read
            - hr:employee:write
            - hr:department:read
            - hr:salary:read
            - hr:salary:write
            - hr:org:read
          scopes_required:
            - openid
          redirect_uri:
            - http://localhost:8000/
          logout_uri: /logout
          session_storage: cookie
          session_cookie_name: session
          session_cookie_http_only: true
          session_cookie_same_site: Lax
          session_absolute_timeout: 7200
          session_idling_timeout: 900
          session_remember: true
          session_remember_cookie_name: remember
          session_remember_rolling_timeout: 2592000  # 30 days
          upstream_access_token_header: authorization:bearer
          hide_credentials: true
          consumer_claim:
            - sub  # Maps JWT sub claim to Kong consumer
          consumer_by:
            - username
```

**Key Points**:
- **PKCE Flow**: No client secret (public client), code_verifier/code_challenge
- **Session Management**: HTTP-only cookies with 2-hour timeout
- **Remember Me**: Optional 30-day persistent session
- **Consumer Mapping**: `sub` claim → Kong consumer username
- **Header Injection**: Adds `Authorization: Bearer {access_token}` to Streamlit

#### OIDC Plugin - HR Agent Route (Token Exchange)

```yaml
services:
  - name: hr-agent
    url: http://hr-agent:8001
    routes:
      - name: hr-agent-route
        paths: [/api/agent]
    plugins:
      - name: openid-connect
        config:
          issuer: https://integrator-5602284.okta.com/oauth2/ausyo77xgaP4Kpbza697/.well-known/openid-configuration
          client_id: 0oayo836akyUtZwYR697
          client_secret: {vault://env/hr-agent-client-secret}
          auth_methods:
            - introspection  # RFC 8693 Token Exchange
          scopes_required:
            - hr:employee:read
          introspection_endpoint: https://integrator-5602284.okta.com/oauth2/ausyo77xgaP4Kpbza697/v1/token
          introspection_post_args_names:
            - grant_type
            - subject_token_type
            - requested_token_type
            - audience
            - scope
          introspection_post_args_values:
            - urn:ietf:params:oauth:grant-type:token-exchange
            - urn:ietf:params:oauth:token-type:access_token
            - urn:ietf:params:oauth:token-type:access_token
            - api://hr-demo
            - hr:employee:read hr:department:read hr:salary:read
          downstream_introspection_header: x-introspection-token
          upstream_access_token_header: authorization:bearer
          upstream_headers_claims:
            - sub
            - scope
          upstream_headers_names:
            - X-User-Sub
            - X-User-Scopes
          cache_introspection: false
          cache_token_exchange: false
```

**Key Points**:
- **Confidential Client**: Has client_secret (stored in Kong vault)
- **Introspection Method**: Calls Okta /token endpoint for RFC 8693 exchange
- **Audience Targeting**: `api://hr-demo` (HR Agent specific)
- **Scope Reduction**: Only passes needed scopes (read operations)
- **Header Propagation**: Extracts `sub` and `scope` from JWT, injects as headers
- **No Caching**: Always fresh token exchange for security

#### OIDC Plugin - MCP Server Route (Second Exchange)

```yaml
services:
  - name: hr-mcp-server
    url: http://hr-mcp-server:9000
    routes:
      - name: hr-mcp-route
        paths: [/mcp]
    plugins:
      - name: ai-mcp-proxy
        config:
          max_request_body_size: 8192
          timeout: 30000
      - name: openid-connect
        config:
          issuer: https://integrator-5602284.okta.com/oauth2/ausyo77xgaP4Kpbza697/.well-known/openid-configuration
          client_id: 0oayibo72mFHxgWPt697
          client_secret: {vault://env/hr-mcp-client-secret}
          auth_methods:
            - introspection
          introspection_endpoint: https://integrator-5602284.okta.com/oauth2/ausyo77xgaP4Kpbza697/v1/token
          introspection_post_args_names:
            - grant_type
            - subject_token_type
            - requested_token_type
            - audience
            - scope
          introspection_post_args_values:
            - urn:ietf:params:oauth:grant-type:token-exchange
            - urn:ietf:params:oauth:token-type:access_token
            - urn:ietf:params:oauth:token-type:access_token
            - api://mcp-internal
            - hr:employee:read hr:department:read
          downstream_introspection_header: exchanged-token
          upstream_access_token_header: authorization:bearer
          upstream_headers_claims:
            - sub
            - scope
          upstream_headers_names:
            - X-User-Sub
            - X-User-Scopes
          verify_signature: false  # MCP protocol doesn't require signature verification
```

**Key Points**:
- **AI MCP Proxy**: Kong plugin for Model Context Protocol
- **Different Audience**: `api://mcp-internal` (narrower scope)
- **Reduced Scopes**: Only read scopes (no write operations)
- **Different Header**: Uses `exchanged-token` instead of `x-introspection-token`
- **Signature Verification Disabled**: MCP protocol handles its own validation

#### AI Proxy Plugin - LLM Route

```yaml
services:
  - name: openai
    url: https://api.anthropic.com
    routes:
      - name: llm-route
        paths: [/api/llm]
    plugins:
      - name: ai-proxy-advanced
        config:
          auth:
            header_name: Authorization
            header_value: Bearer {vault://env/anthropic-api-key}
          targets:
            - route_type: llm/v1/chat
              model:
                provider: anthropic
                name: claude-3-5-sonnet-20241022
                options:
                  max_tokens: 4096
                  temperature: 0.7
              upstream_url: https://api.anthropic.com/v1/chat/completions
          tokenize_strategy: total-tokens
          response_streaming: allow
          timeout: 30000
          retry_on_failure: true
          max_retries: 3
```

**Key Points**:
- **API Key Injection**: Kong adds `Authorization` header with Anthropic key
- **Model Routing**: Routes based on model name in request
- **Token Counting**: Tracks usage for billing/rate limiting
- **Streaming**: Supports SSE responses for real-time output
- **Retry Logic**: Automatic retry with exponential backoff

### Application Security Implementation

#### HR Agent Token Handling

**File**: `hr-agent/app/auth.py`

```python
class TokenContext:
    """Holds authentication info from Kong-injected headers."""

    def __init__(
        self,
        user_scopes: str,
        user_sub: str,
        actor_chain: Optional[str],
        authorization: str,
        x_introspection_token: str,
    ):
        self.user_scopes = user_scopes
        self.user_sub = user_sub
        self.actor_chain = actor_chain
        self.authorization = authorization
        self.x_introspection_token = x_introspection_token
        self.exchanged_token = self._extract_exchanged_token()
        self.scopes_list = [s.strip() for s in self.user_scopes.split()]

    def _extract_exchanged_token(self) -> Optional[str]:
        """Extract access token from Kong's base64-encoded RFC 8693 response."""
        try:
            decoded_bytes = base64.b64decode(self.x_introspection_token)
            decoded_json = json.loads(decoded_bytes)
            access_token = decoded_json.get("access_token")

            logger.info(f"Extracted exchanged token with audience: {decoded_json.get('audience', 'unknown')}")
            logger.info(f"Token scopes: {decoded_json.get('scope', 'none')}")
            logger.info(f"Token expires in: {decoded_json.get('expires_in', 'unknown')} seconds")

            return access_token
        except Exception as e:
            logger.error(f"Failed to extract exchanged token: {e}")
            return None

    def get_headers(self) -> Dict[str, str]:
        """Get headers for MCP calls (includes user context)."""
        return {
            "Authorization": f"Bearer {self.exchanged_token or self.authorization}",
            "X-User-Scopes": self.user_scopes,
            "X-User-Sub": self.user_sub,
        }
```

**Purpose**:
- Extracts and decodes Kong's `x-introspection-token` header
- Parses RFC 8693 JSON response
- Provides scoped token for MCP calls
- Maintains user identity and scopes

#### MCP Server Token Validation

**File**: `hr-mcp-server/internal/handlers/mcp.go`

```go
// ExtractTokenFromHeader extracts exchanged token from Kong header
func ExtractTokenFromHeader(r *http.Request) (string, error) {
    introspectionHeader := r.Header.Get("exchanged-token")
    if introspectionHeader == "" {
        return "", fmt.Errorf("exchanged-token header not found")
    }

    // Base64 decode
    decoded, err := base64.StdEncoding.DecodeString(introspectionHeader)
    if err != nil {
        return "", fmt.Errorf("failed to decode exchanged-token: %w", err)
    }

    // Parse RFC 8693 response
    var tokenResponse struct {
        AccessToken      string `json:"access_token"`
        IssuedTokenType  string `json:"issued_token_type"`
        TokenType        string `json:"token_type"`
        ExpiresIn        int    `json:"expires_in"`
        Scope            string `json:"scope"`
    }

    if err := json.Unmarshal(decoded, &tokenResponse); err != nil {
        return "", fmt.Errorf("failed to parse token response: %w", err)
    }

    log.Printf("Extracted MCP token - Audience: api://mcp-internal, Scopes: %s, Expires in: %d seconds",
        tokenResponse.Scope, tokenResponse.ExpiresIn)

    return tokenResponse.AccessToken, nil
}

// HandleMCP processes MCP requests with scope validation
func HandleMCP(registry *tools.Registry) http.HandlerFunc {
    return func(w http.ResponseWriter, r *http.Request) {
        // Extract token
        mcpToken, err := ExtractTokenFromHeader(r)
        if err != nil {
            log.Printf("Token extraction failed: %v", err)
            http.Error(w, "Unauthorized", http.StatusUnauthorized)
            return
        }

        // Set in response header for client visibility
        w.Header().Set("X-MCP-Token", fmt.Sprintf("Bearer %s", mcpToken))

        // Extract user context from headers
        userScopes := strings.Split(r.Header.Get("X-User-Scopes"), " ")
        userSub := r.Header.Get("X-User-Sub")

        log.Printf("MCP call from user: %s, scopes: %v", userSub, userScopes)

        // Process MCP request
        var mcpRequest struct {
            JSONRPC string `json:"jsonrpc"`
            Method  string `json:"method"`
            Params  struct {
                Name      string                 `json:"name"`
                Arguments map[string]interface{} `json:"arguments"`
            } `json:"params"`
        }

        if err := json.NewDecoder(r.Body).Decode(&mcpRequest); err != nil {
            http.Error(w, "Invalid request", http.StatusBadRequest)
            return
        }

        // Get tool
        tool, exists := registry.GetTool(mcpRequest.Params.Name)
        if !exists {
            http.Error(w, "Tool not found", http.StatusNotFound)
            return
        }

        // Validate scope
        hasScope := false
        for _, scope := range userScopes {
            if scope == tool.RequiredScope {
                hasScope = true
                break
            }
        }

        if !hasScope {
            log.Printf("Authorization failed - user missing scope: %s", tool.RequiredScope)
            http.Error(w, fmt.Sprintf("Missing required scope: %s", tool.RequiredScope), http.StatusForbidden)
            return
        }

        // Execute tool
        result, err := tool.Handler(registry.store, mcpRequest.Params.Arguments)
        if err != nil {
            log.Printf("Tool execution failed: %v", err)
            http.Error(w, err.Error(), http.StatusInternalServerError)
            return
        }

        // Return result
        json.NewEncoder(w).Encode(map[string]interface{}{
            "jsonrpc": "2.0",
            "result":  result,
        })
    }
}
```

**Purpose**:
- Extracts and validates MCP token from Kong
- Validates user has required scope for tool
- Logs all access for audit trail
- Returns MCP token in response for tracing

---

## Value Proposition

### For Security Teams

**Centralized Policy Enforcement**
- All authentication/authorization logic in Kong configuration
- No need to trust application code to enforce security
- Update policies without redeploying applications
- Consistent security posture across all services

**Compliance and Audit**
- Complete audit trail with request correlation IDs
- Track who accessed what data and when
- GDPR, SOC2, HIPAA compliance support
- Centralized logging and monitoring

**Zero Trust Architecture**
- Authentication at every service boundary
- Token exchange prevents lateral movement
- Audience validation ensures tokens can't be reused
- Scope validation at multiple layers (defense in depth)

### For Development Teams

**Reduced Complexity**
- No authentication code in applications
- No OAuth/OIDC libraries needed
- No session management logic
- No API key storage/rotation

**Faster Development**
- Focus on business logic, not security
- Kong handles all token exchange complexity
- Standardized header-based authorization
- Easy testing with mock tokens

**Operational Excellence**
- API key rotation without code changes
- A/B testing with traffic routing
- Rate limiting and DDoS protection
- Automatic retry with failover

### For Business Stakeholders

**Cost Savings**
- Reduce development time (no auth code)
- Centralized API key management (no Claude API key in every service)
- Rate limiting prevents runaway LLM costs
- Faster time to market for new features

**Risk Reduction**
- Industry-standard security (OAuth 2.0, OIDC, RFC 8693)
- Proven Kong platform (used by 90% of Fortune 500)
- Regular security updates from Kong
- Reduced attack surface

**Scalability**
- Kong handles millions of requests per second
- Horizontal scaling with load balancing
- Multi-region deployment support
- Hybrid/multi-cloud ready

---

## Future Enhancements

### 1. ACL Implementation ✅ **COMPLETED**

**Status**: Implemented via AI MCP Proxy plugin with consumer group and tool-level ACLs.

**What was implemented**:
- Consumer group-based default ACL (hr-employees, hr-salary, hr-department)
- Tool-specific ACL overrides (deny alice@demo.local on list_employees_with_salaries)
- Full audit logging to /tmp/json.log
- Consumer mapping from exchanged tokens

See [AI MCP Proxy ACL Implementation](#ai-mcp-proxy-acl-implementation) for complete details.

**Benefits Achieved**:
- Tool-level access control (fine-grained per MCP tool)
- Group-based permissions (RBAC model)
- Explicit deny overrides (principle of least privilege)
- Full audit trail with ACL decisions logged

### 2. Rate Limiting Enhancements

**Goal**: Prevent API abuse and control LLM costs per user

**Implementation**:
```yaml
plugins:
  - name: rate-limiting-advanced
    config:
      limit:
        - 100  # Per minute
        - 1000 # Per hour
        - 5000 # Per day
      window_size:
        - 60
        - 3600
        - 86400
      identifier: consumer
      sync_rate: 10
      namespace: hr-demo
      strategy: cluster
```

**Benefits**:
- Prevent individual users from monopolizing LLM API
- Cost predictability (max $X per user per month)
- Protection against malicious actors

### 3. Advanced Analytics

**Goal**: Understand usage patterns and optimize costs

**Implementation**:
```yaml
plugins:
  - name: datadog
    config:
      host: datadog-agent
      port: 8125
      metrics:
        - name: request.count
          stat_type: counter
          tags:
            - consumer_id
            - route_id
            - status_code
        - name: llm.tokens
          stat_type: counter
          tags:
            - consumer_id
            - model_name
```

**Dashboards**:
- Token usage per user (cost attribution)
- Most called MCP tools (optimize caching)
- Error rates per route (reliability monitoring)
- Response time percentiles (performance SLOs)

### 4. Multi-Region Deployment

**Goal**: Low latency for global users

**Architecture**:
```
                      Kong Control Plane (Konnect)
                               │
        ┌──────────────────────┼──────────────────────┐
        │                      │                      │
  Kong DP (US-East)      Kong DP (EU-West)    Kong DP (APAC)
        │                      │                      │
    US Users              EU Users            APAC Users
```

**Benefits**:
- <50ms latency for 95% of users
- Regional data residency compliance
- Disaster recovery (automatic failover)

### 5. Machine Learning Security

**Goal**: Detect anomalous behavior and prevent attacks

**Features**:
- Anomaly detection (unusual access patterns)
- Prompt injection detection (filter malicious prompts)
- PII detection (prevent sensitive data leakage)
- Cost anomaly alerts (spike in token usage)

**Implementation**:
```yaml
plugins:
  - name: ai-prompt-guard
    config:
      injection_detection: true
      pii_redaction:
        - ssn
        - credit_card
        - email
      max_tokens: 4096
      alert_webhook: https://security.company.com/alerts
```

---

## Appendix

### Troubleshooting Common Issues

#### Issue 1: "Unauthorized" error on /api/agent

**Symptoms**:
- 401 status code
- "Invalid token" error in logs

**Diagnosis**:
1. Check Kong logs: `docker-compose logs kong-gateway | grep ERROR`
2. Verify session cookie exists in browser DevTools
3. Check Okta is reachable: `curl https://integrator-5602284.okta.com`

**Fix**:
- Clear browser cookies and re-login
- Verify `client_id` and `client_secret` in kong.yaml
- Check Okta application configuration

#### Issue 2: MCP Server returns 403 Forbidden

**Symptoms**:
- "Missing required scope" error
- Agent shows error: "Error calling tool"

**Diagnosis**:
1. Check user scopes: View Token Details in UI
2. Check tool requirements: See `hr-mcp-server/internal/tools/registry.go`
3. Verify token exchange succeeded: Check MCP logs for "Extracted MCP token"

**Fix**:
- Grant user additional scopes in Okta
- Update Kong OIDC plugin `introspection_post_args_values.scope`
- Re-login to get new token with updated scopes

#### Issue 3: LLM calls failing

**Symptoms**:
- "Error calling Claude API"
- Timeout errors

**Diagnosis**:
1. Check Anthropic API key: `docker-compose exec kong-gateway env | grep ANTHROPIC`
2. Verify rate limits not exceeded
3. Check network connectivity to api.anthropic.com

**Fix**:
- Update `.env` with valid ANTHROPIC_API_KEY
- Increase timeout in Kong AI Proxy config
- Check Anthropic dashboard for quota

### Security Best Practices

1. **Rotate Secrets Regularly**
   - Kong client secrets every 90 days
   - Anthropic API key every 180 days
   - Use Kong vault for storage

2. **Monitor Token Lifetime**
   - Set short token expiration (1 hour)
   - Implement refresh token rotation
   - Revoke tokens on logout

3. **Implement Rate Limiting**
   - Per-user limits to prevent abuse
   - Per-IP limits for DDoS protection
   - Cost limits for LLM calls

4. **Enable Audit Logging**
   - Log all token exchanges
   - Track sensitive data access
   - Alert on anomalies

5. **Use HTTPS Everywhere**
   - Kong TLS termination
   - Backend mTLS between services
   - Enforce HTTPS redirect

### Glossary

| Term | Definition |
|------|------------|
| **OIDC** | OpenID Connect - Authentication protocol built on OAuth 2.0 |
| **RFC 8693** | OAuth 2.0 Token Exchange specification |
| **PKCE** | Proof Key for Code Exchange - Security extension for OAuth |
| **Audience (`aud`)** | JWT claim specifying intended recipient of token |
| **Scope** | OAuth permission granted to client (e.g., `hr:salary:read`) |
| **Subject (`sub`)** | JWT claim identifying the user |
| **Introspection** | RFC 7662 - Token validation by calling OAuth server |
| **MCP** | Model Context Protocol - Standard for AI tool calling |
| **LangChain** | Python framework for building LLM applications |
| **Kong Gateway** | API gateway and service mesh platform |
| **Konnect** | Kong's control plane SaaS (manages gateway configuration) |

---

## Contact and Support

**Demo Repository**: https://github.com/your-org/hr-token-exchange-demo

**Kong Documentation**:
- OpenID Connect Plugin: https://docs.konghq.com/hub/kong-inc/openid-connect/
- AI Proxy Plugin: https://docs.konghq.com/hub/kong-inc/ai-proxy/
- ACL Plugin: https://docs.konghq.com/hub/kong-inc/acl/

**RFCs Referenced**:
- RFC 6749: OAuth 2.0 Authorization Framework
- RFC 8693: OAuth 2.0 Token Exchange
- RFC 7662: OAuth 2.0 Token Introspection
- RFC 7519: JSON Web Token (JWT)

**Questions?** Contact your Kong Solutions Engineer or email demo-support@konghq.com

---

*Last Updated: 2026-01-14*
*Version: 1.1 (Core Implementation Complete, AI MCP Proxy ACL Implemented)*
