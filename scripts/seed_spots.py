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

STATUS: first batch of 10 for sanity check. More to be appended.
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
]
