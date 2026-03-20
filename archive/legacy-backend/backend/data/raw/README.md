# Raw data (not in Git)

The file `hotel_bookings.csv` is used as the reference dataset for RAG and predictions. It is **not** committed (size limit; see `.gitignore`).

To regenerate `processed/patterns.json`:

1. Obtain the [Hotel Booking Demand dataset](https://www.kaggle.com/datasets/jessemostipak/hotel-booking-demand) (or equivalent).
2. Place `hotel_bookings.csv` in this directory.
3. Run: `python backend/scripts/derive_covers.py`

The deployed app and HuggingFace Space use only `processed/patterns.json`; the raw CSV is needed only for data preparation.
