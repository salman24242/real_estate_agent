-- ============================================================================
-- Dummy data for local development & testing.
-- Safe to run multiple times (uses ON CONFLICT DO NOTHING on unique columns).
-- ============================================================================

-- ----------------------------------------------------------------------------
-- Agents (5 sample agents)
-- ----------------------------------------------------------------------------
INSERT INTO agents (id, name, email, phone, agency) VALUES
    ('11111111-1111-1111-1111-111111111111', 'Sarah Mitchell',  'sarah@urbanrealty.com',   '+1-512-555-0101', 'Urban Realty'),
    ('22222222-2222-2222-2222-222222222222', 'Michael Chen',    'michael@citylivinghomes.com', '+1-512-555-0102', 'City Living Homes'),
    ('33333333-3333-3333-3333-333333333333', 'Priya Patel',     'priya@skyhighrealty.com', '+1-212-555-0103', 'SkyHigh Realty'),
    ('44444444-4444-4444-4444-444444444444', 'David Johnson',   'david@coastalproperties.com', '+1-305-555-0104', 'Coastal Properties'),
    ('55555555-5555-5555-5555-555555555555', 'Emma Rodriguez',  'emma@bayviewhomes.com',   '+1-415-555-0105', 'Bayview Homes')
ON CONFLICT (email) DO NOTHING;

-- ----------------------------------------------------------------------------
-- Demo user (for saved-search testing)
-- ----------------------------------------------------------------------------
INSERT INTO users (id, email, hashed_password) VALUES
    ('99999999-9999-9999-9999-999999999999', 'demo@example.com', 'demo-password-hash')
ON CONFLICT (email) DO NOTHING;

-- ----------------------------------------------------------------------------
-- Listings (25 sample listings covering rent + buy across multiple cities)
-- ----------------------------------------------------------------------------
INSERT INTO listings
    (title, description, listing_type, property_type, price, bedrooms, bathrooms, area_sqft,
     city, neighbourhood, address, latitude, longitude, tags, images, agent_id)
VALUES

-- ======================= AUSTIN =======================
('Modern 2BR Loft in Downtown Austin',
 'Stunning loft with exposed brick, hardwood floors and lots of natural light. Walking distance to 6th Street and Rainey.',
 'rent', 'apartment', 2200, 2, 2, 1100,
 'Austin', 'Downtown', '500 E 6th St, Austin, TX 78701',
 30.266926, -97.739380,
 ARRAY['exposed_brick','hardwood_floors','high_ceilings','balcony','gym','near_restaurants','near_transport','modern_finishes'],
 ARRAY['https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800','https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800'],
 '11111111-1111-1111-1111-111111111111'),

('Cozy 1BR Studio near UT Austin',
 'Perfect for students or young professionals. Fully furnished, utilities included.',
 'rent', 'studio', 1350, 1, 1, 550,
 'Austin', 'West Campus', '2400 Rio Grande St, Austin, TX 78705',
 30.290815, -97.740395,
 ARRAY['near_university','near_transport','updated_kitchen','air_conditioning','high_speed_broadband'],
 ARRAY['https://images.unsplash.com/photo-1560185127-6ed189bf02f4?w=800'],
 '11111111-1111-1111-1111-111111111111'),

('Spacious 3BR House in East Austin',
 'Charming bungalow with private garden, updated kitchen and garage. Great for families.',
 'rent', 'house', 2450, 3, 2, 1650,
 'Austin', 'East Austin', '1823 E Cesar Chavez St, Austin, TX 78702',
 30.258671, -97.716904,
 ARRAY['private_garden','garage','updated_kitchen','hardwood_floors','pet_friendly','near_parks','near_schools','recently_renovated'],
 ARRAY['https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800','https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800'],
 '22222222-2222-2222-2222-222222222222'),

('Luxury 2BR Penthouse with Rooftop',
 'Top-floor penthouse with private rooftop terrace, floor-to-ceiling windows and concierge service.',
 'rent', 'penthouse', 4800, 2, 2, 1400,
 'Austin', 'Downtown', '501 W Avenue, Austin, TX 78701',
 30.272160, -97.750800,
 ARRAY['rooftop_terrace','concierge','gym','swimming_pool','high_ceilings','modern_finishes','city_centre','smart_home'],
 ARRAY['https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800'],
 '22222222-2222-2222-2222-222222222222'),

('Charming 2BR Bungalow for Sale',
 'Original 1940s features, recently renovated kitchen, large back yard. Move-in ready.',
 'buy', 'house', 625000, 2, 2, 1350,
 'Austin', 'Hyde Park', '4102 Avenue G, Austin, TX 78751',
 30.308200, -97.722500,
 ARRAY['period_property','original_features','recently_renovated','hardwood_floors','private_garden','fireplace','near_parks','move_in_ready'],
 ARRAY['https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800'],
 '22222222-2222-2222-2222-222222222222'),

('Affordable 1BR Apartment South Austin',
 'Budget-friendly 1BR with balcony, pool access, and covered parking. Near transit.',
 'rent', 'apartment', 1250, 1, 1, 700,
 'Austin', 'South Austin', '2200 S Lamar Blvd, Austin, TX 78704',
 30.248900, -97.783000,
 ARRAY['balcony','swimming_pool','allocated_parking','near_transport','pet_friendly','air_conditioning'],
 ARRAY['https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800'],
 '11111111-1111-1111-1111-111111111111'),

-- ======================= NEW YORK =======================
('Bright 1BR in Williamsburg',
 'Renovated Brooklyn apartment with exposed brick, high ceilings, and skyline views. Near L train.',
 'rent', 'apartment', 3100, 1, 1, 650,
 'New York', 'Williamsburg', '200 Bedford Ave, Brooklyn, NY 11211',
 40.717240, -73.956580,
 ARRAY['exposed_brick','high_ceilings','hardwood_floors','near_transport','near_restaurants','industrial_style','modern_finishes'],
 ARRAY['https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800'],
 '33333333-3333-3333-3333-333333333333'),

('Studio in Manhattan Midtown',
 'Compact but stylish studio with modern finishes and 24/7 concierge. Near Bryant Park.',
 'rent', 'studio', 2800, 1, 1, 420,
 'New York', 'Midtown', '350 W 42nd St, New York, NY 10036',
 40.758800, -73.991600,
 ARRAY['concierge','lift','gym','modern_finishes','city_centre','near_transport','high_speed_broadband'],
 ARRAY['https://images.unsplash.com/photo-1554995207-c18c203602cb?w=800'],
 '33333333-3333-3333-3333-333333333333'),

('3BR Brownstone for Sale - Brooklyn',
 'Classic brownstone with original features, bay windows, private garden, and fireplace. A period property.',
 'buy', 'townhouse', 1850000, 3, 2, 2100,
 'New York', 'Park Slope', '450 8th St, Brooklyn, NY 11215',
 40.669700, -73.983500,
 ARRAY['period_property','bay_windows','fireplace','crown_moulding','private_garden','original_features','near_parks','near_schools'],
 ARRAY['https://images.unsplash.com/photo-1605146769289-440113cc3d00?w=800'],
 '33333333-3333-3333-3333-333333333333'),

('Luxury 2BR Upper East Side',
 'Pre-war building with concierge, gym and lift. Walk to Central Park.',
 'rent', 'apartment', 5500, 2, 2, 1200,
 'New York', 'Upper East Side', '1050 5th Ave, New York, NY 10028',
 40.779800, -73.963900,
 ARRAY['concierge','gym','lift','park_view','near_parks','period_property','crown_moulding','bay_windows'],
 ARRAY['https://images.unsplash.com/photo-1600566753376-12c8ab7fb75b?w=800'],
 '33333333-3333-3333-3333-333333333333'),

-- ======================= MIAMI =======================
('Beachfront 2BR Condo Miami Beach',
 'Stunning ocean views, private balcony, resort-style pool, and 24/7 concierge. Steps to the beach.',
 'rent', 'apartment', 4200, 2, 2, 1150,
 'Miami', 'Miami Beach', '1500 Ocean Dr, Miami Beach, FL 33139',
 25.782600, -80.133100,
 ARRAY['beachfront','balcony','swimming_pool','concierge','gym','near_beach','modern_finishes','smart_home'],
 ARRAY['https://images.unsplash.com/photo-1512917774080-9991f1c4c750?w=800','https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=800'],
 '44444444-4444-4444-4444-444444444444'),

('Modern 3BR Villa with Pool',
 'Private villa with heated pool, outdoor kitchen, and 2-car garage. Perfect for entertaining.',
 'buy', 'villa', 1250000, 3, 3, 2600,
 'Miami', 'Coral Gables', '1200 Alhambra Cir, Coral Gables, FL 33134',
 25.721500, -80.268200,
 ARRAY['pool','outdoor_kitchen','double_garage','private_garden','modern_finishes','smart_home','gated_community','air_conditioning','solar_panels'],
 ARRAY['https://images.unsplash.com/photo-1613490493576-7fde63acd811?w=800'],
 '44444444-4444-4444-4444-444444444444'),

('Cozy 1BR Studio in Wynwood',
 'Artsy Wynwood studio with industrial style and rooftop terrace access. Near galleries and restaurants.',
 'rent', 'studio', 1750, 1, 1, 520,
 'Miami', 'Wynwood', '2500 NW 2nd Ave, Miami, FL 33127',
 25.801800, -80.198900,
 ARRAY['industrial_style','exposed_brick','communal_roof_terrace','near_restaurants','pet_friendly','modern_finishes'],
 ARRAY['https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800'],
 '44444444-4444-4444-4444-444444444444'),

-- ======================= SAN FRANCISCO =======================
('Charming 2BR Victorian',
 'Classic Victorian with bay windows, hardwood floors, and crown moulding. Near Golden Gate Park.',
 'rent', 'house', 4500, 2, 1, 1350,
 'San Francisco', 'Haight-Ashbury', '1700 Haight St, San Francisco, CA 94117',
 37.769800, -122.450100,
 ARRAY['period_property','bay_windows','hardwood_floors','crown_moulding','fireplace','near_parks','original_features'],
 ARRAY['https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800'],
 '55555555-5555-5555-5555-555555555555'),

('Modern 2BR Condo with Bay View',
 'Sleek condo with floor-to-ceiling windows, EV charger, and communal rooftop.',
 'rent', 'apartment', 4800, 2, 2, 1250,
 'San Francisco', 'SoMa', '350 Main St, San Francisco, CA 94105',
 37.791500, -122.391200,
 ARRAY['modern_finishes','high_ceilings','communal_roof_terrace','ev_charger','concierge','gym','city_centre','smart_home','high_speed_broadband'],
 ARRAY['https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800'],
 '55555555-5555-5555-5555-555555555555'),

('Luxury 4BR House for Sale - Pacific Heights',
 'Stunning home with gourmet kitchen, wine cellar, home office, and 3-car garage.',
 'buy', 'house', 4750000, 4, 4, 3800,
 'San Francisco', 'Pacific Heights', '2200 Pacific Ave, San Francisco, CA 94115',
 37.793300, -122.432500,
 ARRAY['gourmet_kitchen','wine_cellar','home_office','double_garage','hardwood_floors','fireplace','crown_moulding','private_garden','recently_renovated','show_home_condition','smart_home'],
 ARRAY['https://images.unsplash.com/photo-1613977257365-aaae5a9817ff?w=800'],
 '55555555-5555-5555-5555-555555555555'),

('Affordable Studio in Mission',
 'Small but well-located studio, walking distance to BART and restaurants.',
 'rent', 'studio', 1950, 1, 1, 400,
 'San Francisco', 'Mission', '2400 Mission St, San Francisco, CA 94110',
 37.756700, -122.418500,
 ARRAY['near_transport','near_restaurants','pet_friendly','high_speed_broadband'],
 ARRAY['https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=800'],
 '55555555-5555-5555-5555-555555555555'),

-- ======================= SEATTLE =======================
('Bright 2BR with Mountain View',
 'Open-plan apartment with mountain views, balcony, and secure bike storage.',
 'rent', 'apartment', 2650, 2, 2, 1050,
 'Seattle', 'Capitol Hill', '1200 E Pike St, Seattle, WA 98122',
 47.614500, -122.317100,
 ARRAY['mountain_view','balcony','bike_storage','modern_finishes','open_plan_kitchen','near_restaurants','near_transport'],
 ARRAY['https://images.unsplash.com/photo-1560448204-e02f11c3d0e2?w=800'],
 '22222222-2222-2222-2222-222222222222'),

('New Build 3BR Townhouse',
 'Brand-new townhouse with underfloor heating, solar panels and smart thermostat.',
 'buy', 'townhouse', 825000, 3, 3, 1850,
 'Seattle', 'Ballard', '6500 24th Ave NW, Seattle, WA 98117',
 47.676200, -122.387900,
 ARRAY['new_build','solar_panels','underfloor_heating','smart_thermostat','double_glazing','ev_charger','off_street_parking','modern_finishes','high_ceilings'],
 ARRAY['https://images.unsplash.com/photo-1564013799919-ab600027ffc6?w=800'],
 '22222222-2222-2222-2222-222222222222'),

('Waterfront 2BR Condo',
 'Right on the water with park view, swimming pool and concierge.',
 'rent', 'apartment', 3400, 2, 2, 1200,
 'Seattle', 'Belltown', '2033 2nd Ave, Seattle, WA 98121',
 47.613500, -122.345100,
 ARRAY['waterfront','park_view','swimming_pool','concierge','gym','lift','city_centre','modern_finishes'],
 ARRAY['https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800'],
 '22222222-2222-2222-2222-222222222222'),

-- ======================= LONDON =======================
('1BR Period Flat in Notting Hill',
 'Classic period property with original features, high ceilings and communal garden.',
 'rent', 'apartment', 2800, 1, 1, 620,
 'London', 'Notting Hill', '22 Portobello Rd, London W11 3DB',
 51.514200, -0.206100,
 ARRAY['period_property','high_ceilings','crown_moulding','original_features','communal_garden','near_parks','near_transport'],
 ARRAY['https://images.unsplash.com/photo-1540518614846-7eded433c457?w=800'],
 '11111111-1111-1111-1111-111111111111'),

('2BR Mews House',
 'Quiet cul-de-sac in Chelsea with courtyard and allocated parking.',
 'buy', 'house', 1450000, 2, 2, 1100,
 'London', 'Chelsea', '15 Walton Mews, London SW3 2JH',
 51.493000, -0.169900,
 ARRAY['cul_de_sac','courtyard','allocated_parking','period_property','hardwood_floors','double_glazing','near_parks','quiet_street','move_in_ready'],
 ARRAY['https://images.unsplash.com/photo-1600585154340-be6161a56a0c?w=800'],
 '11111111-1111-1111-1111-111111111111'),

-- ======================= DENVER =======================
('Mountain-view 3BR House',
 'Family home with mountain views, private garden and 2-car garage. Pet-friendly with fenced yard.',
 'rent', 'house', 2950, 3, 2, 1900,
 'Denver', 'Washington Park', '1450 S Logan St, Denver, CO 80210',
 39.695800, -104.980200,
 ARRAY['mountain_view','private_garden','garage','pet_friendly','garden_for_pets','fireplace','near_parks','near_schools','home_office'],
 ARRAY['https://images.unsplash.com/photo-1568605114967-8130f3a36994?w=800'],
 '22222222-2222-2222-2222-222222222222'),

('Suburban 4BR Family Home',
 'Spacious family home with playroom, study room and basement.',
 'buy', 'house', 720000, 4, 3, 2800,
 'Denver', 'Cherry Creek', '200 Cherry Creek Dr, Denver, CO 80246',
 39.712300, -104.942800,
 ARRAY['playroom','study_room','basement','utility_room','garage','suburban','near_schools','near_shopping','move_in_ready','fireplace','private_garden'],
 ARRAY['https://images.unsplash.com/photo-1570129477492-45c003edd2be?w=800'],
 '22222222-2222-2222-2222-222222222222'),

-- ======================= CHICAGO =======================
('Vintage 2BR Loft in West Loop',
 'Converted warehouse loft with exposed brick, high ceilings, and industrial style.',
 'rent', 'apartment', 2400, 2, 2, 1300,
 'Chicago', 'West Loop', '1100 W Randolph St, Chicago, IL 60607',
 41.884000, -87.653900,
 ARRAY['exposed_brick','high_ceilings','industrial_style','hardwood_floors','balcony','near_restaurants','near_transport','gym'],
 ARRAY['https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=800'],
 '33333333-3333-3333-3333-333333333333')

ON CONFLICT DO NOTHING;
