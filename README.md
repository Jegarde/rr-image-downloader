# Rec Room Image Downloader
Archive your photos and tags before it's too late!

[Buy me a coffee](https://ko-fi.com/jegarde) if you found this useful and you're feeling generous. :)

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

<img width="169" height="160" alt="image" src="https://github.com/user-attachments/assets/0cf9ef60-006c-4d5c-bb4d-1a27c86ced24" />

<img width="1178" height="317" alt="image" src="https://github.com/user-attachments/assets/933f1915-7969-43a4-b64d-4f4e72194170" />

## Installation
Download the source from this repository.

- Install Python: https://realpython.com/installing-python/
- Install pip: https://pip.pypa.io/en/stable/installation/
- Install pipx: https://pipx.pypa.io/latest/installation/

In the source directory, run: `pipx install .`

It will then install `rr_image_downloader` as a globally available command!

## Usage
Run script: `rr_image_downloader [*account_ids]`

Example: `rr_image_downloader 1700372`

You can input multiple account ids to archive them all.

