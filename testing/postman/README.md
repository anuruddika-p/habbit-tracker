# Testing Documentation — Habit Tracking System

This folder contains all test documentation for the Habit Tracking System final year project, including API test cases, a Postman collection, and test result screenshots.

---

## Test Summary

| Category | Test Cases | Status |
|----------|-----------|--------|
| User Authentication | 6 | ✅ All Passing |
| Habit Management | 2 | ✅ All Passing |
| Habit Logs | 2 | ✅ All Passing |
| Recommendations | 1 | ✅ All Passing |
| Feedback | 2 | ✅ All Passing |
| **Total** | **13** | **✅ 13/13 Passing** |

---

## Folder Contents

```
testing/postman
├── README.md                                         — This file
├── collection/HabitTrackingSystem_API_Tests.postman_collection.json  — Postman collection
├── test_cases.docs                                   — Full test case documentation
└── screenshots/                                      — Test result screenshots
└── global/
```

---

## Test Types Covered

- **Functional Testing** — verifying each API endpoint returns correct responses
- **Negative Testing** — verifying the API correctly rejects invalid or incomplete input
- **Security Testing** — JWT token validation, unauthorised access blocked, cross-user data isolation
- **Business Logic Testing** — recommendation deactivation on negative feedback, missed habit notifications
- **Integration Testing** — frontend to backend end-to-end user journey validation

---

## How to Import and Run the Postman Collection

1. Open Postman
2. Click **Import**
3. Select `HabitTrackingSystem_API_Tests.postman_collection.json`
4. Set the `base_url` collection variable to `http://localhost:5000`
5. Run requests in order — TC-003 login saves the JWT token automatically for all subsequent requests
6. Run the full collection using **Collection Runner** to see all 13 results at once

---

## Key Testing Highlights

**Security test — unauthorised access (TC-006)**
Verifies that accessing user profile without a JWT token returns 401 Unauthorized. Confirms the API does not expose user data to unauthenticated requests.

**Security test — cross-user data isolation (TC-010)**
Verifies that a logged-in user cannot write habit log entries to another user's habit. Returns 403 Forbidden. Confirms user data is properly isolated.

**Business logic test — negative feedback deactivation (TC-013)**
Verifies that submitting a feedback rating below 3 automatically deactivates the recommendation. Confirms the rule-based engine responds correctly to user feedback.

---

## Test Case Document

The `test_cases.docs` file contains the full test case table including:
- Test case ID and description
- API endpoint and request body
- Expected result
- Actual result
- Pass/Fail status
