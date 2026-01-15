# Secrets Management Guide

This document explains how sensitive data is managed in the HR Token Exchange Demo to prevent accidental exposure.

## Overview

This repository uses multiple layers of protection:
1. **Environment variables** for runtime secrets
2. **Kong Vault references** for accessing secrets in configuration
3. **`.gitignore`** to prevent committing sensitive files
4. **Template files** (`.example`) as safe-to-commit examples

## Sensitive Data in This Project

### 1. Environment Variables (`.env`)

**File**: `.env` (gitignored, never committed)

Contains runtime secrets that change per environment:

```bash
# Kong Konnect connection
KONG_CLUSTER_CONTROL_PLANE=your-cp-id.us.cp.konghq.com:443
KONG_CLUSTER_SERVER_NAME=your-cp-id.us.cp.konghq.com
KONG_CLUSTER_TELEMETRY_ENDPOINT=your-cp-id.us.tp.konghq.com:443
KONG_CLUSTER_TELEMETRY_SERVER_NAME=your-cp-id.us.tp.konghq.com

# OIDC Client Secrets
HR_AGENT_CLIENT_SECRET=your-actual-secret-here
HR_MCP_CLIENT_SECRET=your-actual-secret-here

# AI Provider API Key
ANTHROPIC_API_KEY=your-actual-api-key-here
```

**How to set up**:
```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual values
# NEVER commit .env to Git
```

### 2. Kong Configuration Vault References

**File**: `kong/deck/kong.yaml`

Kong configuration uses vault references to pull secrets from environment variables:

```yaml
# Example from kong.yaml
client_secret:
  - "{vault://env/hr-agent-client-secret}"
```

This tells Kong to read the secret from the `HR_AGENT_CLIENT_SECRET` environment variable at runtime.

**Current vault references in `kong.yaml`**:
- Line 124: `{vault://env/hr-agent-client-secret}` → reads `HR_AGENT_CLIENT_SECRET`
- Line 593: `{vault://env/hr-mcp-client-secret}` → reads `HR_MCP_CLIENT_SECRET`

### 3. Kong Konnect Certificates

**Directory**: `kong-certs/` (certificates gitignored)

Contains TLS certificates for data plane connection:
- `tls.crt` - Public certificate (can be committed if needed)
- `tls.key` - **Private key (NEVER commit)**

See [kong-certs/README.md](kong-certs/README.md) for how to obtain these.

## Setup Instructions

### First Time Setup

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd hr-token-exchange-demo
   ```

2. **Create `.env` from template**:
   ```bash
   cp .env.example .env
   ```

3. **Obtain Kong Konnect credentials**:
   - Log into [Kong Konnect](https://cloud.konghq.com)
   - Create a new data plane node
   - Download certificates to `kong-certs/`
   - Copy control plane endpoints

4. **Update `.env` with your values**:
   ```bash
   # Edit .env and replace all placeholder values
   nano .env  # or your preferred editor
   ```

5. **Set up OIDC client secrets**:
   - Register OAuth clients in your identity provider (Okta, Auth0, etc.)
   - Add client secrets to `.env`

6. **Get AI provider API key**:
   - Sign up for Anthropic API
   - Add API key to `.env`

7. **Verify `.env` is gitignored**:
   ```bash
   git status  # .env should NOT appear
   ```

## Security Best Practices

### ✅ DO

- Use `.env` files for all secrets
- Keep `.env.example` updated with placeholders
- Use Kong vault references in `kong.yaml`
- Rotate secrets regularly
- Use different secrets per environment (dev, staging, prod)
- Restrict file permissions: `chmod 600 .env kong-certs/tls.key`

### ❌ DON'T

- Never commit `.env` files
- Never hardcode secrets in configuration files
- Never share secrets in chat, email, or unsecured channels
- Never commit private keys or certificates
- Never use production secrets in development

## Pre-Commit Checklist

Before committing changes, verify:

```bash
# 1. Check git status for sensitive files
git status

# 2. Search for potential secrets in staged files
git diff --cached | grep -i "secret\|password\|key\|token"

# 3. Verify .env is not staged
git ls-files | grep "\.env$"  # Should return nothing

# 4. Verify certificates are not staged
git ls-files | grep "kong-certs/.*\.(key|crt|pem)"  # Should return nothing
```

## What's Safe to Commit

✅ **Safe**:
- `.env.example` (with placeholder values)
- `kong/deck/kong.yaml` (with vault references)
- `docker-compose.yaml` (with `${VARIABLE}` references)
- Documentation files
- Application code

❌ **Never commit**:
- `.env` (actual secrets)
- `kong-certs/*.key` (private keys)
- Any file containing actual API keys, passwords, or tokens

## Environment-Specific Configuration

For multiple environments:

```bash
# Development
.env                    # Local development secrets

# Staging
.env.staging           # Staging secrets (gitignored)

# Production
.env.production        # Production secrets (gitignored, managed via CI/CD)
```

Update `.gitignore` to exclude all `.env*` variants except `.env.example`.

## CI/CD Integration

For automated deployments:

1. Store secrets in your CI/CD platform's secret manager:
   - GitHub Secrets
   - GitLab CI/CD Variables
   - AWS Secrets Manager
   - HashiCorp Vault

2. Inject secrets as environment variables at runtime

3. Never log or expose secrets in CI/CD output

## Troubleshooting

### "Vault reference not resolving"

Kong can't find the environment variable:
```bash
# Verify environment variable is set
docker-compose exec kong-gateway env | grep HR_AGENT_CLIENT_SECRET

# Check vault reference syntax in kong.yaml
# Should be: {vault://env/variable-name-in-lowercase-with-hyphens}
```

### "Control plane connection failed"

Check Kong Konnect configuration:
```bash
# Verify endpoints in .env match Konnect console
# Verify certificates are in kong-certs/
ls -la kong-certs/

# Check Kong logs
docker-compose logs kong-gateway
```

## Additional Resources

- [Kong Vault Documentation](https://docs.konghq.com/gateway/latest/kong-enterprise/secrets-management/)
- [Kong Konnect Data Plane Setup](https://docs.konghq.com/konnect/gateway-manager/data-plane-nodes/)
- [Docker Compose Environment Variables](https://docs.docker.com/compose/environment-variables/)
