"""Curated real photography spots for the seeder (authored by hand, not random).

Each entry is a real, Google-geocodable location. `geocode_query` is forward-
geocoded at seed time to get real lat/lng + city/admin/country, so coordinates
are authentic rather than invented. `notes`, `gear`, and `composition` are
written per-spot in a casual, photographer-to-photographer voice so reviews read
like a real person wrote them about THAT place. The tendency fields (best_times,
access_level, etc.) bias each review so the spot's aggregates come out true to
life (a beach skews Sunset + Summer; a canyon trail skews Moderate access).

`photo_query` is an optional override for the Unsplash image search when the spot
name alone returns nothing; if absent the seeder derives a query from the name.

Enum string values must match the API schema exactly (see BEST_TIMES /
ACCESS_LEVELS / CROWD_LEVELS / SEASONS in scripts/seed_real_data.py).

STATUS: full curated set of real LA-area spots.
"""

SEED_SPOTS = [
    {
        "name": "Griffith Observatory",
        "geocode_query": "Griffith Observatory, Los Angeles, CA",
        "notes": [
            "This is the classic LA skyline shot. Set up on the west lawn and wait "
            "for the city lights to pop on, it happens faster than you think.",
            "Parking up top is rough on weekends. I usually park down by Fern Dell "
            "and walk up, you get a few nice trail shots on the way anyway.",
            "Blue hour is really short here so have everything dialed in. The "
            "building lights and the city come up almost together for maybe ten "
            "good minutes.",
            "Weekdays are so much calmer. On a weekend the front terrace is packed "
            "with tripods once the sun drops.",
            "Heads up, the marine layer can roll in and totally kill the view even "
            "in summer. Check the live cam before you make the drive up.",
            "The Astronomers Monument out front makes a great silhouette if you want "
            "something in the foreground.",
            "Car trails on the road below are a fun long exposure from the east "
            "railing if the skyline shot feels too obvious.",
            "It gets cold and windy on the terrace after dark, bring a jacket even "
            "if it was warm at the bottom of the hill.",
            "If the road is gated because the lot filled up, just take a rideshare, "
            "way less stressful.",
        ],
        "gear": [
            "Bring a tripod for sure, you'll want it once the city lights come on.",
            "A 70 to 200 is perfect for pulling in the skyline and the Hollywood sign.",
            "A grad ND really helps balance the bright sky against the darker basin "
            "at golden hour.",
            "Use a remote or the 2 second timer, the railing shakes when it's busy.",
        ],
        "composition": [
            "Put the dome up front and let the skyline sit low in the frame.",
            "Use the monument as a dark silhouette against the dusk colors.",
            "Let the road below lead the eye into downtown with some car trails.",
        ],
        "best_times": ["GoldenHour", "BlueHour", "Night"],
        "best_seasons": ["YearRound", "Winter", "Fall"],
        "access_level": "Easy",
        "crowd_level": "Crowded",
        "entrance_fee_options": [0.0, 0.0, 0.0, 10.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Venice Canals",
        "geocode_query": "Venice Canals, Venice, CA",
        "notes": [
            "Go at sunrise. The water is dead still and you get perfect mirror "
            "reflections of the little bridges before anyone is out.",
            "Just remember people actually live here, so keep it quiet and be chill "
            "about shooting near their windows.",
            "The arched footbridges are the money shot. The one where Sherman meets "
            "Carroll is my favorite.",
            "Golden hour lights up all the pastel houses and doubles them in the "
            "water, it's gorgeous.",
            "Parking is a pain midday but super easy if you come early. Find a spot "
            "on Pacific and walk in.",
            "Around the holidays people string lights along the canals and the blue "
            "hour reflections are unreal.",
            "Throw a polarizer on to cut the glare and make the reflections deeper.",
            "Get right down at the waterline, it makes the reflection fill the whole "
            "bottom of the frame.",
        ],
        "gear": [
            "A polarizer is clutch here for managing glare on the water.",
            "A 24 to 70 covers the bridges and the wider canal scenes nicely.",
            "Bring a tripod for those still pre dawn reflection shots.",
        ],
        "composition": [
            "Center an arched bridge and mirror it in the still water below.",
            "Drop low to the waterline so the reflection owns the bottom half.",
            "Use the canal itself as a line leading to a bridge in the distance.",
        ],
        "best_times": ["Sunrise", "GoldenHour", "BlueHour"],
        "best_seasons": ["Spring", "Winter", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Sixth Street Viaduct",
        "geocode_query": "Sixth Street Viaduct, Los Angeles, CA",
        "photo_query": "Los Angeles Sixth Street Bridge skyline night",
        "notes": [
            "The lit arches at blue hour are the whole reason to come. They glow and "
            "the downtown skyline sits right behind them.",
            "Shoot from the lower plaza on the east side, you get the arches stacking "
            "up with the skyline framed inside.",
            "Honestly go with a friend after dark. It can get sketchy and there are "
            "street takeovers sometimes, just keep your gear close.",
            "The pedestrian deck gives you clean lines of the arches marching toward "
            "downtown.",
            "Car light trails along the deck pair perfectly with the lit arches on a "
            "long exposure.",
            "Don't bother midday, it's flat and harsh. This is a blue hour and night "
            "spot all the way.",
            "Cyclists and runners are on the deck constantly, so be aware when you "
            "set up a tripod.",
        ],
        "gear": [
            "You'll want a tripod for the blue hour and the light trails.",
            "A wide lens around 16 to 35 grabs the full sweep of the arches.",
            "A remote release keeps your long exposures clean.",
        ],
        "composition": [
            "Let the arches repeat as a rhythm leading toward the skyline.",
            "Frame downtown inside the opening of the closest arch.",
            "Run the deck lines diagonally for depth and add car trails.",
        ],
        "best_times": ["BlueHour", "Night", "GoldenHour"],
        "best_seasons": ["YearRound", "Summer", "Fall"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "El Matador State Beach",
        "geocode_query": "El Matador State Beach, Malibu, CA",
        "notes": [
            "Check the tide chart first, seriously. The sea caves and arches only "
            "work around low tide.",
            "It's a steep staircase and a bit of a scramble down to the sand, so "
            "pack light and wear decent shoes.",
            "Sunset behind the sea stacks is the shot. The light wraps right through "
            "the arch and it's magic.",
            "The lot is small and charges a fee, and it fills up fast for sunset on "
            "weekends.",
            "Bring a cloth, the sea spray coats your front element constantly down "
            "there.",
            "A long exposure turns the surf around the rocks into this dreamy mist.",
            "Get there before golden hour so you can scout your foreground rocks "
            "while you can still see the slippery spots.",
            "Watch the incoming tide. People get stuck behind the rocks out here "
            "every weekend.",
        ],
        "gear": [
            "An ND filter is great for that silky long exposure surf around the stacks.",
            "Bring a microfiber cloth, the spray is relentless on the front element.",
            "A sturdy tripod you don't mind getting wet and sandy.",
            "A wide lens to take in an arch with the stacks beyond it.",
        ],
        "composition": [
            "Shoot through a sea arch to frame a stack lit by the setting sun.",
            "Use a foreground rock and a slow shutter to lead into the surf.",
            "Tuck the sun just behind a stack so the light flares around it.",
        ],
        "best_times": ["GoldenHour", "Sunrise", "BlueHour"],
        "best_seasons": ["Summer", "Fall", "YearRound"],
        "access_level": "Moderate",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0, 8.0, 12.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Eaton Canyon Falls",
        "geocode_query": "Eaton Canyon Falls, Pasadena, CA",
        "photo_query": "waterfall canyon hike California",
        "notes": [
            "It's about a mile and a half each way with a few stream crossings, so "
            "your feet are getting wet, just plan for it.",
            "Overcast days are actually best at the falls. Full sun blows out the "
            "water and the shadows get brutal.",
            "Go early to beat the heat and the crowds that pile up at the base pool "
            "by midday.",
            "A long exposure makes the falls go silky, but you'll need an ND in "
            "daylight down in the canyon.",
            "The canyon stays shaded and cool so the light is soft well into the "
            "morning.",
            "After it rains the flow is amazing but the crossings get genuinely "
            "sketchy, don't push your luck.",
            "Bring a polarizer to kill the glare on the wet rocks and the pool.",
        ],
        "gear": [
            "An ND filter to slow the shutter for that silky water in daylight.",
            "A polarizer for the wet rocks and the pool reflections.",
            "A small travel tripod, you're carrying it the whole hike.",
        ],
        "composition": [
            "Use the stream as a line leading back to the falls.",
            "Anchor the foreground with a wet boulder for depth.",
            "Go vertical to get the full drop and the pool underneath.",
        ],
        "best_times": ["Midday", "GoldenHour", "Sunrise"],
        "best_seasons": ["Spring", "Winter", "Fall"],
        "access_level": "Moderate",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Walt Disney Concert Hall",
        "geocode_query": "Walt Disney Concert Hall, Los Angeles, CA",
        "notes": [
            "The steel curves are the subject here. Overcast light actually works in "
            "your favor and saves you from harsh hot spots.",
            "Walk up to the garden terrace, you get cool abstract shots of the steel "
            "folds away from the street crowds.",
            "Early morning light rakes across the panels and really brings out the "
            "texture.",
            "Travel light. Security will move you along if you plant a big tripod "
            "near the entrances.",
            "Look for the sky and the neighboring buildings reflecting and warping "
            "across the curved panels.",
            "Blue hour with the building lit and a deep sky makes the steel glow.",
            "This is a place to hunt for abstracts, not one single hero shot, so "
            "just wander and look up.",
        ],
        "gear": [
            "A 24 to 70 covers both the full facade and the tighter abstracts.",
            "A polarizer helps you control the reflections on the steel.",
            "A longer lens is fun for isolating curve on curve abstractions.",
        ],
        "composition": [
            "Fill the frame with intersecting steel curves for a clean abstract.",
            "Find a sky reflection warping across a panel and frame just that.",
            "Shoot from a low angle so a curve sweeps diagonally out of frame.",
        ],
        "best_times": ["Sunrise", "GoldenHour", "BlueHour"],
        "best_seasons": ["YearRound", "Winter", "Spring"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": False,
    },
    {
        "name": "Vista Hermosa Natural Park",
        "geocode_query": "Vista Hermosa Natural Park, Los Angeles, CA",
        "notes": [
            "Best little secret for a skyline shot framed by golden grass and oak "
            "hills. You'd never guess you're right next to downtown.",
            "Climb up to the top meadow for the cleanest skyline view, the lower "
            "picnic areas get blocked by trees.",
            "Golden hour sets the dry grass on fire with the towers behind it.",
            "It's genuinely quiet on weekdays, you'll often have the hilltop to "
            "yourself.",
            "The park locks the gate at dusk and they mean it, so don't plan a full "
            "night shoot here.",
            "A longer lens compresses the skyline so it looms bigger behind the grass.",
            "There's a little stream and bridge lower down that makes a nice second "
            "subject.",
        ],
        "gear": [
            "A 70 to 200 to compress the skyline behind the foreground grass.",
            "A tripod for the golden hour and early blue hour frames.",
            "A grad ND to hold the bright sky over the shadowed hillside.",
        ],
        "composition": [
            "Layer the foreground grass, the oak hills, and the skyline for depth.",
            "Put the towers on a third and let the grass lead up to them.",
            "Shoot low through the grass so it frames the base of the skyline.",
        ],
        "best_times": ["GoldenHour", "Sunrise", "BlueHour"],
        "best_seasons": ["Fall", "Summer", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Point Dume",
        "geocode_query": "Point Dume State Beach, Malibu, CA",
        "photo_query": "Malibu coastline cliffs ocean",
        "notes": [
            "Take the boardwalk up to the bluff overlook, the view down the coast "
            "toward the cove is the best part.",
            "In winter and early spring you can spot whales migrating from the "
            "point, so bring the long lens just in case.",
            "Sunset from the bluff is unreal, but the trail down to the beach gets "
            "dark fast so plan your way out.",
            "The lot is small and gated at a set time, and street parking is tight "
            "and strictly enforced.",
            "Down on the sand at low tide the rock face glows in the last light.",
            "It's windy up top, so weigh down a light tripod or it'll shake.",
            "A polarizer really makes that turquoise water pop from the overlook.",
        ],
        "gear": [
            "A 100 to 400 for whales and compressing the distant coastline.",
            "A polarizer to saturate the water from the bluff.",
            "A stable tripod you can weigh down against the wind.",
        ],
        "composition": [
            "Use the curving cove shoreline as a line leading off the bluff.",
            "Set the rocky point as a dark anchor against the bright sea.",
            "Shoot down the coast so the headlands stack into the haze.",
        ],
        "best_times": ["GoldenHour", "Sunrise", "BlueHour"],
        "best_seasons": ["Winter", "Spring", "Fall"],
        "access_level": "Moderate",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0, 3.0, 12.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Echo Park Lake",
        "geocode_query": "Echo Park Lake, Los Angeles, CA",
        "notes": [
            "Summer is the time. The lotus bed blooms and you get pink flowers in "
            "the foreground with the skyline behind.",
            "The fountain with the downtown towers reflected in the lake is the "
            "signature frame from the south end.",
            "Come at sunrise for glassy water and the palms catching that first "
            "warm light.",
            "You can rent a swan boat if you want a foreground element, but honestly "
            "the shoreline angles are plenty.",
            "Golden hour backlights the fountain spray and it looks amazing.",
            "It's a busy park with joggers and dogs and families, so mornings are "
            "your best bet for clean shots.",
            "A polarizer cuts the glare on the lotus leaves and deepens the "
            "reflection.",
        ],
        "gear": [
            "A 24 to 70 covers the fountain, the lotus, and the skyline reflection.",
            "A polarizer for the water and the waxy lotus leaves.",
            "A tripod for sunrise long exposures of the fountain.",
        ],
        "composition": [
            "Put the lotus blooms up front with the skyline reflected behind.",
            "Center the fountain and mirror it in the still morning water.",
            "Use the palm lined shore as a line leading to downtown.",
        ],
        "best_times": ["Sunrise", "GoldenHour", "BlueHour"],
        "best_seasons": ["Summer", "Spring", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Santa Monica Pier",
        "geocode_query": "Santa Monica Pier, Santa Monica, CA",
        "notes": [
            "The neon Ferris wheel against a deep blue hour sky is the shot people "
            "travel for, so get there as the lights come on.",
            "Get under the pier pilings at low tide, you get gritty leading lines "
            "and great silhouette frames toward the surf.",
            "It's crowded basically always. Either lean into the people or shoot "
            "long exposures to blur them out.",
            "From the beach just south of the pier you can get the whole thing with "
            "the sun setting behind it.",
            "The neon reflecting on wet sand after the tide pulls back is so "
            "underrated.",
            "Keep your bag zipped and in front of you at night, pickpockets work "
            "the crowds.",
            "A long exposure turns the Ferris wheel into a ring of light streaks.",
        ],
        "gear": [
            "A tripod for the blue hour neon and the long exposures.",
            "A wide lens around 16 to 35 for the under the pier shots.",
            "An ND to drag the shutter and smooth out the crowds and surf.",
        ],
        "composition": [
            "Set the lit Ferris wheel against the gradient of a blue hour sky.",
            "Use the pilings under the pier as converging leading lines.",
            "Catch the neon reflected on the wet sand in the foreground.",
        ],
        "best_times": ["BlueHour", "Night", "GoldenHour"],
        "best_seasons": ["Summer", "YearRound", "Fall"],
        "access_level": "Easy",
        "crowd_level": "Crowded",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Lake Hollywood Park",
        "geocode_query": "Lake Hollywood Park, Los Angeles, CA",
        "photo_query": "Hollywood Sign Los Angeles hills",
        "notes": [
            "This is the spot for a clean unobstructed Hollywood Sign shot without "
            "doing the whole hike.",
            "Bring a long lens, the sign is farther than it looks and you'll want to "
            "fill the frame.",
            "Morning light hits the sign straight on, afternoon backlights it which "
            "can be moody if that's your thing.",
            "It's a small park in a residential street so parking is limited, just "
            "be respectful of the neighbors.",
            "The grassy hill and the trees make a nice natural frame around the sign.",
            "Weekends get busy with tourists doing the same shot, mornings are way "
            "calmer.",
            "Haze can soften the sign on bad air days, a clear day after rain is "
            "chef's kiss.",
        ],
        "gear": [
            "A 70 to 200 or longer to really pull the sign in.",
            "A polarizer helps cut through the haze a bit.",
            "A tripod if you want tack sharp shots at full zoom.",
        ],
        "composition": [
            "Frame the sign through the trees for a natural border.",
            "Use the green hillside as foreground leading up to the sign.",
            "Go tight and let the letters fill the whole frame.",
        ],
        "best_times": ["GoldenHour", "Sunrise", "Midday"],
        "best_seasons": ["Winter", "Spring", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Runyon Canyon Park",
        "geocode_query": "Runyon Canyon Park, Los Angeles, CA",
        "photo_query": "Los Angeles hills hike city view",
        "notes": [
            "Quick steep hike with a big payoff, you get the whole city laid out "
            "from the top.",
            "Go at sunrise to beat the heat and the crowds, this place is packed by "
            "mid morning.",
            "The view from the upper ridge stretches all the way to downtown on a "
            "clear day.",
            "It's mostly exposed with no shade, so a hazy marine layer morning "
            "actually gives softer light.",
            "Lots of dogs and runners, it's a social trail more than a quiet one.",
            "Blue hour from the top with the city lights coming on is underrated.",
            "Wear real shoes, the dirt gets loose and dusty on the steep parts.",
        ],
        "gear": [
            "A wide lens for the sweeping city panorama.",
            "A tripod for blue hour if you stay past sunset.",
            "A polarizer to punch up a hazy sky.",
        ],
        "composition": [
            "Use the trail itself as a leading line down toward the city.",
            "Layer the ridge lines with downtown in the far distance.",
            "Get a person on the ridge for scale against the skyline.",
        ],
        "best_times": ["Sunrise", "GoldenHour", "BlueHour"],
        "best_seasons": ["Fall", "Winter", "YearRound"],
        "access_level": "Moderate",
        "crowd_level": "Crowded",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "The Getty Center",
        "geocode_query": "The Getty Center, Los Angeles, CA",
        "notes": [
            "The travertine architecture is the star here, all clean lines and warm "
            "stone that glows at golden hour.",
            "The Central Garden is great but the architecture and the city views from "
            "the terraces are what I keep coming back for.",
            "Admission is free, you just pay for parking, and the tram ride up is "
            "part of the fun.",
            "Overcast days are actually nice for the stone, harsh midday sun makes "
            "the white surfaces blow out.",
            "Look for shadows and geometry, the whole place is a playground of "
            "angles and light.",
            "On a clear day you can see all the way to the ocean from the south "
            "terrace.",
            "They close in the evening so you can't really shoot full night, but "
            "late afternoon light is gorgeous.",
        ],
        "gear": [
            "A 24 to 70 covers the architecture and the garden.",
            "A polarizer for the sky against all that pale stone.",
            "A wide lens for the big symmetrical courtyard shots.",
        ],
        "composition": [
            "Use the travertine walls as strong geometric leading lines.",
            "Frame the city view through an architectural opening.",
            "Find symmetry in the courtyards and shoot it dead center.",
        ],
        "best_times": ["GoldenHour", "Midday", "Sunrise"],
        "best_seasons": ["YearRound", "Spring", "Fall"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0, 0.0, 25.0],
        "permit": False,
        "drone": False,
        "tripod": False,
    },
    {
        "name": "Union Station",
        "geocode_query": "Union Station, Los Angeles, CA",
        "photo_query": "Union Station Los Angeles architecture interior",
        "notes": [
            "The old waiting hall is stunning, those big leather chairs and the "
            "light pouring through the tall windows.",
            "Early morning has the best light through the windows and the fewest "
            "commuters in your frame.",
            "It mixes Spanish and Art Deco styles and the details are everywhere, "
            "look up at the ceilings.",
            "The courtyards and archways outside are quieter and great for warm "
            "afternoon light.",
            "Be mindful it's a working station, don't block walkways with a tripod "
            "during rush hour.",
            "The long ticketing corridor makes an amazing symmetrical leading line.",
            "It's a popular film location so it just looks cinematic naturally.",
        ],
        "gear": [
            "A wide lens for the grand hall and the corridors.",
            "A tripod for low light interiors if it's not crowded.",
            "A fast prime for handheld shots in the dim corners.",
        ],
        "composition": [
            "Shoot the long corridor straight on for perfect symmetry.",
            "Catch a beam of window light falling across the waiting hall.",
            "Frame people small under the big archways for scale.",
        ],
        "best_times": ["GoldenHour", "Sunrise", "Midday"],
        "best_seasons": ["YearRound", "Winter", "Fall"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": False,
    },
    {
        "name": "Watts Towers",
        "geocode_query": "Watts Towers, Los Angeles, CA",
        "photo_query": "mosaic tower sculpture colorful",
        "notes": [
            "Wild folk art towers covered in tile, glass, and shells, there's "
            "nothing else like it in the city.",
            "The light through the mosaic gaps makes amazing patterns, mid morning is "
            "great for that.",
            "Get in tight on the details, the textures and embedded objects are the "
            "real story here.",
            "It's in a quieter neighborhood, just be respectful and aware like "
            "anywhere.",
            "A blue sky behind the towers makes the colored glass really pop.",
            "Tours run on a schedule so check before you go if you want inside the "
            "fence.",
            "Backlight through the colored glass at the right angle is magic.",
        ],
        "gear": [
            "A macro or close focusing lens for the mosaic details.",
            "A polarizer to saturate the glass and tile against the sky.",
            "A wide lens to get a full tower top to bottom.",
        ],
        "composition": [
            "Shoot up the tower with a blue sky behind the colored glass.",
            "Fill the frame with the mosaic texture for an abstract.",
            "Catch light passing through a gap in the tilework.",
        ],
        "best_times": ["Midday", "GoldenHour", "Sunrise"],
        "best_seasons": ["YearRound", "Summer", "Spring"],
        "access_level": "Easy",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0, 0.0, 7.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Angels Flight Railway",
        "geocode_query": "Angels Flight Railway, Los Angeles, CA",
        "photo_query": "Angels Flight Los Angeles funicular orange",
        "notes": [
            "The little orange funicular cars are super photogenic, especially the "
            "two passing each other on the incline.",
            "Shoot from the bottom looking up the tracks for that classic "
            "converging line shot.",
            "It's a quick cheap ride and you can shoot from inside the car looking "
            "down too.",
            "Late afternoon the warm light hits the cars and the old station arch "
            "really nicely.",
            "Downtown around it has great texture, the Grand Central Market is right "
            "there.",
            "It can get a little line on weekends but it moves fast.",
            "Blue hour with the station sign lit is a fun one.",
        ],
        "gear": [
            "A 24 to 70 is plenty for the cars and the tracks.",
            "A tripod for blue hour shots of the lit station.",
            "A polarizer to deepen that orange against the sky.",
        ],
        "composition": [
            "Shoot straight up the tracks so the rails converge.",
            "Catch both cars as they pass at the midpoint.",
            "Frame a car under the old Beaux Arts station arch.",
        ],
        "best_times": ["GoldenHour", "BlueHour", "Midday"],
        "best_seasons": ["YearRound", "Fall", "Winter"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0, 1.0],
        "permit": False,
        "drone": False,
        "tripod": False,
    },
    {
        "name": "Manhattan Beach Pier",
        "geocode_query": "Manhattan Beach Pier, Manhattan Beach, CA",
        "notes": [
            "Clean classic California pier, the round building at the end frames up "
            "great against a sunset.",
            "Get there for sunset and shoot the pier silhouette with the sun "
            "dropping into the water.",
            "Low tide gives you wet sand reflections of the whole pier, so good.",
            "The pilings underneath make nice repeating lines and silhouette frames.",
            "It's a wide open west facing beach so almost every clear evening "
            "delivers.",
            "Walk out on the pier for a shot looking back at the coast and the hills.",
            "Surfers are usually out near the pier and make great foreground "
            "subjects.",
        ],
        "gear": [
            "A wide lens for the pier and the big sky.",
            "An ND to smooth the water at sunset.",
            "A tripod for the blue hour reflections.",
        ],
        "composition": [
            "Silhouette the pier building against the setting sun.",
            "Use wet sand at low tide to mirror the pier.",
            "Line up the pilings as a repeating leading line.",
        ],
        "best_times": ["GoldenHour", "BlueHour", "Sunrise"],
        "best_seasons": ["Summer", "Fall", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Malibu Pier",
        "geocode_query": "Malibu Pier, Malibu, CA",
        "notes": [
            "Iconic Malibu pier with the white buildings, looks amazing in warm "
            "evening light.",
            "Shoot from the beach to the side to get the full length of the pier "
            "with the hills behind.",
            "Sunrise here is quiet and the light comes up behind the hills onto the "
            "water.",
            "Surfers at Surfrider right next door give you endless action foreground.",
            "Low tide opens up the sand and rocks for foreground interest.",
            "The pier railings and posts make nice leading lines down its length.",
            "Parking is right there but fills up on nice weekends.",
        ],
        "gear": [
            "A 24 to 70 for the pier and the beach scenes.",
            "A longer lens for the surfers.",
            "An ND and tripod for smooth water long exposures.",
        ],
        "composition": [
            "Run the pier diagonally across the frame with the hills behind.",
            "Use the posts and railing as a line down the pier.",
            "Put a surfer in the foreground with the pier beyond.",
        ],
        "best_times": ["GoldenHour", "Sunrise", "BlueHour"],
        "best_seasons": ["Summer", "Fall", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0, 12.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Leo Carrillo State Beach",
        "geocode_query": "Leo Carrillo State Beach, Malibu, CA",
        "photo_query": "Malibu sea cave beach rocks",
        "notes": [
            "Sea caves, tide pools, and big rock formations, it's a playground at "
            "low tide.",
            "Time it with low tide or you won't be able to get to the caves and "
            "arches.",
            "The light coming through the cave openings late in the day is "
            "incredible.",
            "Tide pools have little worlds in them, get low with a macro if you're "
            "into that.",
            "It's a bit of a drive up the coast but way less crowded than the "
            "closer beaches.",
            "Watch the surf around the rocks, sneaker waves are real out here.",
            "A long exposure smooths the water around the rock stacks beautifully.",
        ],
        "gear": [
            "A wide lens for the caves and the rock formations.",
            "An ND filter for silky surf around the rocks.",
            "A microfiber cloth for the inevitable spray.",
        ],
        "composition": [
            "Shoot from inside a cave out toward the lit beach.",
            "Use a tide pool reflection as foreground at golden hour.",
            "Frame a rock arch with the surf rolling through.",
        ],
        "best_times": ["GoldenHour", "Sunrise", "BlueHour"],
        "best_seasons": ["Summer", "Fall", "Spring"],
        "access_level": "Moderate",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0, 3.0, 12.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Abbot Kinney Boulevard",
        "geocode_query": "Abbot Kinney Boulevard, Venice, CA",
        "photo_query": "Venice Los Angeles street mural colorful",
        "notes": [
            "Murals everywhere and a fun trendy street vibe, great for color and "
            "street shots.",
            "The big murals on the side walls are the obvious draw, the light is "
            "best on them in the morning.",
            "Lots of cute storefronts and cafes make nice little detail and lifestyle "
            "frames.",
            "Weekends are lively and good for street photography if you like people "
            "in your shots.",
            "Golden hour down the street gives you warm light and long shadows.",
            "Keep an eye out, the murals change pretty often so there's always "
            "something new.",
            "It's flat and walkable, easy to spend an hour just wandering.",
        ],
        "gear": [
            "A 35 or 50 prime is perfect for street and storefronts.",
            "A wide lens for the full murals up close.",
            "Honestly just a phone works great for this one too.",
        ],
        "composition": [
            "Get a person walking past a mural for scale and life.",
            "Shoot down the street into the warm low sun for long shadows.",
            "Fill the frame with a mural for a bold color block.",
        ],
        "best_times": ["GoldenHour", "Midday", "Sunrise"],
        "best_seasons": ["YearRound", "Spring", "Summer"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": False,
    },
    {
        "name": "Bronson Canyon",
        "geocode_query": "Bronson Canyon, Los Angeles, CA",
        "photo_query": "cave tunnel hike rock Los Angeles",
        "notes": [
            "The Batcave tunnel is the draw, an easy walk in and a fun frame "
            "shooting out the cave mouth.",
            "Shoot from inside looking out so the dark rock frames the bright "
            "canyon beyond.",
            "It's a short flat trail to the caves, totally doable for anyone.",
            "Midday actually works here since the cave interior is dark either way.",
            "You can sometimes catch the Hollywood Sign from spots along the trail.",
            "Quiet on weekday mornings, busier on weekends with families.",
            "Bring a flashlight if you want to light up the cave walls a bit.",
        ],
        "gear": [
            "A wide lens to get the cave mouth framing the canyon.",
            "A tripod for the dark to bright exposure balance.",
            "A fast lens helps inside the dim tunnel.",
        ],
        "composition": [
            "Frame the bright canyon through the dark cave opening.",
            "Put a person in the cave mouth as a silhouette for scale.",
            "Use the curved tunnel walls to lead the eye out.",
        ],
        "best_times": ["Midday", "GoldenHour", "Sunrise"],
        "best_seasons": ["Fall", "Winter", "Spring"],
        "access_level": "Easy",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Greystone Mansion",
        "geocode_query": "Greystone Mansion, Beverly Hills, CA",
        "photo_query": "Tudor mansion garden estate",
        "notes": [
            "Gorgeous old Tudor estate with formal gardens, feels like you stepped "
            "into another era.",
            "The grounds are free to walk and the architecture plus the gardens give "
            "you tons to shoot.",
            "Morning light on the stone facade is beautiful and the gardens are "
            "quiet then too.",
            "You can't usually go inside without an event, but the exterior and "
            "courtyards are the highlight anyway.",
            "The reflecting areas and stairways make great symmetrical compositions.",
            "It's a popular photo and film spot so you'll see other shooters around.",
            "The city view from the upper terrace is a nice bonus.",
        ],
        "gear": [
            "A 24 to 70 for the architecture and garden scenes.",
            "A wide lens for the full facade.",
            "A longer lens for compressing garden details.",
        ],
        "composition": [
            "Center the facade for a grand symmetrical frame.",
            "Use a garden path or stairway as a leading line.",
            "Frame the mansion through an archway or hedge.",
        ],
        "best_times": ["GoldenHour", "Sunrise", "Midday"],
        "best_seasons": ["Spring", "Fall", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": False,
    },
    {
        "name": "The Last Bookstore",
        "geocode_query": "The Last Bookstore, Los Angeles, CA",
        "photo_query": "bookstore interior books tunnel",
        "notes": [
            "The book tunnel and the arches made of books are the iconic shots, it's "
            "a maze upstairs.",
            "Go on a weekday morning right when they open to actually have space to "
            "shoot.",
            "Upstairs in the labyrinth is where all the fun book sculptures and "
            "arches are.",
            "It's dim inside so bump your ISO or bring a fast lens.",
            "Be courteous, it's a working shop and other people want to browse and "
            "shoot too.",
            "The vault room and the little nooks have great character.",
            "No tripod really, it's too tight and busy, go handheld.",
        ],
        "gear": [
            "A fast prime around f1.8 for the low interior light.",
            "A wide lens to get the full book arches.",
            "Steady hands or a high ISO, tripods are tough in there.",
        ],
        "composition": [
            "Shoot straight through the book tunnel for symmetry.",
            "Frame a person walking under a book arch.",
            "Fill the frame with stacked book spines for texture.",
        ],
        "best_times": ["Midday", "Sunrise", "GoldenHour"],
        "best_seasons": ["YearRound", "Winter", "Fall"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": False,
    },
    {
        "name": "Grand Park",
        "geocode_query": "Grand Park, Los Angeles, CA",
        "photo_query": "Los Angeles downtown park fountain city hall",
        "notes": [
            "The pink chairs and the fountain with City Hall behind it is the "
            "signature downtown frame.",
            "Blue hour is great here, City Hall lights up and the fountain looks "
            "dreamy.",
            "The fountain has a wide pool, get low for reflections of City Hall.",
            "It's terraced so you can shoot from a few levels for different "
            "compositions.",
            "Pretty quiet on weekday evenings, events fill it up otherwise.",
            "The pink furniture adds a fun pop of color to foreground.",
            "Long exposure on the fountain at dusk smooths the water nicely.",
        ],
        "gear": [
            "A wide lens for the fountain with City Hall behind.",
            "A tripod for the blue hour and fountain long exposures.",
            "An ND if you want to smooth the water in daylight.",
        ],
        "composition": [
            "Line up the fountain with City Hall centered behind it.",
            "Get low for a City Hall reflection in the fountain pool.",
            "Use the pink chairs as a colorful foreground anchor.",
        ],
        "best_times": ["BlueHour", "GoldenHour", "Night"],
        "best_seasons": ["YearRound", "Spring", "Fall"],
        "access_level": "Easy",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Baldwin Hills Scenic Overlook",
        "geocode_query": "Baldwin Hills Scenic Overlook, Culver City, CA",
        "photo_query": "Los Angeles hilltop stairs city view",
        "notes": [
            "Big stair climb but the top gives you a huge panorama from downtown all "
            "the way to the ocean on a clear day.",
            "The famous stairs themselves make a great shot looking up or down.",
            "Sunset from the top is the move, the whole basin lights up.",
            "It's a real workout, those stairs are no joke, bring water.",
            "Clear days after rain you can see the ocean and downtown in one frame.",
            "Blue hour up top with the city lights is worth the climb.",
            "Gets windy at the top so secure a light tripod.",
        ],
        "gear": [
            "A wide lens for the big panorama.",
            "A 70 to 200 to compress downtown against the foreground.",
            "A tripod for blue hour, weighted against the wind.",
        ],
        "composition": [
            "Shoot down the long staircase for a dramatic leading line.",
            "Layer the foreground hills with downtown and the ocean.",
            "Catch the city lights coming on at blue hour from the top.",
        ],
        "best_times": ["GoldenHour", "BlueHour", "Sunrise"],
        "best_seasons": ["Fall", "Winter", "YearRound"],
        "access_level": "Difficult",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Kenneth Hahn State Recreation Area",
        "geocode_query": "Kenneth Hahn State Recreation Area, Los Angeles, CA",
        "photo_query": "Los Angeles park hilltop skyline view",
        "notes": [
            "Underrated park with a hilltop that gives you a clean downtown skyline "
            "view framed by green.",
            "The overlook up top is the spot, especially when the grass is green in "
            "spring.",
            "Golden hour lights the hills and the skyline sits nicely behind.",
            "There's a little lotus pond and lake lower down for a different subject.",
            "Way less crowded than the famous overlooks, easy to find a calm spot.",
            "Clear winter days give you the sharpest skyline from up here.",
            "Plenty of parking and easy walking, very low key.",
        ],
        "gear": [
            "A 70 to 200 to compress the skyline behind the hills.",
            "A wide lens for the green foreground and big sky.",
            "A tripod for golden and blue hour.",
        ],
        "composition": [
            "Frame the skyline behind a green foreground ridge.",
            "Use a path or tree line to lead toward downtown.",
            "Reflect the sky in the lower pond at sunrise.",
        ],
        "best_times": ["GoldenHour", "Sunrise", "BlueHour"],
        "best_seasons": ["Spring", "Winter", "Fall"],
        "access_level": "Easy",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0, 6.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Will Rogers State Beach",
        "geocode_query": "Will Rogers State Beach, Pacific Palisades, CA",
        "photo_query": "Los Angeles coast beach sunset",
        "notes": [
            "Long open beach with the hills curving around, great for wide sunset "
            "shots.",
            "Sunset is the obvious time, the sun drops right into the water out "
            "here.",
            "Walk toward the bluffs for the coastline curving away into the haze.",
            "Low tide leaves wet sand that mirrors the sky colors.",
            "It's big and rarely feels packed, easy to find your own stretch.",
            "Lifeguard towers make great minimalist subjects against the sky.",
            "A long exposure of the surf at dusk is calming and clean.",
        ],
        "gear": [
            "A wide lens for the open beach and sky.",
            "An ND for smooth surf at sunset.",
            "A tripod for blue hour long exposures.",
        ],
        "composition": [
            "Isolate a lifeguard tower against a colorful sky.",
            "Use the wet sand to mirror the sunset.",
            "Let the coastline curve lead off toward the bluffs.",
        ],
        "best_times": ["GoldenHour", "BlueHour", "Sunrise"],
        "best_seasons": ["Summer", "Fall", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0, 3.0, 12.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Parker Mesa Overlook",
        "geocode_query": "Parker Mesa Overlook, Topanga, CA",
        "photo_query": "Topanga Los Angeles ocean coast overlook",
        "notes": [
            "Hands down one of the best coastal panoramas in LA, you see the whole "
            "coastline and the ocean from up here.",
            "It's a real hike to get out there so plan for it and bring water.",
            "Sunset is unreal, the marine layer below you catching color is "
            "next level.",
            "Time your return, it gets dark on the trail fast after sunset.",
            "On clear days you can see Catalina sitting out on the water.",
            "It's exposed and breezy up top so weigh down your gear.",
            "Golden hour side light on the ridges gives amazing depth.",
        ],
        "gear": [
            "A wide lens for the massive coastal panorama.",
            "A 70 to 200 to pick out ridges and the distant coast.",
            "A tripod for sunset and blue hour, weighted for wind.",
        ],
        "composition": [
            "Layer the ridge lines down to the ocean for depth.",
            "Catch the marine layer glowing below at sunset.",
            "Use the trail or a ridge as a line into the view.",
        ],
        "best_times": ["GoldenHour", "BlueHour", "Sunrise"],
        "best_seasons": ["Winter", "Spring", "Fall"],
        "access_level": "Difficult",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Jerome C. Daniel Overlook",
        "geocode_query": "Jerome C. Daniel Overlook above Hollywood Bowl, Los Angeles, CA",
        "photo_query": "Mulholland Drive Los Angeles skyline overlook night",
        "notes": [
            "Classic Mulholland pullout looking down over the city, the Hollywood "
            "Sign sits off to the side too.",
            "Night is the move here, the whole grid of city lights spreads out below "
            "you.",
            "Blue hour gives you that deep sky plus the lights just coming on.",
            "It's a small pullout so parking is tight, especially on weekend nights.",
            "A long exposure pulls in car trails on the streets below.",
            "Haze can mute the lights, a clear night after wind is best.",
            "Bring a longer lens to compress the sign with the city.",
        ],
        "gear": [
            "A tripod is a must for the night cityscape.",
            "A 24 to 70 for the wide city spread.",
            "A 70 to 200 to compress the sign and downtown.",
        ],
        "composition": [
            "Spread the full grid of city lights across the frame.",
            "Compress the Hollywood Sign against the distant skyline.",
            "Add street car trails with a long exposure.",
        ],
        "best_times": ["Night", "BlueHour", "GoldenHour"],
        "best_seasons": ["Winter", "Fall", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Marina del Rey",
        "geocode_query": "Marina del Rey, CA",
        "photo_query": "Marina del Rey boats harbor sunset",
        "notes": [
            "Tons of boats and masts, great for reflections and that calm harbor "
            "feeling at sunrise.",
            "Sunrise gives you still water and pretty reflections of the masts and "
            "sky.",
            "Fisherman's Village and the jetty are nice spots to set up.",
            "The masts make a forest of vertical lines, fun to play with.",
            "Sunset over the water from the jetty side is warm and easy.",
            "Pretty mellow and walkable, easy parking most of the time.",
            "Long exposure at dusk smooths the water and the boats glow.",
        ],
        "gear": [
            "A 24 to 70 for the harbor and boat scenes.",
            "A tripod for sunrise reflections and dusk long exposures.",
            "A polarizer to cut glare off the water.",
        ],
        "composition": [
            "Mirror the masts and sky in still sunrise water.",
            "Use a line of boats as a repeating leading line.",
            "Silhouette the masts against a sunset sky.",
        ],
        "best_times": ["Sunrise", "GoldenHour", "BlueHour"],
        "best_seasons": ["Summer", "Fall", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Sunken City",
        "geocode_query": "Sunken City, San Pedro, CA",
        "photo_query": "San Pedro coast cliffs ocean rocks",
        "notes": [
            "Old collapsed clifftop with broken slabs and graffiti right over the "
            "ocean, has a real moody abandoned vibe.",
            "Sunset light on the cliffs and the water is gorgeous out here.",
            "You have to scramble a bit and technically hop a fence, so be smart and "
            "careful near the edges.",
            "The broken concrete and rebar make gritty foreground against the sea.",
            "The graffiti adds color if that's your style, otherwise shoot the raw "
            "coastline.",
            "It's exposed and the cliffs are no joke, do not get close to the edge "
            "for a shot.",
            "Long exposure of the surf hitting the rocks below is dramatic.",
        ],
        "gear": [
            "A wide lens for the cliffs and the ocean.",
            "An ND for long exposures of the surf.",
            "A sturdy tripod, and watch your footing setting it up.",
        ],
        "composition": [
            "Use the broken slabs as a gritty foreground to the sea.",
            "Frame the coastline with the cliffs falling away.",
            "Catch the surf exploding on the rocks below at sunset.",
        ],
        "best_times": ["GoldenHour", "BlueHour", "Sunrise"],
        "best_seasons": ["Winter", "Fall", "Spring"],
        "access_level": "Difficult",
        "crowd_level": "Light",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Zuma Beach",
        "geocode_query": "Zuma Beach, Malibu, CA",
        "notes": [
            "Big wide Malibu beach with clean sand and great open sunsets, easy and "
            "reliable.",
            "Sunset straight out over the water is the classic, almost always "
            "delivers on a clear evening.",
            "The far north end near the rocks has more foreground interest.",
            "Low tide and wet sand give you sky reflections across the beach.",
            "It's huge so even on a busy day you can find an empty stretch.",
            "Watch for dolphins offshore, they cruise by pretty often.",
            "A long exposure at dusk turns the surf into soft mist.",
        ],
        "gear": [
            "A wide lens for the open beach and sunset.",
            "An ND for smooth water at golden hour.",
            "A tripod for the blue hour reflections.",
        ],
        "composition": [
            "Center the sun dropping into the water for a clean sunset.",
            "Use wet sand to mirror the sky colors.",
            "Add a rock or piece of driftwood as foreground anchor.",
        ],
        "best_times": ["GoldenHour", "BlueHour", "Sunrise"],
        "best_seasons": ["Summer", "Fall", "YearRound"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0, 3.0, 12.0],
        "permit": False,
        "drone": False,
        "tripod": True,
    },
    {
        "name": "Bradbury Building",
        "geocode_query": "Bradbury Building, Los Angeles, CA",
        "photo_query": "historic building atrium staircase ironwork",
        "notes": [
            "The interior atrium is jaw dropping, all wrought iron, warm wood, and "
            "light pouring down from the glass roof.",
            "Midday is best when the sun comes through the skylight and fills the "
            "atrium with light.",
            "Visitors can only go up to the first landing, but that's plenty for the "
            "iconic shot.",
            "Shoot up at the iron railings and the open elevator cage for that "
            "timeless look.",
            "It's a working building and a film legend, so be quick and respectful.",
            "The geometry of the stairs and railings is endless for compositions.",
            "Soft cloudy days still work since the light is diffused through the "
            "roof.",
        ],
        "gear": [
            "A wide lens to capture the full atrium and skylight.",
            "A fast prime for the warm lower level light.",
            "Handheld is the move, tripods aren't really allowed inside.",
        ],
        "composition": [
            "Shoot up at the ironwork toward the bright skylight.",
            "Use the staircase railings as sweeping leading lines.",
            "Frame the open elevator cage against the glass roof.",
        ],
        "best_times": ["Midday", "GoldenHour", "Sunrise"],
        "best_seasons": ["YearRound", "Winter", "Fall"],
        "access_level": "Easy",
        "crowd_level": "Moderate",
        "entrance_fee_options": [0.0],
        "permit": False,
        "drone": False,
        "tripod": False,
    },
]
