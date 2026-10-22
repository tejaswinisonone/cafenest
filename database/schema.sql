-- ==============================================================================
-- CaféNest — Cafe Management & Online Ordering System
-- Database Schema (12 Core Relational Tables)
-- Engine: MySQL (InnoDB)
-- ==============================================================================

CREATE DATABASE IF NOT EXISTS `cafenest_db` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `cafenest_db`;

-- Drop existing tables in reverse dependency order if needed for clean re-runs
DROP TABLE IF EXISTS `menu_price_audit`;
DROP TABLE IF EXISTS `stock_movements`;
DROP TABLE IF EXISTS `inventory`;
DROP TABLE IF EXISTS `suppliers`;
DROP TABLE IF EXISTS `payments`;
DROP TABLE IF EXISTS `order_details`;
DROP TABLE IF EXISTS `orders`;
DROP TABLE IF EXISTS `cafe_tables`;
DROP TABLE IF EXISTS `menu`;
DROP TABLE IF EXISTS `categories`;
DROP TABLE IF EXISTS `staff`;
DROP TABLE IF EXISTS `customers`;

-- ------------------------------------------------------------------------------
-- 1. Customers Table
-- ------------------------------------------------------------------------------
CREATE TABLE `customers` (
    `customer_id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `email` VARCHAR(150) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `phone` VARCHAR(20) DEFAULT NULL,
    `address` TEXT DEFAULT NULL,
    `loyalty_points` INT NOT NULL DEFAULT 50,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 2. Menu Categories Table
-- ------------------------------------------------------------------------------
CREATE TABLE `categories` (
    `category_id` INT AUTO_INCREMENT PRIMARY KEY,
    `category_name` VARCHAR(50) NOT NULL UNIQUE,
    `description` VARCHAR(255) DEFAULT NULL,
    `display_order` INT NOT NULL DEFAULT 0,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 3. Menu Items Table
-- ------------------------------------------------------------------------------
CREATE TABLE `menu` (
    `menu_id` INT AUTO_INCREMENT PRIMARY KEY,
    `category_id` INT NOT NULL,
    `name` VARCHAR(100) NOT NULL,
    `description` TEXT DEFAULT NULL,
    `price` DECIMAL(10, 2) NOT NULL,
    `image_url` VARCHAR(500) DEFAULT NULL,
    `is_veg` BOOLEAN NOT NULL DEFAULT TRUE,
    `is_available` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_menu_category` FOREIGN KEY (`category_id`) 
        REFERENCES `categories` (`category_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 4. Cafe Tables Table (Dine-in management)
-- ------------------------------------------------------------------------------
CREATE TABLE `cafe_tables` (
    `table_id` INT AUTO_INCREMENT PRIMARY KEY,
    `table_number` VARCHAR(20) NOT NULL UNIQUE,
    `seating_capacity` INT NOT NULL DEFAULT 2,
    `location_area` VARCHAR(50) NOT NULL DEFAULT 'Main Dining Hall',
    `status` ENUM('Available', 'Occupied', 'Reserved') NOT NULL DEFAULT 'Available',
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 5. Orders Table (Header)
-- ------------------------------------------------------------------------------
CREATE TABLE `orders` (
    `order_id` INT AUTO_INCREMENT PRIMARY KEY,
    `order_reference` VARCHAR(50) NOT NULL UNIQUE,
    `customer_id` INT DEFAULT NULL,
    `table_id` INT DEFAULT NULL,
    `order_type` ENUM('Dine-In', 'Takeaway') NOT NULL DEFAULT 'Dine-In',
    `status` ENUM('Pending', 'Confirmed', 'Preparing', 'Ready', 'Completed', 'Cancelled') NOT NULL DEFAULT 'Pending',
    `subtotal` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `tax_amount` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `total_amount` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `special_instructions` TEXT DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_orders_customer` FOREIGN KEY (`customer_id`) 
        REFERENCES `customers` (`customer_id`) ON DELETE SET NULL,
    CONSTRAINT `fk_orders_table` FOREIGN KEY (`table_id`) 
        REFERENCES `cafe_tables` (`table_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 6. Order Details Table (Line Items)
-- ------------------------------------------------------------------------------
CREATE TABLE `order_details` (
    `order_detail_id` INT AUTO_INCREMENT PRIMARY KEY,
    `order_id` INT NOT NULL,
    `menu_id` INT NOT NULL,
    `quantity` INT NOT NULL,
    `unit_price` DECIMAL(10, 2) NOT NULL,
    `subtotal` DECIMAL(10, 2) NOT NULL,
    CONSTRAINT `fk_details_order` FOREIGN KEY (`order_id`) 
        REFERENCES `orders` (`order_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_details_menu` FOREIGN KEY (`menu_id`) 
        REFERENCES `menu` (`menu_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 7. Payments Table (Simulated & Demonstration Transactions)
-- ------------------------------------------------------------------------------
CREATE TABLE `payments` (
    `payment_id` INT AUTO_INCREMENT PRIMARY KEY,
    `order_id` INT NOT NULL,
    `amount` DECIMAL(10, 2) NOT NULL,
    `method` ENUM('Cash', 'Simulated_UPI') NOT NULL,
    `status` ENUM('Completed', 'Pending', 'Failed') NOT NULL DEFAULT 'Completed',
    `transaction_ref` VARCHAR(100) NOT NULL,
    `is_simulated` BOOLEAN NOT NULL DEFAULT TRUE,
    `paid_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_payments_order` FOREIGN KEY (`order_id`) 
        REFERENCES `orders` (`order_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 8. Staff Table (Employees & Administrative users)
-- ------------------------------------------------------------------------------
CREATE TABLE `staff` (
    `staff_id` INT AUTO_INCREMENT PRIMARY KEY,
    `name` VARCHAR(100) NOT NULL,
    `email` VARCHAR(150) NOT NULL UNIQUE,
    `password_hash` VARCHAR(255) NOT NULL,
    `phone` VARCHAR(20) DEFAULT NULL,
    `role` ENUM('Admin', 'Cashier', 'Barista', 'Waitstaff') NOT NULL DEFAULT 'Admin',
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 9. Suppliers Table
-- ------------------------------------------------------------------------------
CREATE TABLE `suppliers` (
    `supplier_id` INT AUTO_INCREMENT PRIMARY KEY,
    `supplier_name` VARCHAR(100) NOT NULL,
    `contact_name` VARCHAR(100) DEFAULT NULL,
    `phone` VARCHAR(20) DEFAULT NULL,
    `email` VARCHAR(150) DEFAULT NULL,
    `address` TEXT DEFAULT NULL,
    `supplied_items` VARCHAR(255) DEFAULT NULL,
    `is_active` BOOLEAN NOT NULL DEFAULT TRUE,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 10. Inventory Table
-- ------------------------------------------------------------------------------
CREATE TABLE `inventory` (
    `inventory_id` INT AUTO_INCREMENT PRIMARY KEY,
    `supplier_id` INT DEFAULT NULL,
    `item_name` VARCHAR(100) NOT NULL,
    `quantity` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `unit` VARCHAR(20) NOT NULL,
    `reorder_level` DECIMAL(10, 2) NOT NULL DEFAULT 10.00,
    `cost_per_unit` DECIMAL(10, 2) NOT NULL DEFAULT 0.00,
    `updated_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_inventory_supplier` FOREIGN KEY (`supplier_id`) 
        REFERENCES `suppliers` (`supplier_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 11. Stock Movements Table
-- ------------------------------------------------------------------------------
CREATE TABLE `stock_movements` (
    `movement_id` INT AUTO_INCREMENT PRIMARY KEY,
    `inventory_id` INT NOT NULL,
    `quantity_change` DECIMAL(10, 2) NOT NULL,
    `reason` ENUM('Restock', 'Waste / Spoilage', 'Daily Prep Usage', 'Inventory Audit Adjustment', 'Returned') NOT NULL,
    `notes` VARCHAR(255) DEFAULT NULL,
    `staff_id` INT DEFAULT NULL,
    `created_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_movement_inventory` FOREIGN KEY (`inventory_id`) 
        REFERENCES `inventory` (`inventory_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_movement_staff` FOREIGN KEY (`staff_id`) 
        REFERENCES `staff` (`staff_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ------------------------------------------------------------------------------
-- 12. Menu Price Audit Table
-- ------------------------------------------------------------------------------
CREATE TABLE `menu_price_audit` (
    `audit_id` INT AUTO_INCREMENT PRIMARY KEY,
    `menu_id` INT NOT NULL,
    `old_price` DECIMAL(10, 2) NOT NULL,
    `new_price` DECIMAL(10, 2) NOT NULL,
    `changed_by_staff_id` INT DEFAULT NULL,
    `changed_at` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT `fk_audit_menu` FOREIGN KEY (`menu_id`) 
        REFERENCES `menu` (`menu_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_audit_staff` FOREIGN KEY (`changed_by_staff_id`) 
        REFERENCES `staff` (`staff_id`) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
