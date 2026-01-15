# Vault Reference Quick Guide

## Quick Commands

```bash
# Apply vault configuration
cd kong/deck && ./apply-vaults.sh

# Or manually
export DECK_KONNECT_TOKEN=$KONNECT_TOKEN
deck gateway sync -s vaults.yaml --select-tag hr-demo

# Verify vault configuration
deck gateway dump --select-tag hr-demo | grep -A 10 'vaults:'

# Check environment variables in Kong Gateway
docker exec kong-gateway env | grep -E "(OKTA|OPENAI)"
```

## Vault Reference Mapping

### Complete Reference Table

| Vault Reference | Environment Variable | Type | Used In |
|----------------|---------------------|------|---------|
| `{vault://env/okta-hr-agent-client-id}` | `OKTA_HR_AGENT_CLIENT_ID` | OAuth Client ID | HR Agent OIDC plugin |
| `{vault://env/okta-hr-agent-client-secret}` | `OKTA_HR_AGENT_CLIENT_SECRET` | OAuth Secret | HR Agent OIDC plugin |
| `{vault://env/okta-hr-mcp-client-id}` | `OKTA_HR_MCP_CLIENT_ID` | OAuth Client ID | MCP Server OIDC plugin |
| `{vault://env/okta-hr-mcp-client-secret}` | `OKTA_HR_MCP_CLIENT_SECRET` | OAuth Secret | MCP Server OIDC plugin |
| `{vault://env/okta-streamlit-ui-client-id}` | `OKTA_STREAMLIT_UI_CLIENT_ID` | OAuth Client ID | Streamlit PKCE auth |
| `{vault://env/openai-api-key}` | `OPENAI_API_KEY` | API Key | AI Proxy Advanced |

## Where Each Secret is Used

### OKTA_HR_AGENT_CLIENT_ID & OKTA_HR_AGENT_CLIENT_SECRET
- **File**: `kong.yaml`
- **Lines**: 121, 124 (token exchange), 1096, 1099 (bearer auth)
- **Plugin**: `openid-connect`
- **Route**: `/api/agent` (HR Agent service)
- **Purpose**: OAuth token exchange to obtain scoped tokens for accessing HR Agent

### OKTA_HR_MCP_CLIENT_ID & OKTA_HR_MCP_CLIENT_SECRET
- **File**: `kong.yaml`
- **Lines**: 590, 593
- **Plugin**: `openid-connect`
- **Route**: `/mcp` (HR MCP Server)
- **Purpose**: OAuth token exchange to obtain scoped tokens for accessing MCP tools

### OKTA_STREAMLIT_UI_CLIENT_ID
- **File**: `kong.yaml`
- **Lines**: 1488
- **Plugin**: `openid-connect`
- **Route**: `/` (Streamlit UI)
- **Purpose**: PKCE-based authentication for end users (no client secret needed)

### OPENAI_API_KEY
- **File**: `kong.yaml`
- **Lines**: 987
- **Plugin**: `ai-proxy-advanced`
- **Route**: `/api/llm` (OpenAI proxy)
- **Purpose**: Authentication header for OpenAI API requests

## Vault Resolution Process

```
kong.yaml contains:
  client_id: "{vault://env/okta-hr-agent-client-id}"

            ↓ Kong resolves at runtime

1. Parse vault reference: vault=env, secret=okta-hr-agent-client-id
2. Lookup vault entity with prefix="env"
3. Convert secret name: okta-hr-agent-client-id → OKTA_HR_AGENT_CLIENT_ID
4. Read environment variable: OKTA_HR_AGENT_CLIENT_ID
5. Return value to plugin configuration
```

## Environment Variable Checklist

Before deploying, ensure these are set:

```bash
# Okta OAuth Clients (from Okta Admin Console)
□ OKTA_HR_AGENT_CLIENT_ID          # Format: 0oa[21 chars]
□ OKTA_HR_AGENT_CLIENT_SECRET      # Format: secret string
□ OKTA_HR_MCP_CLIENT_ID            # Format: 0oa[21 chars]
□ OKTA_HR_MCP_CLIENT_SECRET        # Format: secret string
□ OKTA_STREAMLIT_UI_CLIENT_ID      # Format: 0oa[21 chars]

# AI Provider Keys
□ OPENAI_API_KEY                   # Format: Bearer sk-...

# Kong Konnect (for decK)
□ KONNECT_TOKEN                    # Format: kpat_...
□ KONG_CLUSTER_CONTROL_PLANE       # Format: *.cp.konghq.com:443
□ KONG_CLUSTER_SERVER_NAME         # Format: *.cp.konghq.com
```

## Testing Vault Resolution

```bash
# 1. Start Kong Gateway with environment variables loaded
docker-compose up -d kong-gateway

# 2. Check Kong can read the variables
docker exec kong-gateway env | grep OKTA_HR_AGENT_CLIENT_ID

# 3. Test an endpoint that uses vault references
curl -v http://localhost:8000/api/agent \
  -H "Authorization: Bearer <token>"

# 4. Check Kong logs for vault errors
docker logs kong-gateway 2>&1 | grep -i vault

# Expected: No "could not find vault" or "no value found" errors
```

## Common Issues

| Issue | Check | Fix |
|-------|-------|-----|
| "could not find vault (env)" | Vault entity exists | Run `deck gateway sync -s vaults.yaml` |
| "no value found for key" | Env var is set | Check `docker exec kong-gateway env \| grep VAR_NAME` |
| "invalid credentials" | Correct value | Verify `.env` file, no extra quotes/spaces |
| Changes not applied | Kong restarted | Run `docker-compose restart kong-gateway` |

## decK Commands Reference

```bash
# Sync vault configuration only
deck gateway sync -s vaults.yaml --select-tag hr-demo

# Sync everything (vault + services + routes + plugins)
deck gateway sync -s kong.yaml --select-tag hr-demo

# Dump current configuration
deck gateway dump --select-tag hr-demo > current-config.yaml

# Validate configuration before applying
deck gateway validate -s vaults.yaml
deck gateway validate -s kong.yaml

# Diff between local and remote
deck gateway diff -s kong.yaml --select-tag hr-demo

# Reset configuration (careful!)
deck gateway reset --select-tag hr-demo --force
```

## File Structure

```
kong/deck/
├── kong.yaml              # Main Kong configuration (references vaults)
├── vaults.yaml           # Vault entity definition (apply this first)
├── apply-vaults.sh       # Helper script to apply vault config
├── VAULT_SETUP.md        # Detailed vault setup guide
└── VAULT_REFERENCE.md    # This quick reference (you are here)
```

## Deployment Workflow

1. **Local Development** (Docker Compose)
   ```bash
   # .env file in project root
   docker-compose up -d
   ```

2. **Konnect Control Plane** (decK)
   ```bash
   # Apply vault first
   deck gateway sync -s vaults.yaml --select-tag hr-demo

   # Then apply main config
   deck gateway sync -s kong.yaml --select-tag hr-demo
   ```

3. **Konnect Data Plane** (Environment Variables)
   - Set environment variables on each data plane node
   - Restart data plane to load new variables
   - Variables can be set via:
     - Kubernetes secrets
     - systemd environment files
     - Docker Compose .env
     - Cloud provider secret managers

## Additional Notes

- **Naming Convention**: Secret names in vault references use `kebab-case`, environment variables use `SCREAMING_SNAKE_CASE`
- **No Secrets in Git**: Never commit `.env` or files containing real credentials
- **Prefix Configuration**: The `config.prefix: ""` in `vaults.yaml` means no additional prefix is added
- **Case Sensitivity**: Environment variable names are case-sensitive; use exact UPPERCASE names
- **Whitespace**: Ensure no trailing spaces or quotes in `.env` file values

---

**Need more help?** See [VAULT_SETUP.md](./VAULT_SETUP.md) for detailed documentation.
