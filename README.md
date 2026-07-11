# Human Analysis Correction System

This is the next layer for Full Video Intelligence.

It allows you to correct:

- overall format;
- hook type;
- video goal;
- main emotion;
- ending type;
- human/AI/no voice;
- voice style;
- caption style;
- meme usage;
- sound usage;
- exact timeline events such as memes, sounds, zooms, captions and reveals.

Every correction is stored permanently in:

```text
outputs/analysis_feedback.db
```

It also generates corrected copies of the analyzer output and production plan:

```text
outputs/corrected_reference_analysis/
```

This is important because the correction is not only displayed in the website.
It changes the downstream production plan. A fact/list correction, for example,
turns off soundboard selection so Creator AI cannot turn it into a Guess Voice
project again.

The learning-statistics table shows how many corrected examples exist for each
label. These become the training/calibration dataset for future classifier/model
upgrades.
