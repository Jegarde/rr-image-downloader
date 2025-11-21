# Rec Room Image Downloader
Archive your photos and tags before it's too late!

## Archive
- All public photos and tags separated in their respective directories
- File names contain
  - publish date first so they're sorted by date
  - player ID of user who took the photo so you can search by player (ID from RecNetBot)
  - image ID so you can access the RecNet post
  - the original image name from RR's image server so you can directly access it from there if you want
- The raw image json data split in chunks of 1,000
  - You can search for specific photos with the raw data if you have some scripting knowledge
  - Raw data contains tagged players
- A readme with instructions for all the above (except a scripting tutorial :P)

<img width="169" height="160" alt="image" src="https://github.com/user-attachments/assets/0cf9ef60-006c-4d5c-bb4d-1a27c86ced24" />

<img width="1178" height="317" alt="image" src="https://github.com/user-attachments/assets/933f1915-7969-43a4-b64d-4f4e72194170" />

## Usage
*assuming you have basic Python knowledge*

Made and tested on Python 3.12. Virtual environment is encouraged.

Install dependencies:
`pip install -r requirements.txt`

Run script:
`python image_downloader.py [*account_ids]`

Example:
`python image_downloader.py 1700372`

You can input multiple account ids to archive them all.
