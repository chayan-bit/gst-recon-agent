# Phone-photo protocol (about 15 minutes)

Goal: replace the clean 200 dpi raster of 10 documents with real phone-camera photos under 3 lighting conditions, so the real-world split also measures real capture noise.
The 10 documents cover all 7 formats and the main discrepancy kinds; their order is in `data/realworld/print/PHOTO_ORDER.txt`.

## 1. Print (3 minutes)

    cd ~/gst-recon-realworld/data/realworld/print            # on kratos, after python -m realworld.build
    pdfunite $(cat PHOTO_ORDER.txt) photo_pack.pdf            # 10 pages, one document per page

Copy `photo_pack.pdf` to the Mac (`scp`), print it single-sided on plain A4, default scaling ("fit to page" is fine).
The POS receipt (page 3) prints as a narrow strip; leave it on the A4 sheet, do not cut.

## 2. Photograph (10 minutes, 30 photos)

Phone camera app, default settings, flash off.
On iPhone set Settings > Camera > Formats > **Most Compatible** first, so photos are JPEG (HEIC is not read).
Take the pages in the order of `PHOTO_ORDER.txt`, one photo per page, the whole page in frame.

| Pass | Folder | Lighting | How to hold the phone |
|---|---|---|---|
| 1 | `light1` | Office ceiling light, page flat on a desk | Straight above the page, as a person scanning a bill would |
| 2 | `light2` | Daylight near a window, light falling from one side | Slight tilt (about 10-20 degrees), your hand's shadow may touch the page edge |
| 3 | `light3` | One desk lamp or dim evening room light | Handheld, no special care; slight blur and warm cast are fine |

Rules: do not crop, rotate, filter or "scan" the photos in any app; do not retake a photo because it looks bad (bad photos are the point); keep exactly 10 photos per pass.
If a photo is truly unusable (page cut off), retake that one immediately so the order stays the same.

## 3. Hand over (2 minutes)

Put the photos in three folders named `light1`, `light2`, `light3` (AirDrop to the Mac, then into `~/Downloads/rw-photos/light1` etc.) and tell Claude where they are.
File names can stay as the phone wrote them (`IMG_4512.JPG`, ...): within each folder they are sorted by name, which is capture order, and matched to `PHOTO_ORDER.txt`.
Alternatively name each file `<case>_<doc>.jpg` (for example `rw01_D02.jpg`); named files are matched by name.

## 4. Build (done by Claude on kratos)

    rsync -a ~/Downloads/rw-photos/ user@gpu-host:gst-recon-realworld/photos/
    python -m realworld.build --images-dir photos/light1 --out data/realworld_photo/light1    # and light2, light3

Each output directory has the same 12 cases; the 10 photographed documents are OCR'd from the photos (`delivery: photo`, source label "phone photo, OCR text", split `realworld_photo`), the other 26 stay clean scans.
The photos are synthetic-party documents, so they carry no real client data, but they stay out of git (`data/` is ignored).
