# Story Scout v1.1 hotfix 2

The remaining Internal Server Error was caused by a missing:

```python
import re
```

The English-language detector calls `re.findall()` and `re.search()` when the
page loads. Python syntax validation did not catch this because it is a runtime
NameError.

This patch also includes migration support for older candidate rows.

Replace:

```text
radar/story_scout.py
```

Then completely stop and restart Flask:

```powershell
Ctrl + C
py app.py
```

To verify the correct file is loaded:

```powershell
py -c "import radar.story_scout as s; print(s.__file__); print(s.scout_stats())"
```
