# Automatic Channel Feedback

This upgrade automatically syncs public performance for `@arnovcs-v2m` every six hours and uses it to personalize Creator AI confidence.

Stored automatically:
- views, likes and comments
- views per hour
- like and comment rates
- inferred format and hook type
- repeated snapshots over time
- personal multipliers for formats and hooks

Open `http://127.0.0.1:5000/my-channel` after starting `py app.py`.

An API key cannot access private Studio metrics such as Stayed to watch, average percentage viewed, retention, or subscribers gained per video. Those require one-time YouTube Analytics OAuth authorization.
