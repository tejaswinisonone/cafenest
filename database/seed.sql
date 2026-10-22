-- ==============================================================================
-- CaféNest — Seed Demonstration Data
-- ==============================================================================

USE `cafenest_db`;

-- 1. Insert Categories
INSERT INTO `categories` (`category_id`, `category_name`, `description`, `display_order`, `is_active`) VALUES
(1, 'Espresso & Hot Brews', 'Hand-pulled espresso shots and slow drip roasts', 1, TRUE),
(2, 'Cold Brews & Iced Coffee', 'Steeped for 18 hours with single-origin beans', 2, TRUE),
(3, 'Artisan Teas & Infusions', 'Whole-leaf botanicals and herbal infusions', 3, TRUE),
(4, 'Bakery & Pastries', 'Freshly baked every morning with French butter', 4, TRUE),
(5, 'Gourmet Sandwiches', 'Toasted rustic sourdough with house-made dressings', 5, TRUE),
(6, 'Desserts & Sweet Bites', 'Decadent chocolate fondants and craft cheesecakes', 6, TRUE);

-- 2. Insert Menu Items
INSERT INTO `menu` (`menu_id`, `category_id`, `name`, `description`, `price`, `image_url`, `is_veg`, `is_available`) VALUES
-- Espresso
(1, 1, 'Velvet Cortado', 'Equal parts rich espresso and silky textured milk with dark cacao notes', 190.00, 'https://images.unsplash.com/photo-1534778101976-62847782c213?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
(2, 1, 'Artisan Flat White', 'Double ristretto poured with velvety micro-foam latte art', 210.00, 'https://images.unsplash.com/photo-1577968897966-3d4325b36b61?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
(3, 1, 'Single-Origin Pour Over', 'Ethiopian Yirgacheffe with floral jasmine and wild berry tasting notes', 240.00, 'https://images.unsplash.com/photo-1514432324607-a09d9b4aefdd?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
(4, 1, 'Signature Spanish Latte', 'Rich espresso with condensed milk and warm Madagascar vanilla sprinkle', 230.00, 'https://images.unsplash.com/photo-1517701604599-bb29b565090c?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
-- Cold Brews
(5, 2, 'Nitro Cold Brew', 'Micro-nitrogen infused slow extraction with a thick Guinness-style crema head', 260.00, 'https://images.unsplash.com/photo-1517701550927-30cf4ba1dba5?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
(6, 2, 'Tonic Espresso Spritzer', 'Fever-Tree artisanal tonic, freshly pulled double shot, and candied orange peel', 250.00, 'https://images.unsplash.com/photo-1461023058943-07fcbe16d735?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
(7, 2, 'Salted Caramel Cold Foam', '18-hour cold brew topped with aerated sea-salt caramel cream foam', 270.00, 'https://images.unsplash.com/photo-1582293041079-7814c2f12063?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
-- Teas
(8, 3, 'Kashmiri Kahwa Saffron Tea', 'Green tea leaves infused with hand-picked saffron, cardamom, and sliced almonds', 220.00, 'https://images.unsplash.com/photo-1576092768241-dec231879fc3?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
(9, 3, 'Japanese Ceremonial Matcha', 'Whisked Uji matcha with steamed organic oat milk and natural agave', 260.00, 'https://images.unsplash.com/photo-1536256263959-770b48d82b0a?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
-- Bakery
(10, 4, 'Almond Frangipane Croissant', 'Flaky 72-layer croissant stuffed with almond cream and roasted flakes', 180.00, 'https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
(11, 4, 'Cinnamon Brioche Swirl', 'Warm spiced Ceylon cinnamon bun glazed with Madagascar cream cheese', 170.00, 'https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
-- Sandwiches
(12, 5, 'Avocado Pesto Sourdough Tartine', 'Crushed Hass avocado, cherry tomatoes, bocconcini, and house basil walnut pesto', 320.00, 'https://images.unsplash.com/photo-1525351484163-7529414344d8?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
(13, 5, 'Smoked Chicken & Truffle Panini', 'Herb-roasted chicken breast, melted aged provolone, arugula, and truffle mayo', 360.00, 'https://images.unsplash.com/photo-1528735602780-2552fd46c7af?auto=format&fit=crop&w=600&q=80', FALSE, TRUE),
-- Desserts
(14, 6, 'Belgian Dark Chocolate Fondant', 'Molten 70% Callebaut chocolate lava cake served warm with espresso dust', 240.00, 'https://images.unsplash.com/photo-1606313564200-e75d5e30476c?auto=format&fit=crop&w=600&q=80', TRUE, TRUE),
(15, 6, 'Burnt Basque Cheesecake', 'Caramelized crust with a rich, molten cream cheese center', 280.00, 'https://images.unsplash.com/photo-1533134242443-d4fd215305ad?auto=format&fit=crop&w=600&q=80', TRUE, TRUE);

-- 3. Insert Cafe Tables
INSERT INTO `cafe_tables` (`table_id`, `table_number`, `seating_capacity`, `location_area`, `status`) VALUES
(1, 'Table 1', 2, 'Window Bay — Street View', 'Available'),
(2, 'Table 2', 2, 'Window Bay — Street View', 'Occupied'),
(3, 'Table 3', 4, 'Main Lounge Hearth', 'Available'),
(4, 'Table 4', 4, 'Main Lounge Hearth', 'Reserved'),
(5, 'Table 5', 2, 'Sanctuary Garden Patio', 'Available'),
(6, 'Table 6', 4, 'Sanctuary Garden Patio', 'Available'),
(7, 'Table 7', 6, 'Communal Study Bar', 'Occupied'),
(8, 'Table 8', 6, 'Communal Study Bar', 'Available'),
(9, 'Table 9', 2, 'Mezzanine Roastery View', 'Available'),
(10, 'Table 10', 4, 'Mezzanine Roastery View', 'Available'),
(11, 'Table 11', 8, 'Private Tasting Booth', 'Reserved'),
(12, 'Table 12', 4, 'Espresso Counter Bench', 'Available');

-- 4. Insert Staff (Default password: admin123 -> sha256: 240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9)
INSERT INTO `staff` (`staff_id`, `name`, `email`, `password_hash`, `phone`, `role`, `is_active`) VALUES
(1, 'Om Watane (Lead Admin)', 'admin@cafenest.com', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '+91 9876543210', 'Admin', TRUE),
(2, 'Ambika Shelke (Manager)', 'ambika@cafenest.com', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '+91 9876543211', 'Admin', TRUE),
(3, 'Tejaswani (Head Barista)', 'tejaswani@cafenest.com', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '+91 9876543212', 'Barista', TRUE),
(4, 'Rahul Verma (Cashier)', 'rahul@cafenest.com', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '+91 9876543213', 'Cashier', TRUE),
(5, 'Pooja Patil (Waitstaff)', 'pooja@cafenest.com', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '+91 9876543214', 'Waitstaff', TRUE);

-- 5. Insert Customers (Default password: customer123 -> sha256: e807f1fcf82d132f9bb018ca6738a19f)
-- Using sha256 for 'customer123': bc71d796796c944ad7b11eb11b590e80df96c561498b3c95a07204fa69cb5024
INSERT INTO `customers` (`customer_id`, `name`, `email`, `password_hash`, `phone`, `address`, `loyalty_points`) VALUES
(1, 'Aarav Sharma', 'aarav@gmail.com', 'b041c0aeb35bb0fa4aa668ca5a920b590196fdaf9a00eb852c9b7f4d123cc6d6', '+91 9123456780', 'Flat 402, Green Valley Apts, Pune', 120),
(2, 'Sneha Deshmukh', 'sneha@gmail.com', 'b041c0aeb35bb0fa4aa668ca5a920b590196fdaf9a00eb852c9b7f4d123cc6d6', '+91 9123456781', 'Lane 5, Koregaon Park, Pune', 85);

-- 6. Insert Suppliers
INSERT INTO `suppliers` (`supplier_id`, `supplier_name`, `contact_name`, `phone`, `email`, `address`, `supplied_items`) VALUES
(1, 'Blue Tokai Roasting Co.', 'Karan Berry', '+91 9820011223', 'wholesale@bluetokai.com', 'Estate 12, Chikmagalur, Karnataka', 'Specialty Arabica & Robusta Green Beans'),
(2, 'Artisan Dairy Farms', 'Vikas Shinde', '+91 9820044556', 'orders@artisandairy.in', 'Manchar, Pune Rural, Maharashtra', 'Organic Whole Milk, Sweet Cream, Butter'),
(3, 'French Flour & Yeast Mills', 'Marie Laurent', '+91 9820077889', 'supply@frenchmill.com', 'Andheri East, Mumbai', 'T55 Pastry Flour, Dry Active Sourdough Yeast'),
(4, 'Spice Route Botanicals', 'Deepak Nair', '+91 9820099001', 'info@spiceroute.org', 'Fort Cochin, Kerala', 'Kashmiri Saffron, Ceylon Cinnamon, Green Cardamom');

-- 7. Insert Inventory Items
INSERT INTO `inventory` (`inventory_id`, `supplier_id`, `item_name`, `quantity`, `unit`, `reorder_level`, `cost_per_unit`) VALUES
(1, 1, 'Ethiopian Yirgacheffe Beans', 24.50, 'kg', 10.00, 1100.00),
(2, 1, 'Monsooned Malabar Beans', 38.00, 'kg', 15.00, 850.00),
(3, 2, 'Farm Fresh Organic Milk', 55.00, 'litres', 20.00, 68.00),
(4, 2, 'Oat Milk Barista Edition', 8.00, 'litres', 12.00, 195.00), -- Low stock alert!
(5, 2, 'French Unsalted Butter', 4.50, 'kg', 8.00, 480.00), -- Low stock alert!
(6, 3, 'T55 French Pastry Flour', 45.00, 'kg', 20.00, 95.00),
(7, 4, 'Madagascar Vanilla Pods', 0.85, 'kg', 1.00, 8500.00), -- Low stock alert!
(8, 4, 'Ceylon Cinnamon Quills', 5.00, 'kg', 2.00, 1400.00);

-- 8. Insert Initial Stock Movements
INSERT INTO `stock_movements` (`movement_id`, `inventory_id`, `quantity_change`, `reason`, `notes`, `staff_id`) VALUES
(1, 1, 30.00, 'Restock', 'Monthly bean delivery batch #BT-902', 1),
(2, 1, -5.50, 'Daily Prep Usage', 'Ground for weekly batch cold brew', 3),
(3, 4, -4.00, 'Daily Prep Usage', 'Barista weekend usage', 3),
(4, 5, -3.50, 'Daily Prep Usage', 'Croissant morning laminated dough', 3);

-- 9. Insert Sample Orders
INSERT INTO `orders` (`order_id`, `order_reference`, `customer_id`, `table_id`, `order_type`, `status`, `subtotal`, `tax_amount`, `total_amount`, `special_instructions`, `created_at`) VALUES
(1, 'NEST-1001', 1, 2, 'Dine-In', 'Completed', 400.00, 20.00, 420.00, 'Extra hot flat white', DATE_SUB(NOW(), INTERVAL 2 HOUR)),
(2, 'NEST-1002', 2, 7, 'Dine-In', 'Preparing', 580.00, 29.00, 609.00, 'Warm the croissant please', DATE_SUB(NOW(), INTERVAL 25 MINUTE)),
(3, 'NEST-1003', 1, NULL, 'Takeaway', 'Ready', 260.00, 13.00, 273.00, 'Pack in insulated cup', DATE_SUB(NOW(), INTERVAL 12 MINUTE)),
(4, 'NEST-1004', 2, 4, 'Dine-In', 'Pending', 720.00, 36.00, 756.00, 'Less sugar in matcha', NOW());

-- 10. Insert Sample Order Details
INSERT INTO `order_details` (`order_id`, `menu_id`, `quantity`, `unit_price`, `subtotal`) VALUES
(1, 2, 1, 210.00, 210.00),
(1, 1, 1, 190.00, 190.00),
(2, 5, 1, 260.00, 260.00),
(2, 12, 1, 320.00, 320.00),
(3, 5, 1, 260.00, 260.00),
(4, 9, 2, 260.00, 520.00),
(4, 10, 1, 180.00, 180.00),
(4, 1, 1, 190.00, 190.00);

-- 11. Insert Simulated Payments
INSERT INTO `payments` (`payment_id`, `order_id`, `amount`, `method`, `status`, `transaction_ref`, `is_simulated`) VALUES
(1, 1, 420.00, 'Simulated_UPI', 'Completed', 'UPI-DEMO-98218731', TRUE),
(2, 2, 609.00, 'Cash', 'Completed', 'CASH-REC-1002', TRUE),
(3, 3, 273.00, 'Simulated_UPI', 'Completed', 'UPI-DEMO-44391201', TRUE),
(4, 4, 756.00, 'Simulated_UPI', 'Pending', 'UPI-PEND-88219034', TRUE);

-- 12. Insert Menu Price Audit initial trail
INSERT INTO `menu_price_audit` (`audit_id`, `menu_id`, `old_price`, `new_price`, `changed_by_staff_id`, `changed_at`) VALUES
(1, 1, 180.00, 190.00, 1, DATE_SUB(NOW(), INTERVAL 5 DAY)),
(2, 5, 250.00, 260.00, 1, DATE_SUB(NOW(), INTERVAL 3 DAY));
