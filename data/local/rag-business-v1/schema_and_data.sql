PRAGMA foreign_keys=ON;
BEGIN;
CREATE TABLE customers(id INTEGER PRIMARY KEY,name TEXT NOT NULL);
CREATE TABLE orders(id INTEGER PRIMARY KEY,customer_id INTEGER REFERENCES customers(id),ordered_at TEXT NOT NULL,amount_cents INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('paid','pending','cancelled')));
CREATE TABLE refunds(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),amount_cents INTEGER NOT NULL);
CREATE TABLE products(id INTEGER PRIMARY KEY,name TEXT NOT NULL);
CREATE TABLE stock_movements(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),quantity_delta INTEGER NOT NULL,occurred_at TEXT NOT NULL);
CREATE TABLE reservations(id INTEGER PRIMARY KEY,product_id INTEGER NOT NULL REFERENCES products(id),quantity INTEGER NOT NULL CHECK(quantity>0),status TEXT NOT NULL CHECK(status IN ('active','released')));
CREATE TABLE shipments(id INTEGER PRIMARY KEY,order_id INTEGER NOT NULL REFERENCES orders(id),promised_at TEXT NOT NULL,delivered_at TEXT);
CREATE TABLE tickets(id INTEGER PRIMARY KEY,created_at TEXT NOT NULL);
CREATE TABLE ticket_messages(id INTEGER PRIMARY KEY,ticket_id INTEGER NOT NULL REFERENCES tickets(id),author_type TEXT NOT NULL CHECK(author_type IN ('staff','bot','customer')),sent_at TEXT NOT NULL);
CREATE TABLE ticket_events(id INTEGER PRIMARY KEY,ticket_id INTEGER NOT NULL REFERENCES tickets(id),sequence_no INTEGER NOT NULL,event_type TEXT NOT NULL CHECK(event_type IN ('open','closed')),UNIQUE(ticket_id,sequence_no));
CREATE TABLE invoices(id INTEGER PRIMARY KEY,customer_id INTEGER NOT NULL REFERENCES customers(id),billed_cents INTEGER NOT NULL);
CREATE TABLE payments(id INTEGER PRIMARY KEY,invoice_id INTEGER NOT NULL REFERENCES invoices(id),amount_cents INTEGER NOT NULL,status TEXT NOT NULL CHECK(status IN ('settled','pending')));
INSERT INTO customers VALUES(1,'Synthetic Customer A'),(2,'Synthetic Customer B'),(3,'Synthetic Customer C'),(4,'Synthetic Customer D');
INSERT INTO orders VALUES
(1,1,'2026-01-31T23:59:59Z',10000,'paid'),
(2,1,'2026-02-01T00:00:00Z',20000,'paid'),
(3,2,'2026-02-14T12:00:00Z',8000,'paid'),
(4,NULL,'2026-02-15T10:00:00Z',3000,'paid'),
(5,3,'2026-02-18T10:00:00Z',6000,'pending'),
(6,3,'2026-02-19T10:00:00Z',9000,'cancelled'),
(7,2,'2026-02-28T23:59:59Z',5000,'paid'),
(8,1,'2026-03-01T00:00:00Z',11000,'paid');
INSERT INTO refunds VALUES(1,2,1000),(2,2,2000),(3,3,500);
INSERT INTO products VALUES(1,'Synthetic Product A'),(2,'Synthetic Product B'),(3,'Synthetic Product C'),(4,'Synthetic Product D');
INSERT INTO stock_movements VALUES
(1,1,100,'2026-02-01T00:00:00Z'),(2,1,-20,'2026-02-02T00:00:00Z'),
(3,1,10,'2026-02-03T00:00:00Z'),(4,2,50,'2026-02-01T00:00:00Z'),
(5,2,-5,'2026-02-02T00:00:00Z'),(6,4,20,'2026-02-01T00:00:00Z');
INSERT INTO reservations VALUES(1,1,10,'active'),(2,1,5,'active'),(3,1,30,'released'),(4,2,5,'released'),(5,4,20,'active');
INSERT INTO shipments VALUES
(1,1,'2026-02-03T12:00:00Z','2026-02-03T13:00:00Z'),
(2,2,'2026-02-04T12:00:00Z','2026-02-04T12:00:00Z'),
(3,3,'2026-02-15T12:00:00Z','2026-02-15T11:00:00Z'),
(4,4,'2026-02-16T12:00:00Z',NULL);
INSERT INTO tickets VALUES(1,'2026-02-01T10:00:00Z'),(2,'2026-02-01T11:00:00Z'),(3,'2026-02-02T09:00:00Z');
INSERT INTO ticket_messages VALUES
(1,1,'bot','2026-02-01T10:00:01Z'),(2,1,'customer','2026-02-01T10:02:00Z'),
(3,1,'staff','2026-02-01T10:10:00Z'),(4,1,'staff','2026-02-01T10:20:00Z'),
(5,2,'bot','2026-02-01T11:00:01Z'),(6,2,'customer','2026-02-01T11:05:00Z'),
(7,3,'staff','2026-02-02T09:30:00Z');
INSERT INTO ticket_events VALUES
(1,1,1,'open'),(2,1,2,'closed'),(3,1,3,'open'),(4,1,4,'closed'),(5,1,5,'open'),
(6,2,1,'open'),(7,3,1,'open'),(8,3,2,'closed');
INSERT INTO invoices VALUES(1,1,10000),(2,1,5000),(3,2,3000),(4,3,4000);
INSERT INTO payments VALUES(1,1,8000,'settled'),(2,1,4000,'settled'),(3,2,1000,'settled'),(4,2,2000,'pending'),(5,4,4000,'settled');
COMMIT;
