from __future__ import annotations
from dataclasses import dataclass, field
from dotenv import load_dotenv
import os

load_dotenv()

@dataclass
class Config:
    youtube_api_key: str = os.getenv('YOUTUBE_API_KEY','').strip()
    output_dir: str = os.getenv('OUTPUT_DIR','outputs')
    db_path: str = os.getenv('DATABASE_PATH','outputs/trend_radar_x.db')
    max_channel_subs: int = int(os.getenv('MAX_CHANNEL_SUBS','100000'))
    min_views: int = int(os.getenv('MIN_VIEWS','1000'))
    days_back: int = int(os.getenv('DAYS_BACK','7'))
    region_code: str = os.getenv('REGION_CODE','US')
    max_results_per_query: int = int(os.getenv('MAX_RESULTS_PER_QUERY','25'))
    max_total_candidates: int = int(os.getenv('MAX_TOTAL_CANDIDATES','500'))
    min_production_score: int = int(os.getenv('MIN_PRODUCTION_SCORE','70'))
    min_auto_score: int = int(os.getenv('MIN_AUTO_SCORE','75'))
    my_channel_url: str = os.getenv('MY_CHANNEL_URL','https://youtube.com/@arnovcs-v2m')
    asset_source_dir: str = os.getenv('ASSET_SOURCE_DIR','assets/source')
    asset_sound_dir: str = os.getenv('ASSET_SOUND_DIR','assets/sounds')
    # Keep this short by default to save API quota. Add more in settings if needed.
    queries: list[str] = field(default_factory=lambda: [
        'roblox shorts',
        'roblox facts shorts',
        'roblox secrets shorts',
        'roblox update shorts',
        'roblox funny shorts',
        'roblox meme shorts',
        'animal hospital roblox shorts',
        'grow a garden roblox shorts',
        'steal a brainrot roblox shorts',
        '99 nights in the forest roblox shorts',
    ])

CONFIG = Config()
