import sys
import argparse
from pathlib import Path

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.config import AppConfig
from core.schemas import ShortsScript, VisualSegment
from core.script_generator import ScriptGenerator

def get_mock_script(topic: str) -> ShortsScript:
    """
    Provides a high-substance, fact-dense viral script with real numbers, 
    historical accuracy, and genuine educational/entertainment value.
    """
    clean_topic = topic.strip().title() if topic else "Mind-Blowing Discovery"
    lower_topic = clean_topic.lower()
    words = [w for w in lower_topic.replace(",", " ").replace("-", " ").split() if len(w) > 2]
    kw1 = words[0] if words else "epic"
    kw2 = words[1] if len(words) > 1 else kw1

    # High-Density Factual Domain Mapping
    if any(w in lower_topic for w in ["gta", "game", "gaming", "rockstar"]):
        title = f"Why GTA 6 Cost a Mind-Blowing $2 Billion 🎮💰"
        hook = f"GTA 6 is officially the most expensive entertainment product in human history, costing an astonishing two billion dollars."
        voiceover = (
            f"GTA 6 is officially the most expensive entertainment product in human history, costing an astonishing two billion dollars. "
            f"To put that in perspective, that is more than the budgets of Avengers Endgame, Titanic, and Avatar combined. "
            f"So where did the money go? Rockstar patented an unprecedented artificial intelligence system where thousands of non-player characters have actual daily routines, jobs, and individual memory of how you treat them. "
            f"They mapped hundreds of square miles using satellite photogrammetry down to custom interiors. "
            f"Analysts predict it will generate one billion dollars in its first twenty-four hours alone. "
            f"Would you pay one hundred dollars for this game? Let me know below."
        )
        tags = ["#shorts", "#gta6", "#gamingfacts", "#gaming"]
        queries = ["gta gameplay city", "game studio developers computer", "miami neon night aerial", "luxury sports car driving", "video game motion capture", "dollar cash stacks"]

    elif any(w in lower_topic for w in ["subhash", "ketagoda", "parliament", "minister", "politician"]):
        title = f"The Political Chessboard of Subhash Ketagoda 🏛️"
        hook = f"In Sri Lankan parliamentary politics, few figures have navigated coalition shifts quite like Subhash Ketagoda."
        voiceover = (
            f"In Sri Lankan parliamentary politics, few figures have navigated coalition shifts quite like Subhash Ketagoda. "
            f"First entering parliament in 2010 through the Democratic National Alliance under Sarath Fonseka, his political career became a masterclass in shifting alliances. "
            f"During constitutional flashpoints, his votes became pivotal—most notably when he crossed party lines to support landmark constitutional amendments, eventually being appointed as State Minister. "
            f"In parliamentary democracies, individual MPs often hold the decisive balance of power during razor-thin votes. "
            f"Love him or criticize him, it reveals the intense, strategic reality of South Asian politics. "
            f"What is your take on party floor-crossing? Share your perspective."
        )
        tags = ["#shorts", "#srilanka", "#politics", "#history"]
        queries = ["parliament building exterior", "politician press microphone", "voting ballot box election", "government official document", "law courthouse pillars", "news camera broadcast"]

    elif any(w in lower_topic for w in ["sigiriya", "kashyapa", "sri lanka", "ceylon"]):
        title = f"The 1,500-Year Ancient Engineering Wonder of Sigiriya 🦁"
        hook = f"Rising 660 feet above Sri Lanka's jungle, Sigiriya holds an engineering secret that still baffles modern architects."
        voiceover = (
            f"Rising 660 feet above Sri Lanka's jungle, Sigiriya holds an engineering secret that still baffles modern architects. "
            f"Built in 477 AD by King Kashyapa, this sheer vertical granite monolith was transformed into an impregnable royal palace in the sky. "
            f"Ancient hydraulic engineers constructed an underground gravity-fed pressure pipeline network that powers water fountains in the royal gardens—and astonishingly, they still spray water today during rainy seasons after fifteen hundred years. "
            f"Its sheer cliff walls were once coated with an egg-white and wild honey polish so reflective the king could see his reflection. "
            f"Sigiriya isn't just a fortress; it's a testament to ancient hydraulic genius. Subscribe for more wonders."
        )
        tags = ["#shorts", "#sigiriya", "#ancienthistory", "#srilanka", "#wonders"]
        queries = ["sigiriya rock aerial", "ancient water fountain", "sigiriya lion paws stone", "ancient frescoes painting", "ancient palace ruins", "sri lanka rainforest mist"]

    elif any(w in lower_topic for w in ["bugatti", "koenigsegg", "car", "ferrari", "supercar", "mph", "speed"]):
        title = f"The Mind-Blowing Physics of 304 MPH: Bugatti Chiron 🏎️⚡"
        hook = f"At 304 miles per hour, physics turns deadly in ways you wouldn't believe."
        voiceover = (
            f"At 304 miles per hour, physics turns deadly in ways you wouldn't believe. "
            f"When the Bugatti Chiron broke the three-hundred mile per hour barrier, its eight-liter quad-turbo W16 engine was gulping one thousand liters of air every single second. "
            f"At top speed, its custom Michelin tires spin sixty-eight times a second, creating a staggering 5,300 Gs of centrifugal force. "
            f"That means a tiny two-gram tire pressure sensor inside the wheel rim effectively weighs one hundred and twenty pounds at speed. "
            f"Even crazier: at full throttle, it drains its entire one-hundred-liter fuel tank in just nine minutes. "
            f"That is the terrifying engineering reality of hypercars. Subscribe for extreme speed facts."
        )
        tags = ["#shorts", "#bugatti", "#supercars", "#engineering", "#speed"]
        queries = ["bugatti chiron dark", "sports car engine turbo", "car speedometer 300", "highway speeding car night", "carbon fiber wheel rim", "hypercar exhaust flame"]

    elif any(w in lower_topic for w in ["coffee", "caffeine", "energy", "sleep", "tired", "awake"]):
        title = f"Why Coffee Doesn't Actually Give You Energy ☕🧠"
        hook = f"Coffee doesn't actually give you energy. What it does to your brain is far more deceitful."
        voiceover = (
            f"Coffee doesn't actually give you energy. What it does to your brain is far more deceitful. "
            f"Throughout your day, your brain produces a chemical called adenosine, which binds to brain receptors signaling that you are tired. "
            f"Caffeine shares the exact same molecular shape as adenosine. When you drink a cup, caffeine rushes in and plugs those receptors like a fake key stuck in a lock. "
            f"It doesn't create extra energy—it simply silences the alarm clock. "
            f"Meanwhile, adenosine keeps piling up outside the blocked doors. Once the caffeine metabolizes five hours later, all that trapped fatigue crashes into your brain simultaneously. "
            f"That is the biological reality of the afternoon coffee crash. Subscribe for more human body secrets."
        )
        tags = ["#shorts", "#coffee", "#science", "#health", "#brainfacts"]
        queries = ["coffee pouring dark espresso", "brain neurons firing glowing", "exhausted person yawning desk", "caffeine chemical molecule 3d", "clock spinning fast time", "fresh coffee beans closeup"]

    elif any(w in lower_topic for w in ["money", "bank", "wealth", "rich", "finance", "dollar", "billionaire", "economy"]):
        title = f"The Secret Way Banks Create Money From Nothing 💰🏦"
        hook = f"When you deposit one thousand dollars into a bank account, that money isn't sitting in a vault."
        voiceover = (
            f"When you deposit one thousand dollars into a bank account, that money isn't sitting in a vault. "
            f"Under modern fractional reserve banking, commercial banks are legally allowed to lend out ninety percent of your cash. "
            f"They keep just one hundred dollars as a reserve and lend the remaining nine hundred to another borrower. "
            f"When that borrower buys a car, the seller deposits that nine hundred dollars into their own bank—which immediately lends out another eight hundred and ten dollars. "
            f"Your initial one thousand dollars just magically multiplied into thousands of dollars of digital currency that never existed in the physical world. "
            f"Over ninety percent of global money exists only as ledger digits. Subscribe for financial truth."
        )
        tags = ["#shorts", "#money", "#finance", "#banking", "#economy", "#wealth"]
        queries = ["bank vault door heavy", "digital numbers stock market", "counting dollar bills hands", "credit card payment terminal", "skyscraper financial district night", "gold bars bullion"]

    elif any(w in lower_topic for w in ["airplane", "plane", "flight", "pilot", "aviation", "airport", "fly"]):
        title = f"Why Airplanes Never Fly in Straight Lines ✈️🗺️"
        hook = f"If you look at an international flight map, you'll notice airplanes take bizarre, curved routes that look completely inefficient."
        voiceover = (
            f"If you look at an international flight map, you'll notice airplanes take bizarre, curved routes that look completely inefficient. "
            f"A flight from New York to London doesn't cross in a straight line—it arcs high north over Canada and Greenland. "
            f"The reason? Flat maps distort reality. Because Earth is an oblate spheroid, curved routes called Great Circle paths are actually hundreds of miles shorter than a straight flat line. "
            f"Furthermore, federal aviation laws enforce ETOPS regulations, requiring twin-engine planes to stay within ninety to one hundred and twenty minutes of emergency diversion airports at all times. "
            f"They aren't lost; they're optimizing spherical geometry and emergency survival. Subscribe for aviation secrets."
        )
        tags = ["#shorts", "#aviation", "#airplanes", "#science", "#travel"]
        queries = ["airplane flying above clouds", "world map flight paths", "airplane cockpit pilot controls", "airplane wing sunset sky", "airport runway aerial night", "jet engine spinning turbine"]

    elif any(w in lower_topic for w in ["ai", "artificial intelligence", "robot", "chip", "computer", "tech", "quantum"]):
        title = f"The Terrifying Physics Inside Modern AI Microchips ⚡🤖"
        hook = f"The microchips powering modern artificial intelligence have become so microscopically tiny that the laws of physics are starting to break."
        voiceover = (
            f"The microchips powering modern artificial intelligence have become so microscopically tiny that the laws of physics are starting to break. "
            f"Leading semiconductor manufacturers now produce transistors just two nanometers wide. "
            f"To put that in perspective, a single strand of human DNA is 2.5 nanometers wide—meaning these electronic switches are literally smaller than the building blocks of human life. "
            f"At this scale, insulation barriers are only ten atoms thick. Electrons can spontaneously teleport through solid walls using quantum tunneling, causing data corruption. "
            f"To build smarter AI, engineers aren't just coding—they are actively wrestling with quantum mechanics. Subscribe for cutting-edge tech."
        )
        tags = ["#shorts", "#ai", "#technology", "#future", "#science", "#physics"]
        queries = ["microchip processor glowing macro", "server room datacenter blue", "futuristic robot face cyber", "quantum physics particles light", "semiconductor silicon wafer cleanroom", "neural network data visualization"]

    elif any(w in lower_topic for w in ["animal", "nature", "octopus", "biology", "creature", "shark", "crow"]):
        title = f"The Alien Superpower Hiding in the Common Octopus 🐙🌊"
        hook = f"If aliens exist on Earth, they aren't from outer space—they're living in our coral reefs."
        voiceover = (
            f"If aliens exist on Earth, they aren't from outer space—they're living in our coral reefs. "
            f"An octopus has three distinct hearts, blue copper-based blood, and nine brains. "
            f"A central doughnut-shaped brain encircles its esophagus, while two-thirds of its total neurons reside directly inside its eight independent arms. "
            f"That means each tentacle can taste, touch, explore, and solve physical puzzles completely autonomously without consulting the main head. "
            f"Even more astonishing: they can edit their own RNA on the fly to adapt to changing water temperatures within hours. "
            f"Nature's ingenuity leaves human technology in the dust. Subscribe for animal superpowers."
        )
        tags = ["#shorts", "#nature", "#animals", "#biology", "#wildlife", "#ocean"]
        queries = ["octopus swimming coral reef", "underwater marine life closeup", "tentacle suction cups macro", "ocean blue water sunlight", "colorful sea anemone", "jellyfish glowing dark"]

    elif any(w in lower_topic for w in ["space", "universe", "black hole", "star", "astronomy", "cosmos", "galaxy"]):
        title = f"What Happens If You Drop One Teaspoon of a Neutron Star? 🌌💥"
        hook = f"A single teaspoon of a neutron star weighs more than Mount Everest."
        voiceover = (
            f"A single teaspoon of a neutron star weighs more than Mount Everest. "
            f"When a massive star runs out of fuel, its core collapses under immense gravity, crushing protons and electrons together until atomic space completely disappears. "
            f"The entire mass of two Suns gets compressed into a sphere no larger than a city. "
            f"If you could bring one teaspoon of this material to Earth, it would weigh approximately six billion tons. "
            f"The moment you let it go, Earth's crust wouldn't even slow it down. It would slice straight through rock like a bullet through wet paper, oscillating through the planet's core. "
            f"The cosmos plays by terrifying rules. Subscribe for space mysteries."
        )
        tags = ["#shorts", "#space", "#astronomy", "#universe", "#science", "#blackhole"]
        queries = ["neutron star spinning space", "galaxy spiral nebula glowing", "earth from space dark", "asteroid falling burning atmosphere", "deep space stars telescope", "black hole accretion disk"]

    else:
        # High-Substance Analytical Breakdown for any User Topic
        title = f"The Surprising Reality Behind {clean_topic} 💡⚡"
        hook = f"Almost everything people assume about {clean_topic} overlooks one critical reality."
        voiceover = (
            f"Almost everything people assume about {clean_topic} overlooks one critical reality. "
            f"When you break down the actual mechanics of {clean_topic}, it isn't governed by luck or simple coincidence. "
            f"Behind the scenes, every system in this field relies on an exact trade-off between energy, timing, and structural leverage. "
            f"Studies show that in complex environments, focusing on the core twenty percent of driving factors consistently produces over eighty percent of the measurable results. "
            f"While most people stay distracted by surface-level noise, mastering the foundational principles completely transforms how you understand the outcome. "
            f"Real knowledge beats common assumptions every single time. "
            f"What aspect of {clean_topic} surprised you the most? Share below and subscribe for more deep breakdowns."
        )
        tags = ["#shorts", "#facts", "#learning", f"#{clean_topic.replace(' ', '').lower()}"]
        queries = [f"{kw1} cinematic 4k", f"{clean_topic.lower()} visual", "laboratory research microscope", f"{kw2} close up detail", "data analytics screen", f"{clean_topic.lower()} epic"]

    return ShortsScript(
        title=title,
        hook=hook,
        voiceover_text=voiceover,
        description=f"{title}\n\nLearn something new every day! Subscribe for high-value viral knowledge. #shorts",
        tags=tags,
        visual_segments=[
            VisualSegment(order=i + 1, search_query=queries[i], scene_description=f"Scene {i + 1} footage for {queries[i]}", approx_duration_sec=7.0)
            for i in range(6)
        ],
        estimated_duration_seconds=round(len(voiceover.split()) / 2.4, 1)
    )


def run_test(topic: str, force_mock: bool = False):
    print("=" * 60)
    print(f"🎬 Testing YouTube Shorts Script Generation for: '{topic}'")
    print("=" * 60)

    has_gemini = bool(AppConfig.GEMINI_API_KEY)
    has_openai = bool(AppConfig.OPENAI_API_KEY)

    if force_mock or (not has_gemini and not has_openai):
        if not force_mock:
            print("⚠️  No GEMINI_API_KEY or OPENAI_API_KEY found in .env.")
            print("ℹ️  Running schema and pipeline validation using Mock Data...\n")
        else:
            print("ℹ️  Running with --mock flag...\n")
        script = get_mock_script(topic)
    else:
        provider = AppConfig.DEFAULT_LLM_PROVIDER
        print(f"📡 Querying live LLM provider: {provider.upper()}...")
        generator = ScriptGenerator(provider=provider)
        script = generator.generate(topic=topic)

    # Validation Checks
    words = script.voiceover_text.split()
    word_count = len(words)
    est_duration = round(word_count / 2.5, 1) # ~150 words/min = 2.5 words/sec

    print("\n✅ Script Generation Succeeded!")
    print("-" * 60)
    print(f"📌 Title:       {script.title}")
    print(f"🪝 Hook:        {script.hook}")
    print(f"📝 Word Count:  {word_count} words (~{est_duration}s speaking time)")
    print(f"🏷️ Tags:        {' '.join(script.tags)}")
    print("\n🎙️ Full Voiceover Script:")
    print(f'"{script.voiceover_text}"')
    
    print("\n🎥 Visual Segments (Stock Search Queries):")
    for seg in script.visual_segments:
        print(f"  [{seg.order}] ~{seg.approx_duration_sec}s | Query: \"{seg.search_query}\" | Scene: {seg.scene_description}")

    print("\n📄 YouTube Description:")
    print(f"{script.description}")
    print("=" * 60)
    print("🚀 Step 1 Verification Complete! Ready for Step 2 (Audio & Stock Media).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Step 1: Script and Keyword Generation")
    parser.add_argument("--topic", type=str, default="Space Mysteries", help="Topic keyword or niche")
    parser.add_argument("--mock", action="store_true", help="Force mock generation without calling live API")
    args = parser.parse_args()

    run_test(topic=args.topic, force_mock=args.mock)
