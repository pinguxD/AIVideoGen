from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class Config:
    youtube_api_key: str = os.getenv('YOUTUBE_API_KEY','').strip()
    my_channel_id: str = os.getenv('MY_CHANNEL_ID','').strip()
    days_back: int = int(os.getenv('DAYS_BACK','7'))
    region_code: str = os.getenv('REGION_CODE','US').strip() or 'US'
    max_results_per_query: int = int(os.getenv('MAX_RESULTS_PER_QUERY','20'))
    max_total_candidates: int = int(os.getenv('MAX_TOTAL_CANDIDATES','250'))
    max_channel_subs: int = int(os.getenv('MAX_CHANNEL_SUBS','50000'))
    min_views: int = int(os.getenv('MIN_VIEWS','1000'))
    min_production_score: int = int(os.getenv('MIN_PRODUCTION_SCORE','60'))
    min_auto_score: int = int(os.getenv('MIN_AUTO_SCORE','50'))
    mine_raw_gameplay: bool = os.getenv('MINE_RAW_GAMEPLAY','false').lower() in ['1','true','yes','on']
    max_mined_clips_per_file: int = int(os.getenv('MAX_MINED_CLIPS_PER_FILE','8'))
    mined_clip_length_seconds: int = int(os.getenv('MINED_CLIP_LENGTH_SECONDS','9'))
    output_dir: str = 'outputs'
    db_path: str = 'outputs/trend_radar_x.db'
    queries: list[str] = field(default_factory=lambda: [
        'roblox shorts', 'roblox funny shorts', 'roblox meme shorts',
        'roblox facts shorts', 'roblox secrets shorts', 'roblox myth shorts',
        'animal hospital roblox shorts', 'guess the voice roblox shorts',
        'grow a garden roblox shorts', '99 nights in the forest roblox shorts',
        'steal a brainrot roblox shorts', 'roblox horror shorts',
        'doors roblox shorts', 'pressure roblox shorts', 'new roblox game shorts'
    ])

CONFIG = Config()
