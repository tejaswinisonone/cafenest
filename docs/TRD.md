# TECHNICAL REQUIREMENTS DOCUMENT (TRD)

## CaféNest — Technical Architecture & Implementation
**Document Version:** 1.0  
**Stack:** HTML5, CSS3, Vanilla JavaScript (ES6+), Python (Flask), MySQL (InnoDB)  

---

### 1. Architectural Overview
CaféNest employs a clean 3-tier architecture:
- **Presentation Layer**: Pure HTML5, custom CSS3 tokens from the Google Stitch *Artisanal Warmth* design system, and Vanilla JavaScript utilizing Fetch API.
- **Application Layer**: Python Flask application structured into modular blueprints (`auth`, `menu`, `orders`, `payments`, `tables`, `inventory`, `staff`, `reports`). Server-side validation recalculates all financial totals and verifies availability in real-time.
- **Data Layer**: MySQL database running on InnoDB with foreign key constraints, unique rules, indexes, and ACID transactions.

---

### 2. API Endpoints Map
| Endpoint | Method | Role | Description |
| :--- | :--- | :--- | :--- |
| `/api/auth/register` | POST | Public | Register customer account |
| `/api/auth/login` | POST | Public | Authenticate customer or staff |
| `/api/auth/logout` | POST | Authenticated | Terminate session |
| `/api/auth/me` | GET | Public | Session verification & profile details |
| `/api/auth/profile` | PUT | Customer | Update customer contact & delivery address |
| `/api/menu` | GET | Public | Filtered menu catalog |
| `/api/menu/categories` | GET | Public | Categories with active counts |
| `/api/menu/save` | POST | Staff | Add/update item & log price audits |
| `/api/menu/toggle-availability`| POST | Staff | Toggle availability status |
| `/api/orders` | POST | Public/Customer | Validated transactional order placement |
| `/api/orders` | GET | Customer/Staff | List orders (role scoped) |
| `/api/orders/<id>` | GET | Customer/Staff | Full order line items & payment |
| `/api/orders/track/<ref>` | GET | Public | Quick tracking by reference code |
| `/api/orders/update-status` | POST | Staff | Advance kitchen status workflow |
| `/api/payments/demo` | POST | Public | Simulated UPI / Cash recording |
| `/api/tables` | GET | Public | List cafe tables & occupancy |
| `/api/tables/status` | POST | Staff | Update table status |
| `/api/inventory` | GET | Staff | Stock items with low-stock alerts |
| `/api/inventory/movement` | POST | Staff | Record additions/deductions |
| `/api/inventory/suppliers` | GET/POST | Staff | Supplier directory |
| `/api/staff` | GET/POST | Admin | Staff roster & credentials |
| `/api/admin/dashboard` | GET | Staff | Real-time KPI figures & live queue |
| `/api/admin/sales` | GET | Staff | Sales analytics & trends |

---

### 3. Business & Security Rules
- All incoming quantities must be positive integers ($> 0$).
- Item availability is checked against current MySQL records prior to insertion.
- Prices submitted by the client are never trusted; subtotals and 5% GST are calculated by Python using authoritative MySQL price fields.
- Password hashes use SHA-256 with secure comparison.
- When an order linked to a table is completed or cancelled, the table is automatically released back to `Available`.
- Price adjustments trigger automatic insert into `menu_price_audit`.
