"""
HR Agent UI - OAuth Token Exchange Demo

This Flask application provides the UI layer for the HR Agent.
It runs behind Kong Gateway with OIDC plugin and calls the FastAPI agent backend.

Architecture:
Browser → Kong (OIDC) → Flask UI → Kong → HR Agent → Kong → MCP Server

Kong handles all OAuth flows automatically, including:
- Redirecting to Okta for authentication
- Handling the authorization code exchange
- Token exchange at each hop
- Proxying authenticated requests to this app
"""

from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import base64
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_NAME'] = 'flask_session'  # Avoid conflict with Kong's session cookie

# Configuration
class Config:
    # Internal service URLs (accessed via Kong)
    KONG_INTERNAL_URL = os.environ.get('KONG_INTERNAL_URL', 'http://kong-gateway:8000')

    # HR Agent endpoint
    AGENT_URL = os.environ.get('AGENT_URL', f'{KONG_INTERNAL_URL}/api/agent')

config = Config()


def decode_jwt_payload(token):
    """Decode JWT payload without verification (for display purposes)"""
    try:
        parts = token.split('.')
        if len(parts) != 3:
            return None

        # Add padding if needed
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += '=' * padding

        payload_json = base64.urlsafe_b64decode(payload_b64).decode('utf-8')
        return json.loads(payload_json)
    except Exception as e:
        print(f"Error decoding JWT: {e}", flush=True)
        return None


def get_user_info():
    """Extract user info from Kong's Authorization header"""
    # Kong sends the access token via standard Authorization: Bearer header
    auth_header = request.headers.get('Authorization', '')
    access_token = None
    token_payload = None

    if auth_header.startswith('Bearer '):
        access_token = auth_header[7:]  # Remove 'Bearer ' prefix
        print(f"[AUTH] Found Bearer token in Authorization header", flush=True)
        token_payload = decode_jwt_payload(access_token)

    return {
        'access_token': access_token,
        'token_payload': token_payload
    }


@app.route('/')
@app.route('/index')
def home():
    """
    Home page - HR Agent Chat Interface

    When a user accesses this route through Kong:
    1. Kong OIDC plugin checks for valid session
    2. If no session: Kong redirects to Okta
    3. User logs in and approves consent screen
    4. Kong gets token and proxies request here with Authorization header
    """
    # Get user info from Authorization header
    # Note: OAuth callback parameters (code, state) are cleaned up by JavaScript in the browser
    auth_data = get_user_info()

    # Log authenticated request
    if auth_data['token_payload']:
        print("\n" + "="*80, flush=True)
        print("[AUTHENTICATED REQUEST]", flush=True)
        print("="*80, flush=True)
        print(f"\n[USER INFO]", flush=True)
        print(f"  User (sub): {auth_data['token_payload'].get('sub', 'unknown')}", flush=True)
        print(f"  Email: {auth_data['token_payload'].get('email', 'NOT FOUND')}", flush=True)
        print(f"  Scopes: {auth_data['token_payload'].get('scope', 'NOT FOUND')}", flush=True)
        print("="*80 + "\n", flush=True)

    # Store the access token in session for later use
    if auth_data['access_token']:
        session['access_token'] = auth_data['access_token']
        print(f"[AUTH] Stored access token in session", flush=True)

    # Parse scopes for display
    scopes = []
    if auth_data['token_payload']:
        scope_str = auth_data['token_payload'].get('scope', '')
        scopes = [s for s in scope_str.split() if s.startswith('hr:')]

    return render_template('home.html',
                         user_info=auth_data['token_payload'],
                         token_payload=auth_data['token_payload'],
                         scopes=scopes,
                         authenticated=bool(auth_data['access_token']))


@app.route('/api/chat', methods=['POST'])
def api_chat():
    """
    Process chat message via the HR Agent Service
    Calls the FastAPI agent's /chat endpoint through Kong
    """
    # Get token from session
    access_token = session.get('access_token')

    if not access_token:
        print(f"[CHAT] No token in session, returning 401", flush=True)
        return jsonify({'error': 'Not authenticated - no token in session'}), 401

    # Decode and inspect token claims
    token_payload = decode_jwt_payload(access_token)
    if token_payload:
        print("\n" + "="*80, flush=True)
        print("[TOKEN_DEBUG] INITIAL TOKEN (from session) being sent to Kong:", flush=True)
        print("="*80, flush=True)
        print(f"  Token preview: {access_token[:20]}...{access_token[-20:]}", flush=True)
        print(f"  aud (audience): {token_payload.get('aud', 'NOT FOUND')}", flush=True)
        print(f"  sub (subject): {token_payload.get('sub', 'NOT FOUND')}", flush=True)
        print(f"  scope: {token_payload.get('scope', 'NOT FOUND')}", flush=True)
        print(f"  client_id: {token_payload.get('client_id', 'NOT FOUND')}", flush=True)
        print(f"  iss (issuer): {token_payload.get('iss', 'NOT FOUND')}", flush=True)
        print(f"  exp (expiry): {token_payload.get('exp', 'NOT FOUND')}", flush=True)
        print("="*80, flush=True)
        print("NOTE: Kong should exchange this token for api://hr-demo audience", flush=True)
        print("="*80 + "\n", flush=True)

    data = request.json
    message = data.get('message')
    chat_history = data.get('chat_history', [])

    if not message:
        return jsonify({'error': 'message is required'}), 400

    try:
        print(f"[CHAT] Forwarding query to HR agent", flush=True)
        print(f"  Message: {message}", flush=True)

        # Call HR Agent Service through Kong
        response = requests.post(
            config.AGENT_URL,
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            json={
                'message': message,
                'chat_history': chat_history
            },
            timeout=60
        )

        print(f"[CHAT] Agent responded with status: {response.status_code}", flush=True)

        if response.status_code == 200:
            data = response.json()
            print(f"[CHAT] Agent responded successfully", flush=True)

            # Store exchanged tokens if present in response
            if 'exchanged_token' in data and data['exchanged_token']:
                if 'exchanged_tokens' not in session:
                    session['exchanged_tokens'] = []

                # The exchanged_token now contains a 'tokens' array
                tokens_array = data['exchanged_token'].get('tokens', [])

                for token_info in tokens_array:
                    # Log token details for debugging
                    hop = token_info.get('hop')
                    claims = token_info.get('claims', {})
                    audience = claims.get('aud', 'Unknown')

                    print(f"\n[TOKEN_DEBUG] Received Hop {hop} token:", flush=True)
                    print(f"  Audience (aud): {audience}", flush=True)
                    print(f"  Subject (sub): {claims.get('sub', 'Unknown')}", flush=True)
                    print(f"  Scopes: {claims.get('scope', 'Unknown')}", flush=True)

                    # Check if this token is already stored (avoid duplicates)
                    token_exists = False
                    for stored_token in session['exchanged_tokens']:
                        if stored_token.get('token') == token_info.get('token'):
                            token_exists = True
                            print(f"[TOKEN_DEBUG] Token already stored, skipping duplicate", flush=True)
                            break

                    if not token_exists:
                        session['exchanged_tokens'].append(token_info)
                        print(f"[TOKEN] Stored exchanged token (Hop {hop}) with audience: {audience}", flush=True)

            return jsonify(data)
        else:
            print(f"[CHAT_ERROR] Agent returned {response.status_code}", flush=True)
            print(f"[CHAT_ERROR] Response: {response.text[:500]}", flush=True)
            return jsonify({
                'error': 'Agent service error',
                'status': response.status_code,
                'detail': response.text[:500]
            }), response.status_code

    except Exception as e:
        print(f"[CHAT_ERROR] {str(e)}", flush=True)
        return jsonify({
            'error': str(e),
            'response': 'I apologize, but I encountered an error processing your request.'
        }), 500


@app.route('/api/user-info')
def api_user_info():
    """API endpoint to get current user information"""
    auth_data = get_user_info()

    if not auth_data['access_token']:
        return jsonify({'error': 'Not authenticated'}), 401

    # Parse scopes
    scopes = []
    if auth_data['token_payload']:
        scope_str = auth_data['token_payload'].get('scope', '')
        scopes = [s for s in scope_str.split() if s.startswith('hr:')]

    return jsonify({
        'user': auth_data['token_payload'],
        'scopes': scopes,
        'authenticated': True
    })


@app.route('/api/token-details')
def api_token_details():
    """
    API endpoint to get detailed token information
    Returns the initial access token and decoded claims
    """
    access_token = session.get('access_token')

    if not access_token:
        return jsonify({'error': 'Not authenticated'}), 401

    # Decode token payload
    token_payload = decode_jwt_payload(access_token)

    if not token_payload:
        return jsonify({'error': 'Invalid token format'}), 400

    # Calculate token expiry info
    exp_timestamp = token_payload.get('exp')
    exp_datetime = None
    time_until_expiry = None

    if exp_timestamp:
        exp_datetime = datetime.fromtimestamp(exp_timestamp).isoformat()
        time_until_expiry = exp_timestamp - datetime.utcnow().timestamp()

    # Parse and categorize scopes
    scope_str = token_payload.get('scope', '')
    all_scopes = scope_str.split()
    hr_scopes = [s for s in all_scopes if s.startswith('hr:')]
    other_scopes = [s for s in all_scopes if not s.startswith('hr:')]

    # Get exchanged tokens from session
    exchanged_tokens = session.get('exchanged_tokens', [])

    return jsonify({
        'token': access_token,
        'claims': token_payload,
        'expiry': {
            'timestamp': exp_timestamp,
            'datetime': exp_datetime,
            'seconds_until_expiry': time_until_expiry
        },
        'scopes': {
            'hr_scopes': hr_scopes,
            'other_scopes': other_scopes,
            'all': all_scopes
        },
        'exchanged_tokens': exchanged_tokens,
        'token_exchange_info': {
            'description': 'Token exchanges happen at Kong Gateway level',
            'hops': [
                {
                    'hop': 1,
                    'from': 'Flask UI',
                    'to': 'HR Agent',
                    'endpoint': '/api/agent',
                    'mechanism': 'Kong OIDC plugin performs token exchange (RFC 8693)',
                    'audience': 'api://hr-demo',
                    'scopes_requested': 'hr:employee:read hr:employee:write hr:salary:read hr:department:read'
                },
                {
                    'hop': 2,
                    'from': 'HR Agent',
                    'to': 'MCP Server',
                    'endpoint': '/mcp',
                    'mechanism': 'Kong OIDC plugin performs second token exchange',
                    'audience': 'hr-agent',
                    'scopes_requested': 'Based on tool being called'
                }
            ],
            'note': 'Exchanged tokens are captured from responses and displayed below.'
        }
    })


@app.route('/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'service': 'hr-agent-ui',
        'timestamp': datetime.utcnow().isoformat()
    })


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8501))
    print(f"Starting HR Agent UI on port {port}", flush=True)
    print(f"Agent URL: {config.AGENT_URL}", flush=True)
    app.run(host='0.0.0.0', port=port, debug=True)
