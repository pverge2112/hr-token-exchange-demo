package tools

import (
	"encoding/json"
	"fmt"

	"github.com/hr-token-exchange-demo/hr-mcp-server/internal/data"
)

// Tool represents an MCP tool with scope requirements
type Tool struct {
	Name        string                 `json:"name"`
	Description string                 `json:"description"`
	InputSchema map[string]interface{} `json:"inputSchema"`
	RequiredScope string               `json:"-"`
	Handler     ToolHandler            `json:"-"`
}

// ToolHandler is a function that executes a tool
type ToolHandler func(store *data.Store, args map[string]interface{}) (interface{}, error)

// Registry manages available MCP tools
type Registry struct {
	tools map[string]*Tool
	store *data.Store
}

// NewRegistry creates a new tool registry
func NewRegistry(store *data.Store) *Registry {
	r := &Registry{
		tools: make(map[string]*Tool),
		store: store,
	}
	r.registerTools()
	return r
}

// registerTools registers all available tools
func (r *Registry) registerTools() {
	// get_employee tool
	r.tools["get_employee"] = &Tool{
		Name:        "get_employee",
		Description: "Get employee information by employee ID",
		InputSchema: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"employee_id": map[string]interface{}{
					"type":        "string",
					"description": "The employee ID (e.g., emp-001)",
				},
			},
			"required": []string{"employee_id"},
		},
		RequiredScope: "hr:employee:read",
		Handler:       r.getEmployee,
	}

	// update_employee tool
	r.tools["update_employee"] = &Tool{
		Name:        "update_employee",
		Description: "Update employee information",
		InputSchema: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"employee_id": map[string]interface{}{
					"type":        "string",
					"description": "The employee ID",
				},
				"title": map[string]interface{}{
					"type":        "string",
					"description": "New job title",
				},
				"location": map[string]interface{}{
					"type":        "string",
					"description": "New location",
				},
			},
			"required": []string{"employee_id"},
		},
		RequiredScope: "hr:employee:write",
		Handler:       r.updateEmployee,
	}

	// list_departments tool
	r.tools["list_departments"] = &Tool{
		Name:        "list_departments",
		Description: "List all departments in the organization",
		InputSchema: map[string]interface{}{
			"type":       "object",
			"properties": map[string]interface{}{},
		},
		RequiredScope: "hr:department:read",
		Handler:       r.listDepartments,
	}

	// get_salary tool
	r.tools["get_salary"] = &Tool{
		Name:        "get_salary",
		Description: "Get salary information for an employee (sensitive data)",
		InputSchema: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"employee_id": map[string]interface{}{
					"type":        "string",
					"description": "The employee ID",
				},
			},
			"required": []string{"employee_id"},
		},
		RequiredScope: "hr:salary:read",
		Handler:       r.getSalary,
	}

	// update_salary tool
	r.tools["update_salary"] = &Tool{
		Name:        "update_salary",
		Description: "Update salary information (highly sensitive operation)",
		InputSchema: map[string]interface{}{
			"type": "object",
			"properties": map[string]interface{}{
				"employee_id": map[string]interface{}{
					"type":        "string",
					"description": "The employee ID",
				},
				"base": map[string]interface{}{
					"type":        "integer",
					"description": "New base salary",
				},
				"bonus": map[string]interface{}{
					"type":        "integer",
					"description": "New bonus amount",
				},
			},
			"required": []string{"employee_id"},
		},
		RequiredScope: "hr:salary:write",
		Handler:       r.updateSalary,
	}

	// get_org_chart tool
	r.tools["get_org_chart"] = &Tool{
		Name:        "get_org_chart",
		Description: "Get organizational chart and structure",
		InputSchema: map[string]interface{}{
			"type":       "object",
			"properties": map[string]interface{}{},
		},
		RequiredScope: "hr:org:read",
		Handler:       r.getOrgChart,
	}

	// list_employees tool
	r.tools["list_employees"] = &Tool{
		Name:        "list_employees",
		Description: "List all employees in the organization",
		InputSchema: map[string]interface{}{
			"type":       "object",
			"properties": map[string]interface{}{},
		},
		RequiredScope: "hr:employee:read",
		Handler:       r.listEmployees,
	}

	// list_employees_with_salaries tool - EFFICIENT: Returns all employees with salary in one call
	r.tools["list_employees_with_salaries"] = &Tool{
		Name:        "list_employees_with_salaries",
		Description: "List all employees with their salary information. Use this instead of calling get_salary for each employee individually.",
		InputSchema: map[string]interface{}{
			"type":       "object",
			"properties": map[string]interface{}{},
		},
		RequiredScope: "hr:salary:read",
		Handler:       r.listEmployeesWithSalaries,
	}

	// list_employees_by_department tool - EFFICIENT: Returns employees grouped by department
	r.tools["list_employees_by_department"] = &Tool{
		Name:        "list_employees_by_department",
		Description: "List all employees grouped by their department. Use this to see which employees belong to each department.",
		InputSchema: map[string]interface{}{
			"type":       "object",
			"properties": map[string]interface{}{},
		},
		RequiredScope: "hr:employee:read",
		Handler:       r.listEmployeesByDepartment,
	}
}

// GetTools returns all tools (optionally filtered by scopes)
func (r *Registry) GetTools(scopes []string) []*Tool {
	if len(scopes) == 0 {
		// Return all tools if no scope filtering
		tools := make([]*Tool, 0, len(r.tools))
		for _, tool := range r.tools {
			tools = append(tools, tool)
		}
		return tools
	}

	// Filter tools by available scopes
	scopeMap := make(map[string]bool)
	for _, scope := range scopes {
		scopeMap[scope] = true
	}

	tools := make([]*Tool, 0)
	for _, tool := range r.tools {
		if scopeMap[tool.RequiredScope] {
			tools = append(tools, tool)
		}
	}
	return tools
}

// GetTool retrieves a specific tool by name
func (r *Registry) GetTool(name string) (*Tool, bool) {
	tool, ok := r.tools[name]
	return tool, ok
}

// Tool Handlers

func (r *Registry) getEmployee(store *data.Store, args map[string]interface{}) (interface{}, error) {
	employeeID, ok := args["employee_id"].(string)
	if !ok {
		return nil, fmt.Errorf("employee_id must be a string")
	}

	emp, err := store.GetEmployee(employeeID)
	if err != nil {
		return nil, err
	}

	return emp, nil
}

func (r *Registry) updateEmployee(store *data.Store, args map[string]interface{}) (interface{}, error) {
	employeeID, ok := args["employee_id"].(string)
	if !ok {
		return nil, fmt.Errorf("employee_id must be a string")
	}

	emp, err := store.GetEmployee(employeeID)
	if err != nil {
		return nil, err
	}

	// Update fields if provided
	if title, ok := args["title"].(string); ok {
		emp.Title = title
	}
	if location, ok := args["location"].(string); ok {
		emp.Location = location
	}

	err = store.UpdateEmployee(emp)
	if err != nil {
		return nil, err
	}

	return map[string]interface{}{
		"success": true,
		"employee": emp,
	}, nil
}

func (r *Registry) listEmployees(store *data.Store, args map[string]interface{}) (interface{}, error) {
	emps := store.ListEmployees()

	// Return simplified list with just ID and Name
	result := make([]map[string]string, 0, len(emps))
	for _, emp := range emps {
		result = append(result, map[string]string{
			"id":   emp.ID,
			"name": emp.Name,
		})
	}

	return result, nil
}

func (r *Registry) listDepartments(store *data.Store, args map[string]interface{}) (interface{}, error) {
	depts := store.ListDepartments()
	return depts, nil
}

func (r *Registry) getSalary(store *data.Store, args map[string]interface{}) (interface{}, error) {
	employeeID, ok := args["employee_id"].(string)
	if !ok {
		return nil, fmt.Errorf("employee_id must be a string")
	}

	sal, err := store.GetSalary(employeeID)
	if err != nil {
		return nil, err
	}

	return sal, nil
}

func (r *Registry) updateSalary(store *data.Store, args map[string]interface{}) (interface{}, error) {
	employeeID, ok := args["employee_id"].(string)
	if !ok {
		return nil, fmt.Errorf("employee_id must be a string")
	}

	sal, err := store.GetSalary(employeeID)
	if err != nil {
		return nil, err
	}

	// Update fields if provided
	if base, ok := args["base"].(float64); ok {
		sal.Base = int64(base)
	}
	if bonus, ok := args["bonus"].(float64); ok {
		sal.Bonus = int64(bonus)
	}
	if equity, ok := args["equity"].(float64); ok {
		sal.Equity = int64(equity)
	}

	err = store.UpdateSalary(sal)
	if err != nil {
		return nil, err
	}

	return map[string]interface{}{
		"success": true,
		"salary":  sal,
	}, nil
}

func (r *Registry) getOrgChart(store *data.Store, args map[string]interface{}) (interface{}, error) {
	chart := store.GetOrgChart()
	return chart, nil
}

func (r *Registry) listEmployeesWithSalaries(store *data.Store, args map[string]interface{}) (interface{}, error) {
	emps := store.ListEmployees()

	// Join employees with their salary information
	type EmployeeWithSalary struct {
		ID         string `json:"id"`
		Name       string `json:"name"`
		Email      string `json:"email"`
		Title      string `json:"title"`
		Department string `json:"department"`
		Location   string `json:"location"`
		Base       int64  `json:"base_salary"`
		Bonus      int64  `json:"bonus"`
		Equity     int64  `json:"equity"`
		Total      int64  `json:"total_compensation"`
	}

	result := make([]EmployeeWithSalary, 0, len(emps))
	for _, emp := range emps {
		sal, err := store.GetSalary(emp.ID)
		if err != nil {
			// Skip employees without salary data
			continue
		}

		result = append(result, EmployeeWithSalary{
			ID:         emp.ID,
			Name:       emp.Name,
			Email:      emp.Email,
			Title:      emp.Title,
			Department: emp.Department,
			Location:   emp.Location,
			Base:       sal.Base,
			Bonus:      sal.Bonus,
			Equity:     sal.Equity,
			Total:      sal.Base + sal.Bonus + sal.Equity,
		})
	}

	return result, nil
}

func (r *Registry) listEmployeesByDepartment(store *data.Store, args map[string]interface{}) (interface{}, error) {
	emps := store.ListEmployees()

	// Group employees by department
	empsByDept := make(map[string][]map[string]string)
	for _, emp := range emps {
		if _, exists := empsByDept[emp.Department]; !exists {
			empsByDept[emp.Department] = make([]map[string]string, 0)
		}

		empsByDept[emp.Department] = append(empsByDept[emp.Department], map[string]string{
			"id":    emp.ID,
			"name":  emp.Name,
			"title": emp.Title,
		})
	}

	return empsByDept, nil
}

// CallTool executes a tool with the given arguments
func (r *Registry) CallTool(name string, args map[string]interface{}) (interface{}, error) {
	tool, ok := r.GetTool(name)
	if !ok {
		return nil, fmt.Errorf("tool not found: %s", name)
	}

	return tool.Handler(r.store, args)
}

// MarshalJSON customizes JSON marshaling for Tool
func (t *Tool) MarshalJSON() ([]byte, error) {
	return json.Marshal(struct {
		Name        string                 `json:"name"`
		Description string                 `json:"description"`
		InputSchema map[string]interface{} `json:"inputSchema"`
	}{
		Name:        t.Name,
		Description: t.Description,
		InputSchema: t.InputSchema,
	})
}
