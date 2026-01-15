# Kong Konnect Data Plane Certificates

This directory contains the TLS certificates required for the Kong Gateway data plane to connect to Kong Konnect control plane.

## Required Files

- `tls.crt` - Data plane certificate (public)
- `tls.key` - Data plane private key (**NEVER commit this to Git**)

## How to Obtain Certificates

1. Log into [Kong Konnect](https://cloud.konghq.com)
2. Navigate to **Gateway Manager** → **Data Plane Nodes**
3. Click **"New Data Plane Node"**
4. Konnect will generate and display:
   - Certificate (`tls.crt`)
   - Private Key (`tls.key`)
   - Control Plane endpoint
   - Telemetry endpoint

5. Save the certificate and key to this directory:
   ```bash
   # From the project root
   cp /path/to/downloaded/tls.crt kong-certs/tls.crt
   cp /path/to/downloaded/tls.key kong-certs/tls.key
   ```

6. Update your `.env` file with the control plane endpoints (see `.env.example`)

## Security Notes

⚠️ **IMPORTANT**: The `tls.key` file contains your private key and must be kept secure:
- Never commit it to version control (it's in `.gitignore`)
- Restrict file permissions: `chmod 600 kong-certs/tls.key`
- Do not share it in chat, email, or unsecured channels
- Each environment should have its own unique certificate

## Certificate Rotation

Kong Konnect data plane certificates do not expire, but you can rotate them at any time:
1. Generate new certificates in Kong Konnect
2. Replace the files in this directory
3. Restart the Kong Gateway container: `docker-compose restart kong-gateway`

## Troubleshooting

If Kong Gateway fails to connect to Konnect:
- Verify certificate files exist and are readable
- Check that control plane endpoints in `.env` match your Konnect organization
- Review Kong Gateway logs: `docker-compose logs kong-gateway`
- Ensure the certificate was downloaded from the correct Konnect organization
