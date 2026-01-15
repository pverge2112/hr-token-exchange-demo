# Kong Vault Configuration Guide

This guide explains how to set up and use Kong's ENV vault to securely manage secrets for the HR Token Exchange Demo.

## Overview

Kong vaults allow you to store sensitive credentials outside of your configuration files and reference them securely. This demo uses the **ENV vault**, which reads secrets from environment variables on the Kong Gateway data plane.

## Vault References in Use

The following vault references are used throughout the Kong configuration (`kong.yaml`):

### Okta OAuth Client Credentials

| Vault Reference | Environment Variable | Used By |
|----------------|---------------------|---------|
| `{vault://env/okta-hr-agent-client-id}` | `OKTA_HR_AGENT_CLIENT_ID` | HR Agent service (token exchange) |
| `{vault://env/okta-hr-agent-client-secret}` | `OKTA_HR_AGENT_CLIENT_SECRET` | HR Agent service (token exchange) |
| `{vault://env/okta-hr-mcp-client-id}` | `OKTA_HR_MCP_CLIENT_ID` | HR MCP Server (token exchange) |
| `{vault://env/okta-hr-mcp-client-secret}` | `OKTA_HR_MCP_CLIENT_SECRET` | HR MCP Server (token exchange) |
| `{vault://env/okta-streamlit-ui-client-id}` | `OKTA_STREAMLIT_UI_CLIENT_ID` | Streamlit UI (PKCE auth) |

### AI Provider Credentials

| Vault Reference | Environment Variable | Used By |
|----------------|---------------------|---------|
| `{vault://env/openai-api-key}` | `OPENAI_API_KEY` | AI Proxy Advanced plugin |

## Quick Start

### 1. Set Environment Variables

Ensure all required environment variables are set in your `.env` file:

```bash
# Okta OAuth Applications
OKTA_HR_AGENT_CLIENT_ID=0oa...
OKTA_HR_AGENT_CLIENT_SECRET=xxx...
OKTA_HR_MCP_CLIENT_ID=0oa...
OKTA_HR_MCP_CLIENT_SECRET=xxx...
OKTA_STREAMLIT_UI_CLIENT_ID=0oa...

# AI Provider
OPENAI_API_KEY=Bearer sk-...

# Kong Konnect (for decK)
KONNECT_TOKEN=kpat_...
```

### 2. Apply Vault Configuration

Use the provided helper script:

```bash
cd kong/deck
./apply-vaults.sh
```

Or manually with decK:

```bash
export DECK_KONNECT_TOKEN=$KONNECT_TOKEN
export DECK_KONNECT_CONTROL_PLANE_NAME=kong-token-exchange-prototype
deck gateway sync -s vaults.yaml --select-tag hr-demo
```

### 3. Apply Main Configuration

After the vault is configured, apply your main Kong configuration:

```bash
deck gateway sync -s kong.yaml --select-tag hr-demo
```

## How It Works

### ENV Vault Configuration

The `vaults.yaml` file defines an ENV vault with the following configuration:

```yaml
vaults:
  - name: env
    prefix: env
    description: ENV vault for reading secrets from environment variables
    config:
      prefix: ""  # No additional prefix on env var names
```

### Name Resolution

Kong resolves vault references to environment variables using this pattern:

1. Vault reference format: `{vault://PREFIX/secret-name}`
2. Environment variable format: `CONFIG_PREFIX + UPPERCASE(secret-name with hyphens → underscores)`

**Examples:**

- `{vault://env/okta-hr-agent-client-id}` → `OKTA_HR_AGENT_CLIENT_ID`
- `{vault://env/openai-api-key}` → `OPENAI_API_KEY`

Since our `config.prefix` is blank (`""`), the secret name is directly converted to the environment variable name.

### For Local Development (Docker)

When running locally with Docker Compose, Kong Gateway reads environment variables from:

1. The `.env` file in the project root (loaded by docker-compose)
2. Variables defined in `docker-compose.yaml` under the `kong-gateway` service

Make sure your `.env` file contains all required variables.

### For Konnect Deployments

For Kong Konnect managed deployments:

1. **Control Plane Configuration**: The vault entity is synced to Konnect via decK
2. **Data Plane Environment**: You must set environment variables on each data plane node

**Setting variables on Konnect data planes:**

- For cloud-hosted data planes: Use Konnect's Control Plane configuration UI
- For self-hosted data planes: Set environment variables in your deployment (K8s secrets, systemd, etc.)

## Verifying Vault Configuration

### 1. Check Vault Entity

Dump your current configuration to verify the vault exists:

```bash
deck gateway dump --konnect-token $KONNECT_TOKEN \
  --konnect-control-plane-name kong-token-exchange-prototype \
  --select-tag hr-demo | grep -A 10 'vaults:'
```

You should see:

```yaml
vaults:
  - name: env
    prefix: env
    description: ENV vault for reading secrets from environment variables
    config:
      prefix: ""
```

### 2. Test Vault Resolution

Test that Kong can resolve vault references:

```bash
# Test the Streamlit UI endpoint (uses PKCE with Okta client ID from vault)
curl -v http://localhost:8000/

# Test the HR Agent endpoint (uses client secret from vault for token exchange)
curl -v http://localhost:8000/api/agent \
  -H "Authorization: Bearer <test-token>"
```

Check Kong Gateway logs for any vault resolution errors:

```bash
docker logs kong-gateway 2>&1 | grep -i vault
```

### 3. Common Error Messages

| Error | Cause | Solution |
|-------|-------|----------|
| `could not find vault` | Vault not configured | Apply `vaults.yaml` with decK |
| `no value found in vault` | Environment variable not set | Set the required env var on data plane |
| `vault ENV has no value` | Env var name mismatch | Check secret name → env var conversion |

## Vault Configuration Files

This directory contains:

| File | Purpose |
|------|---------|
| `vaults.yaml` | decK configuration defining the ENV vault entity |
| `apply-vaults.sh` | Helper script to validate and apply vault config |
| `VAULT_SETUP.md` | This documentation file |
| `kong.yaml` | Main Kong configuration (references vault secrets) |

## Security Best Practices

1. **Never commit secrets**: Keep `.env` and actual credential values out of version control
2. **Use `.env.example`**: Provide a template without real values
3. **Rotate credentials**: Regularly rotate OAuth client secrets and API keys
4. **Restrict access**: Limit who can view environment variables on data planes
5. **Audit access**: Monitor which services access vault secrets via Kong logs

## Alternative Vault Backends

While this demo uses the ENV vault, Kong supports other backends for production use:

- **AWS Secrets Manager**: Store secrets in AWS with automatic rotation
- **HashiCorp Vault**: Enterprise secret management with fine-grained access control
- **GCP Secret Manager**: Google Cloud's secret storage service
- **Azure Key Vault**: Microsoft Azure's key management service
- **Konnect Config Store**: Konnect's built-in secret storage (beta)

See Kong's [Vault documentation](https://docs.konghq.com/gateway/latest/kong-enterprise/secrets-management/) for more details.

## Troubleshooting

### Vault not found

**Symptom**: Kong logs show `could not find vault (env)`

**Solution**:
```bash
# Re-apply vault configuration
deck gateway sync -s vaults.yaml --select-tag hr-demo

# Verify it was created
deck gateway dump --select-tag hr-demo | grep -A 5 'vaults:'
```

### Secret not resolved

**Symptom**: Kong logs show `no value found in vault for key 'okta-hr-agent-client-id'`

**Solution**:
```bash
# Verify environment variable is set (for Docker)
docker exec kong-gateway env | grep OKTA_HR_AGENT_CLIENT_ID

# For local testing, restart Kong after setting env vars
docker-compose restart kong-gateway
```

### Wrong value returned

**Symptom**: OAuth fails with invalid client credentials

**Solution**:
```bash
# Check that env var value is correct
echo $OKTA_HR_AGENT_CLIENT_SECRET

# Verify .env file is loaded
docker-compose config | grep OKTA_HR_AGENT_CLIENT_SECRET

# Check for extra quotes or whitespace in .env
cat .env | grep OKTA_HR_AGENT_CLIENT_SECRET
```

## Additional Resources

- [Kong Vault Entity Reference](https://docs.konghq.com/gateway/latest/kong-enterprise/secrets-management/reference/)
- [ENV Vault Configuration](https://docs.konghq.com/gateway/latest/kong-enterprise/secrets-management/backends/env/)
- [decK Vault Management](https://docs.konghq.com/deck/latest/guides/vaults/)
- [Konnect Config Store](https://docs.konghq.com/konnect/gateway-manager/configuration/)

## Support

For issues with this demo:
- Check the main [README.md](../../README.md)
- Review [SECRETS_MANAGEMENT.md](../../docs/SECRETS_MANAGEMENT.md)
- Open an issue in the repository
