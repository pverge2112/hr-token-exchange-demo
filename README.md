# Kong Security Architecture: HR Token Exchange Demo

A production-grade demonstration of Kong Gateway's advanced security capabilities for AI agent architectures, featuring OAuth 2.0 Token Exchange (RFC 8693), fine-grained access control, and Model Context Protocol (MCP) security.

## 🎯 Demo Overview

This demo showcases a secure HR system where an AI agent accesses sensitive employee data through multiple service boundaries, with Kong Gateway providing comprehensive security at every layer.

**Key Security Features**:
- 🔒 **Zero Trust Architecture** - Every service boundary requires authentication
- 🎟️ **RFC 8693 Token Exchange** - Multi-hop token exchange with audience targeting
- 🛡️ **Fine-Grained Access Control** - Consumer groups + tool-level ACLs
- 🤖 **AI Gateway Integration** - Secure LLM access with API key management
- 📊 **Full Audit Logging** - Complete visibility into all security decisions

## 📐 Architecture

![Token Exchange Flow](./images/token-exchange-flow.png)

### Components

1. **Streamlit UI** - User interface for HR queries
2. **HR Agent** - AI agent that orchestrates LLM and MCP tool calls
3. **Kong Gateway** - Centralized security and API gateway
4. **HR MCP Server** - Model Context Protocol server with HR tools
5. **Anthropic Claude** - LLM for natural language processing

### Security Layers

| Layer | Authentication | Authorization | Token Type |
|-------|---------------|---------------|------------|
| **User → Agent** | Okta OIDC | Session cookie | `okta.com` audience |
| **Agent → MCP** | Token Exchange | Consumer groups | `api://hr-demo` audience |
| **MCP Tools** | Token Exchange | Tool-level ACL | `api://mcp-internal` audience |
| **Agent → LLM** | Kong AI Proxy | API key mgmt | Anthropic API key |

## 🔐 Security Highlights

### Multi-Hop Token Exchange (RFC 8693)

The demo implements a three-tier token exchange flow:

```
User Token (okta.com)
    ↓ [Token Exchange #1]
Agent Token (api://hr-demo, scopes: profile, email, hr:read)
    ↓ [Token Exchange #2]
MCP Token (api://mcp-internal, scopes: mcp:employee:read, mcp:salary:read)
```

Each exchange:
- ✅ Narrows the token audience to the specific service
- ✅ Reduces scopes to minimum required permissions
- ✅ Maintains user identity throughout the chain
- ✅ Provides defense-in-depth security

### Fine-Grained Access Control

**Consumer Groups** (Default ACL):
- `hr-employees` - Basic employee data access
- `hr-department` - Department information access
- `hr-salary` - Salary information access (most privileged)

**Tool-Level ACL** (Overrides):
- Specific users can be denied access to individual MCP tools
- Example: `alice@demo.local` is denied access to `list_employees_with_salaries`

**Access Control Matrix**:

| User | Consumer Groups | list_employees | list_employees_with_salaries |
|------|----------------|----------------|------------------------------|
| alice@demo.local | hr-employees, hr-department | ✅ Allowed | ❌ Denied (tool ACL) |
| bob@demo.local | hr-employees, hr-department, hr-salary | ✅ Allowed | ✅ Allowed |

## 🚀 Quick Start

### Prerequisites

- Docker and Docker Compose
- Kong Konnect account (free tier available)
- Okta developer account
- Anthropic API key

### Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/your-username/hr-token-exchange-demo.git
   cd hr-token-exchange-demo
   ```

2. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your actual values
   ```

3. **Obtain Kong Konnect certificates**:
   - See [kong-certs/README.md](kong-certs/README.md) for instructions
   - Download `tls.crt` and `tls.key` to `kong-certs/`

4. **Start the stack**:
   ```bash
   docker-compose up -d
   ```

5. **Access the UI**:
   - Open http://localhost:8501
   - Log in with your Okta credentials
   - Try HR queries like "Show me all employees" or "What's Alice's salary?"

### Configuration Files

- **`.env`** - Environment variables (gitignored, created from `.env.example`)
- **`kong/deck/kong.yaml`** - Kong Gateway configuration
- **`docker-compose.yaml`** - Service orchestration
- **`SECRETS_MANAGEMENT.md`** - Secrets management guide

## 📊 Demo Walkthrough

### Part 1: Basic Authentication Flow

1. **User Login**:
   - User authenticates via Okta
   - Receives session cookie with `okta.com` audience token
   - Token contains: `sub`, `email`, `groups`

2. **Query Submission**:
   - User asks: "Show me all employees"
   - Request flows through Kong with session cookie

### Part 2: Token Exchange for Agent

3. **First Token Exchange**:
   - Kong exchanges user token for agent token
   - Audience: `okta.com` → `api://hr-demo`
   - Scopes: All → `profile, email, hr:read`

4. **Agent Processing**:
   - HR Agent receives exchanged token
   - Plans to call MCP tools
   - Identifies user as `alice@demo.local`

### Part 3: Token Exchange for MCP

5. **Second Token Exchange**:
   - Kong exchanges agent token for MCP token
   - Audience: `api://hr-demo` → `api://mcp-internal`
   - Scopes: `hr:read` → `mcp:employee:read, mcp:salary:read`

6. **Consumer Mapping**:
   - Kong resolves consumer from token's `sub` claim
   - Maps to Kong consumer: `alice@demo.local`
   - Retrieves consumer groups: `hr-employees`, `hr-department`

### Part 4: Access Control

7. **Default ACL Check**:
   - AI MCP Proxy checks consumer groups
   - Alice has `hr-employees` ✅ (allowed by default ACL)

8. **Tool-Level ACL Override**:
   - For `list_employees_with_salaries` tool
   - Tool ACL denies `alice@demo.local` ❌
   - Request is blocked with 403 Forbidden

9. **Allowed Tool Access**:
   - For `list_employees` tool
   - No tool-level override exists
   - Default ACL allows (Alice has `hr-employees` group) ✅

### Part 5: Audit Logging

10. **Review Security Events**:
    ```bash
    docker-compose exec kong-gateway tail -f /tmp/json.log
    ```

    See:
    - Consumer identity
    - MCP tool called
    - ACL decision (allow/deny)
    - Request/response payloads

## 📚 Documentation

- **[KONG_SECURITY_DEMO.md](docs/KONG_SECURITY_DEMO.md)** - Comprehensive security architecture documentation
- **[SECRETS_MANAGEMENT.md](SECRETS_MANAGEMENT.md)** - Secrets and configuration management
- **[kong-certs/README.md](kong-certs/README.md)** - Kong Konnect certificate setup

## 🔍 Key Security Metrics

| Metric | Value | Description |
|--------|-------|-------------|
| **Authentication Boundaries** | 3 | User → Agent → MCP |
| **Token Audiences** | 3 | `okta.com`, `api://hr-demo`, `api://mcp-internal` |
| **OAuth Scopes** | 7 | Enforced at multiple layers |
| **Consumer Groups** | 3 | `hr-employees`, `hr-department`, `hr-salary` |
| **Tool-Level ACLs** | 1+ | Per-tool access overrides |
| **Session Lifetime** | 2 hours | With 15-min idle timeout |
| **Audit Logging** | 100% | All MCP tool access logged |

## 🛡️ Security Benefits

### Zero Trust Architecture
- No implicit trust between services
- Every request authenticated and authorized
- Token exchange enforces audience isolation

### Defense in Depth
- Multiple security layers:
  1. Session authentication (Okta)
  2. Token exchange with audience targeting
  3. Consumer group ACLs
  4. Tool-level ACL overrides
  5. Full audit logging

### Least Privilege
- Tokens scoped to minimum required permissions
- Consumer groups provide role-based access
- Tool ACLs enable fine-grained control

### Compliance & Auditing
- Complete audit trail of all security decisions
- Consumer identity tracked throughout request chain
- Payload logging for forensic analysis

## 🎓 Use Cases

This architecture pattern applies to:

- **AI Agent Platforms** - Secure multi-service AI architectures
- **HR Systems** - Protecting sensitive employee data
- **Healthcare** - PHI/PII protection with audit requirements
- **Financial Services** - PCI/SOX compliance scenarios
- **Enterprise SaaS** - Multi-tenant security isolation

## 🔧 Technology Stack

- **Kong Gateway 3.13** - API Gateway and security enforcement
- **Kong Konnect** - Cloud control plane for Kong
- **Okta** - Identity provider (OIDC)
- **Anthropic Claude** - Large language model
- **Model Context Protocol** - LLM tool integration standard
- **Docker Compose** - Container orchestration
- **Python/FastAPI** - Backend services
- **Streamlit** - User interface

## 📈 Future Enhancements

- [ ] Rate limiting per consumer group
- [ ] Dynamic scope calculation based on user attributes
- [ ] Token introspection caching
- [ ] Grafana dashboards for security metrics
- [ ] Slack notifications for ACL denials
- [ ] Time-based access controls (business hours only)

## 🤝 Contributing

This is a demonstration repository. For questions or feedback, please open an issue.

## 📄 License

[Add your license here]

## 🙏 Acknowledgments

- Kong Gateway team for AI MCP Proxy plugin
- Anthropic for Claude and Model Context Protocol
- Okta for developer-friendly OIDC implementation

---

*Version: 1.1 (Core Implementation Complete, AI MCP Proxy ACL Implemented)*
