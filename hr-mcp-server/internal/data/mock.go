package data

import (
	"fmt"
	"sync"
)

// Employee represents an employee record
type Employee struct {
	ID         string `json:"id"`
	Name       string `json:"name"`
	Email      string `json:"email"`
	Title      string `json:"title"`
	Department string `json:"department"`
	ManagerID  string `json:"manager_id,omitempty"`
	StartDate  string `json:"start_date"`
	Location   string `json:"location"`
}

// Department represents a department
type Department struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	HeadID string `json:"head_id"`
	Budget int64  `json:"budget"`
}

// Salary represents salary information
type Salary struct {
	EmployeeID string `json:"employee_id"`
	Base       int64  `json:"base"`
	Bonus      int64  `json:"bonus"`
	Equity     int64  `json:"equity"`
}

// Store provides access to mock HR data
type Store struct {
	employees   map[string]*Employee
	departments map[string]*Department
	salaries    map[string]*Salary
	mu          sync.RWMutex
}

// NewStore creates a new data store with mock data
func NewStore() *Store {
	store := &Store{
		employees:   make(map[string]*Employee),
		departments: make(map[string]*Department),
		salaries:    make(map[string]*Salary),
	}
	store.loadMockData()
	return store
}

func (s *Store) loadMockData() {
	// Departments
	s.departments["dept-eng"] = &Department{
		ID:     "dept-eng",
		Name:   "Engineering",
		HeadID: "emp-010",
		Budget: 5000000,
	}
	s.departments["dept-prod"] = &Department{
		ID:     "dept-prod",
		Name:   "Product",
		HeadID: "emp-011",
		Budget: 2000000,
	}
	s.departments["dept-hr"] = &Department{
		ID:     "dept-hr",
		Name:   "Human Resources",
		HeadID: "emp-012",
		Budget: 1000000,
	}
	s.departments["dept-sales"] = &Department{
		ID:     "dept-sales",
		Name:   "Sales",
		HeadID: "emp-013",
		Budget: 3000000,
	}

	// Employees
	employees := []*Employee{
		{
			ID:         "emp-001",
			Name:       "Sarah Chen",
			Email:      "sarah.chen@corp.com",
			Title:      "Senior Engineer",
			Department: "Engineering",
			ManagerID:  "emp-010",
			StartDate:  "2021-03-15",
			Location:   "San Francisco",
		},
		{
			ID:         "emp-002",
			Name:       "Marcus Johnson",
			Email:      "marcus.johnson@corp.com",
			Title:      "Product Manager",
			Department: "Product",
			ManagerID:  "emp-011",
			StartDate:  "2020-08-01",
			Location:   "New York",
		},
		{
			ID:         "emp-003",
			Name:       "Priya Patel",
			Email:      "priya.patel@corp.com",
			Title:      "Staff Engineer",
			Department: "Engineering",
			ManagerID:  "emp-010",
			StartDate:  "2019-01-10",
			Location:   "Seattle",
		},
		{
			ID:         "emp-004",
			Name:       "James Lee",
			Email:      "james.lee@corp.com",
			Title:      "Sales Director",
			Department: "Sales",
			ManagerID:  "emp-013",
			StartDate:  "2018-05-20",
			Location:   "Austin",
		},
		{
			ID:         "emp-005",
			Name:       "Emma Wilson",
			Email:      "emma.wilson@corp.com",
			Title:      "HR Specialist",
			Department: "Human Resources",
			ManagerID:  "emp-012",
			StartDate:  "2022-02-01",
			Location:   "Chicago",
		},
		{
			ID:         "emp-010",
			Name:       "David Park",
			Email:      "david.park@corp.com",
			Title:      "VP Engineering",
			Department: "Engineering",
			StartDate:  "2017-03-01",
			Location:   "San Francisco",
		},
		{
			ID:         "emp-011",
			Name:       "Lisa Martinez",
			Email:      "lisa.martinez@corp.com",
			Title:      "VP Product",
			Department: "Product",
			StartDate:  "2018-09-15",
			Location:   "New York",
		},
		{
			ID:         "emp-012",
			Name:       "Robert Taylor",
			Email:      "robert.taylor@corp.com",
			Title:      "VP Human Resources",
			Department: "Human Resources",
			StartDate:  "2019-06-01",
			Location:   "Chicago",
		},
		{
			ID:         "emp-013",
			Name:       "Jennifer Adams",
			Email:      "jennifer.adams@corp.com",
			Title:      "VP Sales",
			Department: "Sales",
			StartDate:  "2017-11-10",
			Location:   "Austin",
		},
		{
			ID:         "emp-014",
			Name:       "Michael Brown",
			Email:      "michael.brown@corp.com",
			Title:      "Junior Engineer",
			Department: "Engineering",
			ManagerID:  "emp-010",
			StartDate:  "2023-01-15",
			Location:   "Seattle",
		},
	}

	for _, emp := range employees {
		s.employees[emp.ID] = emp
	}

	// Salaries
	salaries := []*Salary{
		{EmployeeID: "emp-001", Base: 185000, Bonus: 25000, Equity: 50000},
		{EmployeeID: "emp-002", Base: 165000, Bonus: 20000, Equity: 40000},
		{EmployeeID: "emp-003", Base: 205000, Bonus: 30000, Equity: 60000},
		{EmployeeID: "emp-004", Base: 155000, Bonus: 50000, Equity: 30000},
		{EmployeeID: "emp-005", Base: 95000, Bonus: 10000, Equity: 15000},
		{EmployeeID: "emp-010", Base: 285000, Bonus: 75000, Equity: 150000},
		{EmployeeID: "emp-011", Base: 275000, Bonus: 70000, Equity: 140000},
		{EmployeeID: "emp-012", Base: 245000, Bonus: 60000, Equity: 120000},
		{EmployeeID: "emp-013", Base: 265000, Bonus: 100000, Equity: 130000},
		{EmployeeID: "emp-014", Base: 125000, Bonus: 10000, Equity: 25000},
	}

	for _, sal := range salaries {
		s.salaries[sal.EmployeeID] = sal
	}
}

// GetEmployee retrieves an employee by ID
func (s *Store) GetEmployee(id string) (*Employee, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	emp, ok := s.employees[id]
	if !ok {
		return nil, fmt.Errorf("employee not found: %s", id)
	}
	return emp, nil
}

// UpdateEmployee updates an employee record
func (s *Store) UpdateEmployee(emp *Employee) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, ok := s.employees[emp.ID]; !ok {
		return fmt.Errorf("employee not found: %s", emp.ID)
	}
	s.employees[emp.ID] = emp
	return nil
}

// ListEmployees returns all employees
func (s *Store) ListEmployees() []*Employee {
	s.mu.RLock()
	defer s.mu.RUnlock()

	emps := make([]*Employee, 0, len(s.employees))
	for _, emp := range s.employees {
		emps = append(emps, emp)
	}
	return emps
}

// ListDepartments returns all departments
func (s *Store) ListDepartments() []*Department {
	s.mu.RLock()
	defer s.mu.RUnlock()

	depts := make([]*Department, 0, len(s.departments))
	for _, dept := range s.departments {
		depts = append(depts, dept)
	}
	return depts
}

// GetSalary retrieves salary information for an employee
func (s *Store) GetSalary(employeeID string) (*Salary, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	sal, ok := s.salaries[employeeID]
	if !ok {
		return nil, fmt.Errorf("salary not found for employee: %s", employeeID)
	}
	return sal, nil
}

// UpdateSalary updates salary information
func (s *Store) UpdateSalary(sal *Salary) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if _, ok := s.salaries[sal.EmployeeID]; !ok {
		return fmt.Errorf("salary not found for employee: %s", sal.EmployeeID)
	}
	s.salaries[sal.EmployeeID] = sal
	return nil
}

// GetOrgChart returns organizational structure
func (s *Store) GetOrgChart() map[string]interface{} {
	s.mu.RLock()
	defer s.mu.RUnlock()

	// Build a simple org chart structure
	orgChart := make(map[string]interface{})
	orgChart["departments"] = s.departments

	// Group employees by department
	empByDept := make(map[string][]*Employee)
	for _, emp := range s.employees {
		empByDept[emp.Department] = append(empByDept[emp.Department], emp)
	}
	orgChart["employees_by_department"] = empByDept

	return orgChart
}
