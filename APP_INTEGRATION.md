# APP.PY INTEGRATION — two direct edits

Your source modules are ready after copying the `radar` folder.

## 1. Add the navigation item

Find `NAV_ITEMS = [` near the top of `app.py`.

Add this entry near Creator AI:

```python
("/classification-review", "Classification Review"),
```

For example:

```python
NAV_ITEMS = [
    ("/studio", "Studio"),
    ("/clips", "Clip Review"),
    ("/recommendations", "Recommended Shorts"),
    ("/auto-studio", "Auto Studio"),
    ("/creator-ai", "Creator AI"),
    ("/classification-review", "Classification Review"),
    ...
]
```

## 2. Register the routes

Near the bottom of `app.py`, immediately before the Creator AI route registration,
add:

```python
from radar.classification_web import register_classification_routes

register_classification_routes(
    app,
    BASE,
    page,
    esc,
    load_recommendations,
)
```

The end of the file should look roughly like:

```python
from radar.channel_web import register_channel_routes
register_channel_routes(app, page, esc)

from radar.classification_web import register_classification_routes
register_classification_routes(
    app,
    BASE,
    page,
    esc,
    load_recommendations,
)

from radar.creator_web import register_creator_routes
register_creator_routes(
    app,
    BASE,
    page,
    render_stats,
    load_recommendations,
    esc,
)
```

## 3. Run

```powershell
py trend_radar.py
py app.py
```

Open:

```text
http://127.0.0.1:5000/classification-review
```

Correct uncertain videos, then rerun `py trend_radar.py`.
