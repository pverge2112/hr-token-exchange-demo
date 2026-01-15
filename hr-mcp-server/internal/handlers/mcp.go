package handlers

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"

	"github.com/hr-token-exchange-demo/hr-mcp-server/internal/auth"
	"github.com/hr-token-exchange-demo/hr-mcp-server/internal/data"
	"github.com/hr-token-exchange-demo/hr-mcp-server/internal/tools"
)

// MCPRequest represents a JSON-RPC 2.0 request
type MCPRequest struct {
	JSONRPC string                 `json:"jsonrpc"`
	ID      interface{}            `json:"id"`
	Method  string                 `json:"method"`
	Params  map[string]interface{} `json:"params,omitempty"`
}

// MCPResponse represents a JSON-RPC 2.0 response
type MCPResponse struct {
	JSONRPC string      `json:"jsonrpc"`
	ID      interface{} `json:"id"`
	Result  interface{} `json:"result,omitempty"`
	Error   *MCPError   `json:"error,omitempty"`
}

// MCPError represents a JSON-RPC 2.0 error
type MCPError struct {
	Code    int         `json:"code"`
	Message string      `json:"message"`
	Data    interface{} `json:"data,omitempty"`
}

// TokenExchangeResponse represents the RFC 8693 token exchange response
type TokenExchangeResponse struct {
	AccessToken     string `json:"access_token"`
	IssuedTokenType string `json:"issued_token_type"`
	TokenType       string `json:"token_type"`
	ExpiresIn       int    `json:"expires_in"`
	Scope           string `json:"scope"`
}

// Handler manages MCP protocol requests
type Handler struct {
	registry *tools.Registry
	store    *data.Store
}

// NewHandler creates a new MCP handler
func NewHandler(store *data.Store) *Handler {
	return &Handler{
		registry: tools.NewRegistry(store),
		store:    store,
	}
}

// min returns the minimum of two integers
func min(a, b int) int {
	if a < b {
		return a
	}
	return b
}

// ServeHTTP handles HTTP requests
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
	// Set CORS headers
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-User-Scopes, X-User-Sub, X-Actor-Chain, Authorization, x-introspection-token")

	// Check for exchanged token from Kong's token exchange introspection
	// Kong sends the exchanged token in x-introspection-token header
	introspectionHeader := r.Header.Get("x-introspection-token")
	var tokenToCapture string

	if introspectionHeader != "" {
		// Debug: Log the raw introspection header value
		log.Printf("[MCP_DEBUG] x-introspection-token header received (length: %d)", len(introspectionHeader))
		if len(introspectionHeader) > 100 {
			log.Printf("[MCP_DEBUG] Header value (first 100 chars): %s...", introspectionHeader[:100])
		}

		// Kong base64-encodes the RFC 8693 JSON response and sends it in this header
		// First, try to base64 decode it
		decodedBytes, err := base64.StdEncoding.DecodeString(introspectionHeader)
		if err != nil {
			log.Printf("[MCP] Failed to base64 decode x-introspection-token: %v", err)
		} else {
			decodedStr := string(decodedBytes)
			log.Printf("[MCP_DEBUG] Decoded header (first 200 chars): %s", decodedStr[:min(len(decodedStr), 200)])

			// Now try to parse the decoded string as JSON
			var exchangeResp TokenExchangeResponse
			if err := json.Unmarshal(decodedBytes, &exchangeResp); err == nil && exchangeResp.AccessToken != "" {
				// Successfully parsed JSON - use the exchanged access_token
				tokenToCapture = "Bearer " + exchangeResp.AccessToken
				log.Printf("[MCP] ✓ Captured EXCHANGED token from x-introspection-token header")
				log.Printf("[MCP] Token type: %s, Issued type: %s, Expires in: %d seconds",
					exchangeResp.TokenType, exchangeResp.IssuedTokenType, exchangeResp.ExpiresIn)
				log.Printf("[MCP] Exchanged token preview: %s...%s",
					exchangeResp.AccessToken[:40], exchangeResp.AccessToken[len(exchangeResp.AccessToken)-20:])
			} else {
				log.Printf("[MCP] Failed to parse decoded JSON: %v", err)
			}
		}
	}

	// Fallback to Authorization header if no exchanged token found
	if tokenToCapture == "" {
		authHeader := r.Header.Get("Authorization")
		if authHeader != "" {
			tokenToCapture = authHeader
			log.Printf("[MCP] Using token from Authorization header (no exchange token found)")
		}
	}

	// Set the captured token in response header
	if tokenToCapture != "" {
		w.Header().Set("X-MCP-Token", tokenToCapture)
		// Debug: Log what token we're sending back
		if len(tokenToCapture) > 50 {
			log.Printf("[MCP_DEBUG] Setting X-MCP-Token (length: %d): %s...%s",
				len(tokenToCapture), tokenToCapture[:40], tokenToCapture[len(tokenToCapture)-20:])
		} else {
			log.Printf("[MCP_DEBUG] Setting X-MCP-Token: %s", tokenToCapture)
		}
	}

	if r.Method == "OPTIONS" {
		w.WriteHeader(http.StatusOK)
		return
	}

	if r.Method != "POST" {
		h.sendError(w, nil, -32600, "Method not allowed", nil)
		return
	}

	// Read request body
	body, err := io.ReadAll(r.Body)
	if err != nil {
		h.sendError(w, nil, -32700, "Parse error", nil)
		return
	}
	defer r.Body.Close()

	// Parse JSON-RPC request
	var req MCPRequest
	if err := json.Unmarshal(body, &req); err != nil {
		h.sendError(w, nil, -32700, "Parse error", nil)
		return
	}

	// Get user scopes from Kong header
	scopeHeader := r.Header.Get("X-User-Scopes")
	userScopes := auth.ParseScopes(scopeHeader)

	// Get user subject and actor chain for logging
	userSub := r.Header.Get("X-User-Sub")
	actorChain := r.Header.Get("X-Actor-Chain")

	log.Printf("[MCP] Method: %s, User: %s, Scopes: %v, Actor: %s",
		req.Method, userSub, userScopes, actorChain)

	// Route to appropriate handler
	switch req.Method {
	case "initialize":
		h.handleInitialize(w, &req)
	case "tools/list":
		h.handleToolsList(w, &req, userScopes)
	case "tools/call":
		h.handleToolsCall(w, &req, userScopes)
	default:
		h.sendError(w, req.ID, -32601, "Method not found", nil)
	}
}

// handleInitialize handles MCP initialization
func (h *Handler) handleInitialize(w http.ResponseWriter, req *MCPRequest) {
	result := map[string]interface{}{
		"protocolVersion": "2024-11-05",
		"capabilities": map[string]interface{}{
			"tools": map[string]interface{}{},
		},
		"serverInfo": map[string]interface{}{
			"name":    "hr-mcp-server",
			"version": "1.0.0",
		},
	}

	h.sendResponse(w, req.ID, result)
}

// handleToolsList handles tools/list requests
func (h *Handler) handleToolsList(w http.ResponseWriter, req *MCPRequest, scopes []string) {
	// TEMPORARY: Return ALL tools without scope filtering
	// Kong ACL will handle authorization when tools are called
	availableTools := h.registry.GetTools([]string{})

	result := map[string]interface{}{
		"tools": availableTools,
	}

	log.Printf("[MCP] tools/list returned %d tools (scope filtering disabled, Kong will enforce)", len(availableTools))

	h.sendResponse(w, req.ID, result)
}

// handleToolsCall handles tools/call requests
func (h *Handler) handleToolsCall(w http.ResponseWriter, req *MCPRequest, scopes []string) {
	// Extract tool name
	toolName, ok := req.Params["name"].(string)
	if !ok {
		h.sendError(w, req.ID, -32602, "Invalid params: name required", nil)
		return
	}

	// Extract arguments
	args, ok := req.Params["arguments"].(map[string]interface{})
	if !ok {
		args = make(map[string]interface{})
	}

	// Note: Authorization is handled by Kong Gateway via token exchange and scope validation
	// If the request reaches here, Kong has already validated that the user has the required scopes
	log.Printf("[MCP] Executing tool: %s for user with scopes: %v", toolName, scopes)

	// Execute the tool (CallTool will validate that the tool exists)
	result, err := h.registry.CallTool(toolName, args)
	if err != nil {
		log.Printf("[MCP] Tool execution error - Tool: %s, Error: %v", toolName, err)
		h.sendError(w, req.ID, -32000, fmt.Sprintf("Tool execution failed: %v", err), nil)
		return
	}

	log.Printf("[MCP] Tool executed successfully - Tool: %s", toolName)

	// Marshal result to JSON for proper formatting
	resultJSON, err := json.Marshal(result)
	if err != nil {
		log.Printf("[MCP] Error marshaling result: %v", err)
		h.sendError(w, req.ID, -32000, fmt.Sprintf("Failed to format result: %v", err), nil)
		return
	}

	// Return result
	response := map[string]interface{}{
		"content": []map[string]interface{}{
			{
				"type": "text",
				"text": string(resultJSON),
			},
		},
	}

	h.sendResponse(w, req.ID, response)
}

// sendResponse sends a successful JSON-RPC response
func (h *Handler) sendResponse(w http.ResponseWriter, id interface{}, result interface{}) {
	resp := MCPResponse{
		JSONRPC: "2.0",
		ID:      id,
		Result:  result,
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(resp)
}

// sendError sends a JSON-RPC error response
func (h *Handler) sendError(w http.ResponseWriter, id interface{}, code int, message string, data interface{}) {
	resp := MCPResponse{
		JSONRPC: "2.0",
		ID:      id,
		Error: &MCPError{
			Code:    code,
			Message: message,
			Data:    data,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(resp)
}
