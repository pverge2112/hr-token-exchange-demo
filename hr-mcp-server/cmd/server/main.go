package main

import (
	"log"
	"net/http"
	"os"

	"github.com/hr-token-exchange-demo/hr-mcp-server/internal/data"
	"github.com/hr-token-exchange-demo/hr-mcp-server/internal/handlers"
)

func main() {
	// Get port from environment or use default
	port := os.Getenv("PORT")
	if port == "" {
		port = "9000"
	}

	// Initialize data store
	store := data.NewStore()
	log.Println("Initialized mock HR data store")

	// Create MCP handler
	mcpHandler := handlers.NewHandler(store)

	// Setup HTTP server
	http.Handle("/mcp", mcpHandler)
	http.HandleFunc("/health", healthHandler)

	addr := ":" + port
	log.Printf("Starting HR MCP Server on %s", addr)
	log.Printf("MCP endpoint: http://localhost%s/mcp", addr)
	log.Printf("Health endpoint: http://localhost%s/health", addr)

	if err := http.ListenAndServe(addr, nil); err != nil {
		log.Fatalf("Server failed to start: %v", err)
	}
}

func healthHandler(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	w.Write([]byte(`{"status":"healthy","service":"hr-mcp-server"}`))
}
