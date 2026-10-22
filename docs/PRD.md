# PRODUCT REQUIREMENTS DOCUMENT (PRD)

## CaféNest — Cafe Management and Online Ordering System
**Document Version:** 1.0  
**Project Type:** College DBMS Lab Project  
**Team Members:** Om Watane, Ambika Shelke, Tejaswani, and team member  

### Technology Stack
- **Frontend:** HTML, CSS, JavaScript (Vanilla JavaScript only)
- **Backend:** Python (Flask modular architecture)
- **Database:** SQL (MySQL relational database)
- **Design System:** Google Stitch — Artisanal Warmth

---

### 1. Executive Summary
CaféNest brings customer ordering and day-to-day cafe management into a unified system. Customers explore artisanal roasts, add items to a basket, choose dine-in table or takeaway service, confirm simulated payments, and track orders in real time. Administrators and cafe staff maintain menus, track inventory levels, monitor cafe tables, manage staff records, and view operational analytics.

### 2. Functional Areas Implemented
1. **Customer Accounts & Profiles**: Secure sign-up, sign-in with SHA-256 password hashing, profile updates, and loyalty points.
2. **Menu & Food Item Catalog**: Filterable catalog by category, dietary preference (Veg / Non-Veg), search, and live availability toggling.
3. **Cart & Table Checkout**: Client and server validated cart quantities, trusted price recalculation, dine-in table assignment, and special barista instructions.
4. **Orders & Status Progression**: Database transactional placement into header (`orders`) and line items (`order_details`), 5-stage milestone tracking (`Pending` ➔ `Confirmed` ➔ `Preparing` ➔ `Ready` ➔ `Completed`).
5. **Simulated Payments**: Demonstration payments supporting simulated UPI (with mock QR code & UPI ID) and Cash at Counter.
6. **Cafe Table Management**: 12 designated cafe tables with live states (`Available`, `Occupied`, `Reserved`).
7. **Inventory & Suppliers**: Stock quantities, low-stock threshold alerts, supplier directory, and atomic stock movements with audited reasons.
8. **Staff Roles**: Role-based access control (`Admin`, `Cashier`, `Barista`, `Waitstaff`).
9. **Menu Price Auditing**: Automatic logging of old price, new price, staff ID, and timestamp into `menu_price_audit`.
10. **Administrative Reports**: Real-time KPI summaries, category revenue breakdowns, daily sales trends, and top selling items.
