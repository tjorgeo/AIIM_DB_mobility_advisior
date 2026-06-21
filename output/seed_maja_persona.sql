-- ====================================================================
-- BCG Platinion - Phase 1 Sandbox Database Setup
-- Persona Profile Deployment: Maja Hoffmann
-- Date: June 2026
-- ====================================================================

-- 1. CLEAN REBUILD PARADIGM
DROP TABLE IF EXISTS audit_log CASCADE;
DROP TABLE IF EXISTS recommendations CASCADE;
DROP TABLE IF EXISTS travel_history CASCADE;
DROP TABLE IF EXISTS subscriptions CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- 2. CREATE CORE SCHEMAS WITH CONSTRAINTS
CREATE TABLE users (
    id UUID PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    age INT,
    city VARCHAR(100),
    occupation VARCHAR(100),
    cost_priority INT CHECK (cost_priority BETWEEN 0 AND 100),
    co2_priority INT CHECK (co2_priority BETWEEN 0 AND 100),
    flexibility_priority INT CHECK (flexibility_priority BETWEEN 0 AND 100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE subscriptions (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    service VARCHAR(100) NOT NULL,
    monthly_cost_eur NUMERIC(10, 2) NOT NULL,
    status VARCHAR(50) DEFAULT 'active',
    renewal_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE travel_history (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    trip_date DATE NOT NULL,
    origin VARCHAR(150),
    destination VARCHAR(150),
    mode VARCHAR(50) NOT NULL, -- train_regional, train_long_distance, car_sharing
    distance_km NUMERIC(10, 2),
    cost_eur_base NUMERIC(10, 2), -- Original base single-ticket price before sub calculation
    co2_kg NUMERIC(10, 2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Index zur Performance-Optimierung der Agenten-Queries (<30s SLA)
CREATE INDEX idx_travel_history_user_date ON travel_history(user_id, trip_date);

-- 3. INSERT METADATA & PROFILE FOR MAJA HOFFMANN [cite: 35, 43]
INSERT INTO users (id, name, age, city, occupation, cost_priority, co2_priority, flexibility_priority)
VALUES (
    '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', 
    'Maja Hoffmann', 
    34, 
    'Frankfurt', 
    'Product Manager (Fintech)', 
    60, 
    85, 
    75
);

-- 4. INSERT CURRENT ACTIVE SUBSCRIPTIONS (STATUS QUO) [cite: 48, 51]
INSERT INTO subscriptions (id, user_id, service, monthly_cost_eur, status, renewal_date) 
VALUES ('1f9b3117-062e-4e41-b286-9a2e63cbca9f', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', 'bahncard_50', 20.33, 'active', '2026-12-31');
INSERT INTO subscriptions (id, user_id, service, monthly_cost_eur, status, renewal_date) 
VALUES ('c29a8a3c-b034-45eb-bfbc-5df1da01df22', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', 'deutschlandticket', 49.00, 'active', '2026-07-31');
INSERT INTO subscriptions (id, user_id, service, monthly_cost_eur, status, renewal_date) 
VALUES ('748be7ef-fa06-444f-a0ee-6c38bda4c431', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', 'miles_carsharing', 9.00, 'active', '2026-09-15');

-- 5. INSERT 12-MONTH HISTORICAL SYNTHETIC TRAVEL LOGS (85 TRIPS FOR THE ANALYST) [cite: 59]
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('cf8ceb03-f363-4cb5-8cc4-e9185ea933bf', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-06-02', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 25.7, 6.61, 0.77);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('175001ff-17bb-4e94-817c-6bc411514757', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-06-14', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 23.9, 5.74, 0.72);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('7f71b764-f6df-4eb9-bbcc-0ae90bfdb71f', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-06-21', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 38.2, 5.99, 1.15);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('9f7a9be3-b05c-43fe-a33d-51a87b8d4f71', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-06-21', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 21.0, 9.84, 0.63);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('31f77d34-72b2-4d24-8b65-693da756d11f', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-06-22', 'Frankfurt Hbf', 'Hamburg Hbf', 'train_long_distance', 490.0, 137.20, 7.35);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('95b87ac2-1847-49f3-8b7c-02cf42f9da33', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-07-05', 'Frankfurt Hbf', 'Munich Hbf', 'train_long_distance', 390.0, 109.20, 5.85);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('2d81a3d9-952b-4bf1-bf61-394efbe88714', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-07-14', 'Frankfurt Bornheim', 'Frankfurt Westend', 'car_sharing', 14.1, 17.55, 2.12);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('63bf72ea-4d8e-49b6-8be7-5fae38fb50cf', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-07-19', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 34.0, 9.17, 1.02);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('e03294cf-1cb3-48ee-bd51-fbcf72db45fe', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-07-24', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 36.3, 11.23, 1.09);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('bb29dcd4-5fef-4be9-98ee-ef11ba72a6bc', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-07-27', 'Frankfurt Hbf', 'Munich Hbf', 'train_long_distance', 390.0, 109.20, 5.85);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('bf729ed2-2bc3-487e-bb21-0cfd4aef83fb', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-07-31', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 20.3, 5.06, 0.61);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('df92be7c-3cfb-4e1e-92fd-1faebcd392f4', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-08-02', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 26.6, 9.61, 0.80);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('6fb2e9da-3fcb-4be8-82ef-df147cd3ef2a', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-08-04', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 41.5, 9.38, 1.25);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('87b2e6cf-a19c-4be9-bf8e-67feab9d2e1f', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-08-11', 'Frankfurt Hbf', 'Stuttgart Hbf', 'train_long_distance', 200.0, 56.00, 3.00);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('7d829ebc-219d-4be9-ba8f-dfcb7cfa84fd', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-08-15', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 20.4, 10.33, 0.61);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('aa729bde-3cb2-47ef-be8f-ef946cdf72bd', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-08-16', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 19.3, 11.20, 0.58);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('0f72beb3-dcb1-47fa-89cf-1f84cdfa732e', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-08-20', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 34.2, 5.03, 1.03);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('b29ecdb3-cf8a-4be8-bd7c-dfbc729edcf3', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-08-25', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 27.5, 7.37, 0.83);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('c72bcde9-3fc2-487f-be9f-fa7cfda9274e', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-08-29', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 34.6, 9.61, 1.04);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('3bf2daef-92cf-48ef-be32-2faedcf82319', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-09-02', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 30.1, 7.50, 0.90);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('fb29cdfa-3ef2-48fe-a931-df249cbdf3fe', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-09-05', 'Frankfurt Hbf', 'Munich Hbf', 'train_long_distance', 390.0, 109.20, 5.85);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('2d3e9fbc-83fa-49bc-9fa8-1f2e9dca3922', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-09-11', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 21.0, 8.52, 0.63);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('cf92bdfe-2bf3-49ef-b32d-20fedcba3e2f', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-09-12', 'Frankfurt Hbf', 'Berlin Hbf', 'train_long_distance', 545.0, 152.60, 8.18);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('7f329ebd-12bc-48fa-bf7e-29fdcbde4f2d', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-09-14', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 17.5, 4.88, 0.53);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('a0b2cd9e-3f9c-4be7-82fd-faef93cd74be', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-09-22', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 17.0, 9.39, 0.51);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('d829ebcf-fa23-4be7-bdcf-329fadecf329', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-09-28', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 26.2, 7.31, 0.79);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('29bdcfa3-3ef2-4bf1-bf32-9fadebca72df', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-10-02', 'Frankfurt Hbf', 'Munich Hbf', 'train_long_distance', 390.0, 109.20, 5.85);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('ef92bdcf-3bf2-4da8-9efc-fa239debcf72', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-10-10', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 33.1, 11.23, 0.99);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('92bdcfa2-23bf-48f1-aee2-cf329debfa23', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-10-15', 'Frankfurt Hbf', 'Berlin Hbf', 'train_long_distance', 545.0, 152.60, 8.18);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('3fe2da9c-29cf-48ef-b321-dfcb729edcba', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-10-24', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 34.6, 6.22, 1.04);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('6fb29cda-3ef2-48ea-b231-fadecf729ebd', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-11-04', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 20.3, 10.98, 0.61);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('7d829ebc-21cf-4aef-ba92-defcba739ede', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-11-14', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 23.4, 9.87, 0.70);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('aa729bde-3fc2-487f-be8d-ef92bdcf74ab', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-11-18', 'Frankfurt Hbf', 'Berlin Hbf', 'train_long_distance', 545.0, 152.60, 8.18);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('cc92bde3-fc29-47ea-bd82-df729ebcf32a', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-11-20', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 16.5, 4.70, 0.50);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('ee92bdc3-fc29-48fa-bdcf-329fadec7329', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-11-22', 'Frankfurt Hbf', 'Stuttgart Hbf', 'train_long_distance', 200.0, 56.00, 3.00);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('ff92bdc2-3bf2-48ea-bdee-cf329debcf72', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-11-28', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 28.1, 7.85, 0.84);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('12bdcfa3-ef29-4bf1-bdee-9fadebca72df', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-12-05', 'Frankfurt Hbf', 'Munich Hbf', 'train_long_distance', 390.0, 109.20, 5.85);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('34f2daef-92cf-48ef-bdee-2faedcf82319', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-12-12', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 34.5, 9.12, 1.04);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('56b87ac2-1847-49f3-8bde-0cf42f9da33b', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-12-14', 'Frankfurt Bornheim', 'Frankfurt Westend', 'car_sharing', 5.6, 9.98, 0.84);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('78bf72ea-4d8e-49b6-8bde-5fae38fb50cf', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-12-20', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 29.8, 8.44, 0.89);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('9ab2cd9e-3f9c-4be7-82de-faef93cd74be', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2025-12-24', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 20.3, 11.23, 0.61);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('bc29dcd4-5fef-4be9-98ee-ef11ba72a6bc', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-01-04', 'Frankfurt Hbf', 'Hamburg Hbf', 'train_long_distance', 490.0, 137.20, 7.35);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('de81a3d9-952b-4bf1-bf61-394efbe88714', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-01-08', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 25.0, 6.78, 0.75);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('fa729bde-3cb2-47ef-be8f-ef946cdf72bd', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-01-14', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 34.6, 9.88, 1.04);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('1c92bde3-fc29-47ea-bd82-df729ebcf32a', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-01-18', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 23.4, 5.12, 0.70);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('3e92bdc3-fc29-48fa-bdcf-329fadec7329', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-01-22', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 28.5, 7.14, 0.86);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('5f92bdc2-3bf2-48ea-bdee-cf329debcf72', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-01-28', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 20.3, 5.60, 0.61);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('72bdcfa3-ef29-4bf1-bdee-9fadebca72df', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-02-02', 'Frankfurt Hbf', 'Berlin Hbf', 'train_long_distance', 545.0, 152.60, 8.18);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('94f2daef-92cf-48ef-bdee-2faedcf82319', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-02-05', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 44.5, 11.23, 1.34);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('b6b87ac2-1847-49f3-8bde-0cf42f9da33b', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-02-12', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 34.2, 8.50, 1.03);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('d8bf72ea-4d8e-49b6-8bde-5fae38fb50cf', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-02-15', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 19.3, 4.90, 0.58);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('fab2cd9e-3f9c-4be7-82de-faef93cd74be', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-02-18', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 25.1, 7.33, 0.75);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('1c29dcd4-5fef-4be9-98ee-ef11ba72a6bc', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-02-22', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 38.2, 9.61, 1.15);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('3e81a3d9-952b-4bf1-bf61-394efbe88714', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-02-28', 'Frankfurt Hbf', 'Munich Hbf', 'train_long_distance', 390.0, 109.20, 5.85);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('5fa29bde-3cb2-47ef-be8f-ef946cdf72bd', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-03-02', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 20.3, 5.20, 0.61);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('7c92bde3-fc29-47ea-bd82-df729ebcf32a', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-03-05', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 25.4, 7.31, 0.76);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('9e92bdc3-fc29-48fa-bdcf-329fadec7329', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-03-12', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 21.0, 5.44, 0.63);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('bf92bdc2-3bf2-48ea-bdee-cf329debcf72', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-03-14', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 34.6, 9.61, 1.04);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('d2bdcfa3-ef29-4bf1-bdee-9fadebca72df', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-03-20', 'Frankfurt Hbf', 'Berlin Hbf', 'train_long_distance', 545.0, 152.60, 8.18);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('f4f2daef-92cf-48ef-bdee-2faedcf82319', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-03-22', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 17.5, 4.22, 0.53);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('16b87ac2-1847-49f3-8bde-0cf42f9da33b', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-03-24', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 26.6, 7.31, 0.80);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('38bf72ea-4d8e-49b6-8bde-5fae38fb50cf', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-03-28', 'Frankfurt Hbf', 'Munich Hbf', 'train_long_distance', 390.0, 109.20, 5.85);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('5ab2cd9e-3f9c-4be7-82de-faef93cd74be', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-04-02', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 34.2, 9.61, 1.03);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('7c29dcd4-5fef-4be9-98ee-ef11ba72a6bc', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-04-05', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 20.3, 5.01, 0.61);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('9e81a3d9-952b-4bf1-bf61-394efbe88714', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-04-12', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 34.0, 9.12, 1.02);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('bfa29bde-3cb2-47ef-be8f-ef946cdf72bd', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-04-14', 'Frankfurt Hbf', 'Frankfurt Airport', 'train_regional', 23.4, 5.44, 0.70);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('dc92bde3-fc29-47ea-bd82-df729ebcf32a', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-04-20', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 28.5, 7.82, 0.86);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('fe92bdc3-fc29-48fa-bdcf-329fadec7329', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-04-22', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 20.3, 5.60, 0.61);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('1f92bdc2-3bf2-48ea-bdee-cf329debcf72', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-04-28', 'Frankfurt Hbf', 'Munich Hbf', 'train_long_distance', 390.0, 109.20, 5.85);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('32bdcfa3-ef29-4bf1-bdee-9fadebca72df', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-05-02', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 25.4, 7.12, 0.76);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('54f2daef-92cf-48ef-bdee-2faedcf82319', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-05-05', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 21.0, 5.44, 0.63);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('76b87ac2-1847-49f3-8bde-0cf42f9da33b', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-05-12', 'Frankfurt Hbf', 'Wiesbaden Hbf', 'train_regional', 34.6, 9.61, 1.04);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('98bf72ea-4d8e-49b6-8bde-5fae38fb50cf', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-05-14', 'Frankfurt Hbf', 'Berlin Hbf', 'train_long_distance', 545.0, 152.60, 8.18);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('bab2cd9e-3f9c-4be7-82de-faef93cd74be', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-05-20', 'Frankfurt Hbf', 'Darmstadt Hbf', 'train_regional', 17.5, 4.88, 0.53);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('dc29dcd4-5fef-4be9-98ee-ef11ba72a6bc', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-05-22', 'Frankfurt Hbf', 'Mainz Hbf', 'train_regional', 26.6, 7.31, 0.80);
INSERT INTO travel_history (id, user_id, trip_date, origin, destination, mode, distance_km, cost_eur_base, co2_kg) VALUES ('fe81a3d9-952b-4bf1-bf61-394efbe88714', '4ae3d0db-1a6f-42b7-bd20-0fc61266b095', '2026-05-28', 'Frankfurt Hbf', 'Munich Hbf', 'train_long_distance', 390.0, 109.20, 5.85);