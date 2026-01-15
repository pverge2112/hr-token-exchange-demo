package auth

import (
	"strings"
)

// ParseScopes parses a space-separated scope string into a slice
func ParseScopes(scopeStr string) []string {
	if scopeStr == "" {
		return []string{}
	}

	scopes := strings.Split(scopeStr, " ")
	result := make([]string, 0, len(scopes))
	for _, scope := range scopes {
		trimmed := strings.TrimSpace(scope)
		if trimmed != "" {
			result = append(result, trimmed)
		}
	}
	return result
}

// HasScope checks if a required scope is present in the available scopes
func HasScope(required string, available []string) bool {
	for _, scope := range available {
		if scope == required {
			return true
		}
	}
	return false
}

// ScopeError represents a scope-related error
type ScopeError struct {
	RequiredScope string
	Message       string
}

func (e *ScopeError) Error() string {
	return e.Message
}

// NewScopeError creates a new scope error
func NewScopeError(requiredScope string) *ScopeError {
	return &ScopeError{
		RequiredScope: requiredScope,
		Message:       "insufficient permissions: missing scope '" + requiredScope + "'",
	}
}
