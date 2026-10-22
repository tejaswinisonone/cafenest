# CaféNest — Cafe Management and Online Ordering System

> **College DBMS Lab Demonstration Project**  
> **Team Members:** Om Watane, Ambika Shelke, Tejaswani, and team member  
> **Mandatory Technology Stack:** HTML, CSS, Vanilla JavaScript, Python (Flask), MySQL  
> **UI/UX Design Reference:** Designed in **Google Stitch** using the *Artisanal Warmth* design system (`assets/ad3006cb6fad414992850a6363ab6469`)

---

## ☕ Project Overview
**CaféNest** is a full-stack cafe management and online ordering system that combines customer-facing table/takeaway ordering with an administrative operations portal. Built with strict adherence to project constraints:
- **Frontend:** Pure Semantic HTML5, CSS3, and Vanilla JavaScript (ES6+ with Fetch API). **Zero prohibited libraries** (No React, Vue, Angular, TypeScript, or Node.js).
- **Backend:** Python (Flask modular blueprints) handling input validation, transactions, session cookies, and business logic.
- **Database:** Permanent relational **MySQL database (`cafenest_db`) with 12 core normalized tables**.

---

## 🎨 UI/UX Design System (Google Stitch)
The interface was established in **Google Stitch** (Project ID: `3494447285558720606`) using the **Artisanal Warmth** aesthetic:
- **Deep Roast Espresso (`#2C1E16`)**: Anchor for headers, high-contrast actions, and brand elements.
- **Roasted Amber (`#D97736`)**: Focal calls-to-action, active status indicators, and button glows.
- **Sage Green (`#4A5D4E`)**: Vegetarian/botanical tags and positive availability states.
- **Milk Froth Canvas (`#FEF8F4`)**: Soft, creamy background surfaces that eliminate sterile whites.
- **Typography**: `Playfair Display` for editorial serif headers paired with `Plus Jakarta Sans` for clean UI forms, pricing, and badges.

---

## 🗄️ Database Architecture (12 Core Tables)
The relational schema is defined in `database/schema.sql` and populated with rich demonstration records in `database/seed.sql`:
1. `customers`: Customer profiles, contact details, and loyalty points balance.
2. `categories`: 6 menu categories (Hot Brews, Cold Brews, Teas, Bakery, Sandwiches, Desserts).
3. `menu`: 15 artisan food and beverage items with INR pricing, images, veg flags, and availability.
4. `cafe_tables`: 12 designated tables across Window Bay, Main Lounge, Garden Patio, and Mezzanine.
5. `orders`: Order header records with unique references (e.g. `NEST-XXXXX`), status, and tax amounts.
6. `order_details`: Line items linked to orders with trusted unit prices.
7. `payments`: Demonstration payments with simulated UPI QR and Cash at Counter options.
8. `staff`: Staff roster with role-based access (`Admin`, `Cashier`, `Barista`, `Waitstaff`).
9. `suppliers`: Coffee roasters, organic dairy, and flour mill vendor records.
10. `inventory`: Stock items with low-stock warnings when `quantity <= reorder_level`.
11. `stock_movements`: Audited additions and deductions with structured reasons (Restock, Daily Prep Usage, Spoilage).
12. `menu_price_audit`: Automatic audit trail logging every price modification, prior price, new price, staff ID, and timestamp.

---

## 🚀 Quick Setup & Run Instructions

### 1. Prerequisites
- Python 3.10+
- MySQL Server (Service running on port 3306)
- Python packages: `flask`, `flask-cors`, `pymysql`, `cryptography`

### 2. Initialize Database
Execute the database initialization script to build `cafenest_db` and load seed data:
```bash
python database/init_db.py
```

### 3. Start the Application Server
Run the Python backend:
```bash
python backend/app.py
```
Open your browser and navigate to:
```
http://127.0.0.1:5000/
```

### 4. Run Automated Test Suite
To verify all APIs, transaction validation, and business rules:
```bash
python -m unittest tests/test_all.py
```

---

## 🔑 Demonstration Credentials

| User Role | Email | Password | Access Area |
| :--- | :--- | :--- | :--- |
| **Lead Administrator** | `admin@cafenest.com` | `admin123` | Full Operations Portal (`/frontend/administrator/index.html`) |
| **Head Barista / Staff**| `tejaswani@cafenest.com`| `admin123` | Operations Portal (Kitchen & Inventory) |
| **Customer Patron** | `aarav@gmail.com` | `customer123` | Customer Ordering & Profile (`/frontend/customer/profile.html`) |
| **Guest Patron** | *None required* | *None required* | Direct Menu & Dine-In Ordering |

---

## 📂 Project Directory Structure
```
cafeNest_project/
├── index.html                           # Customer Homepage & Brand Experience
├── README.md                            # Complete setup and system documentation
├── backend/
│   ├── app.py                           # Central Flask application entry point
│   ├── config/
│   │   └── db_config.py                 # MySQL database connection factory
│   ├── middleware/
│   │   └── auth_middleware.py           # Role authorization & SHA-256 hashing
│   └── modules/
│       ├── auth.py                      # Authentication & Profile management
│       ├── menu.py                      # Menu CRUD & Price change audit logging
│       ├── orders.py                    # Transactional ordering & business rules
│       ├── payments.py                  # Demonstration simulated payment flow
│       ├── tables.py                    # Cafe table occupancy management
│       ├── inventory.py                 # Stock & supplier movements
│       ├── staff.py                     # Employee management & role controls
│       └── reports.py                   # Dashboard KPI metrics & sales reports
├── database/
│   ├── schema.sql                       # 12 core relational tables DDL
│   ├── seed.sql                         # Demonstration data DML
│   └── init_db.py                       # Automated database builder
├── frontend/
│   ├── assets/
│   │   ├── css/style.css                # Artisanal Warmth design system CSS
│   │   └── js/
│   │       ├── app.js                   # Cart & global application state
│   │       └── admin.js                 # Operations portal interactive logic
│   ├── customer/
│   │   ├── menu.html                    # Menu with live search & dietary filter
│   │   ├── cart.html                    # Basket & Dine-in table selector
│   │   ├── payment.html                 # Demonstration simulated UPI & cash
│   │   ├── tracking.html                # 5-step live kitchen status tracker
│   │   └── profile.html                 # Customer accounts & loyalty points
│   └── administrator/
│       └── index.html                   # Central operations dashboard
├── docs/
│   ├── PRD.md                           # Product Requirements Document
│   ├── TRD.md                           # Technical Requirements Document
│   └── database-design.md               # Schema & ER diagram documentation
└── tests/
    └── test_all.py                      # Automated test suite
```
