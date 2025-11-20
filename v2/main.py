import aiohttp
import os
import asyncio
import aiofiles
import json
import shutil
from requests_html import AsyncHTMLSession
from typing import List
from tqdm.asyncio import tqdm_asyncio
from collections import namedtuple

# uvloop makes asyncio 2-4x faster. 
# linux/macos only: doesn't support windows :(
try:
    import uvloop
    uvloop.install()
except Exception:
    print("[INFO] uvloop not available on windows :(")
    
Image = namedtuple("Image", ["url", "filepath"])
ImagesWithCount = namedtuple("ImagesWithCount", ["count", "images"])


"""
Archives a Rec Room account tagged photos and tagged photos.

[account_id]/
├─ photos/
├─ photos_data/
├─ tagged/
├─ tagged_data/
├─ readme.txt

Usage:
```py
account_id = 1700372
await ImageDownloader.create(account_id)
await ImageDownloader.archive()
```
"""
class ImageDownloader:
    HOST = "https://apim.rec.net/apis/api/images/"
    TAGGED_ENDPOINT = "v3/feed/player"
    PHOTOS_ENDPOINT = "v4/player"

    CONCURRENCY = 30 
    TIMEOUT = aiohttp.ClientTimeout(total=30)

    html_session: AsyncHTMLSession = None
    session: aiohttp.ClientSession = None
    semaphore: asyncio.Semaphore = None
    account_id: int = None

    photos_count: int = 0
    tagged_count: int = 0
    total_count: int = 0

    images_to_download: List[Image] = []


    def __init__(self, account_id: int):
        self.account_id = account_id


    """
    Creates an image downloader instance.
    """
    @classmethod
    async def create(cls, account_id: int) -> ImageDownloader:
        self = ImageDownloader(account_id)

        self._create_directories()
        self._copy_shared_files()
        self.session = aiohttp.ClientSession()
        self.semaphore = asyncio.Semaphore(self.CONCURRENCY)
        self.html_session = AsyncHTMLSession()

        return self
    

    """
    Closes the sessions gracefully
    """
    async def close(self) -> None:
        if self.session:
            await self.session.close()
            self.session = None
        if self.html_session:
            await self.html_session.close()
            self.html_session = None

    
    """
    Archives account's taken photos and tagged photos.

    [account_id]/
    ├─ photos/
    ├─ photos_data/
    ├─ tagged/
    ├─ tagged_data/
    ├─ readme.txt

    Closes sessions once done!
    """
    async def archive(self, ask_for_confirmation: bool = True) -> None:
        print("Gathering image data. This can take a moment...")
        await self._gather_images()

        if ask_for_confirmation and self._prompt_for_confirmation() == False:
            print("Cancelled!")
            return
        
        print("Downloading...")

        download_count = await self._download_all()

        print(f"\nFinished archiving photos! Account: {self.account_id}")
        print(f"Downloaded {download_count} / {self.total_count} images.")

        await self.close()
        

    """
    Asks the user if they want to proceed with downloading the photos.
    Returns answer as a boolean.
    """
    def _prompt_for_confirmation(self) -> bool:
        print(f"You're about to download {self.total_count:,} photos in total.")
        print(f"Taken photos: {self.photos_count:,}")
        print(f"Tagged photos: {self.tagged_count:,}")
        print(f"Account ID: {self.account_id}\n")

        answer = ""
        while answer != "y":
            answer = input("Proceed? (y/n) > ").lower()
            if answer == "n":
                return False
            
        return True
    
    
    """ 
    Creates archive directories 
    """
    def _create_directories(self) -> None:
        assert self.account_id != None, "Account ID missing!"

        root_path = str(self.account_id)
        directories = ("photos", "tagged", "photos_data", "tagged_data")

        for name in directories:
            dir = os.path.join(root_path, name)
            os.makedirs(dir, exist_ok=True)


    """
    Copies shared files into the archive
    """
    def _copy_shared_files(self) -> None:
        root_path = str(self.account_id)
        shared_files_path = "shared_files"

        assert os.path.exists(root_path), "Directories missing!"
        assert os.path.exists(shared_files_path), "Shared files missing!"

        shutil.copytree(shared_files_path, root_path, dirs_exist_ok=True)


    """
    Gathers taken photos and tagged photos. 
    Stores total count of photos in instance variable total_count
    """
    async def _gather_images(self) -> None:
        await self._download_image_data(is_tagged=True)
        await self._download_image_data(is_tagged=False)
        self.total_count = self.photos_count + self.tagged_count


    """
    Downloads the public image data from RecNet. Stores images in images_to_download list.
    Returns image count.

    ARGS
    is_tagged: 
        True: grabs images player is tagged in
        False: grabs images player has taken
    """
    async def _download_image_data(self, is_tagged: bool) -> int:
        PAGE_MAX_COUNT = 1000
        page = 0
        while True:
            images_json = await self._fetch_image_data(is_tagged, page)
            self._save_image_data(is_tagged, images_json, page)

            images_with_count = self._convert_images_json_to_tuples(images_json, is_tagged)

            self.images_to_download += images_with_count.images

            if images_with_count.count < PAGE_MAX_COUNT:
                break

            page += 1

        if is_tagged:
            return self.tagged_count
        else:
            return self.photos_count


    """
    Saves raw image data to archive
    """
    def _save_image_data(self, is_tagged: bool, image_data: List[dict], page: int) -> None:
        filepath = os.path.join(
            str(self.account_id), 
            "tagged_data" if is_tagged else "photos_data", 
            f"{page}.json"
        )

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(image_data, f, ensure_ascii=False, indent=4)


    """
    Returns the URL for image data
    1 page = 1,000 images
    """
    def _get_image_data_url(self, is_tagged: bool, page: int) -> str:
        endpoint = self.TAGGED_ENDPOINT if is_tagged else self.PHOTOS_ENDPOINT
        url = f"{self.HOST}/{endpoint}/{self.account_id}?take=1000&skip={page*1000}"
        return url


    """
    Fetches image json data. 
    1 page = 1,000 images.
    """
    async def _fetch_image_data(self, is_tagged: bool, page: int) -> List[dict]:
        url = self._get_image_data_url(is_tagged, page)
        html = await self._fetch_html_data(url)

        # Image data is located inside pre element
        raw_images_json = html.find("pre", first=True).text
        images_json = json.loads(raw_images_json)

        return images_json


    """
    Fetches HTML data with JavaScript rendering
    This is to work around Rec Room's skid-proof API
    """
    async def _fetch_html_data(self, url: str) -> str:
        resp = await self.html_session.get(url)
        # API requires JavaScript rendering in order to return data. Otherwise returns 403.
        await resp.html.arender(timeout=20)
        return resp.html
    

    """
    Turns image data into a indexable filename
    """
    def _format_filename(self, image_data: dict) -> str:
        image_id = image_data["Id"]
        creation_date = self._shorten_creation_timestamp(image_data["CreatedAt"])
        player_id = image_data["PlayerId"]
        room_id = image_data["RoomId"]
        image_name = image_data['ImageName']

        filename = f"{creation_date} [{image_id}] [player: {player_id}] [room: {room_id}] {image_name}"
        filename = self._add_png_extension_if_missing(filename)

        return filename
    

    """
    Shortens a ISO 8601 timestamp to just the date
    ex: 2023-10-12T20:24:50.0168341Z -> 2023-10-12
    """
    def _shorten_creation_timestamp(self, creation_timestamp: str) -> str:
        if "T" in creation_timestamp:
            return creation_timestamp.split("T")[0]
        return creation_timestamp

    """
    Takes in a list of image data and returns images with the count.
    Also counts image count and stores in the respective instance image count variable.
    """
    def _convert_images_json_to_tuples(self, images_json: List[dict], is_tagged: bool) -> ImagesWithCount:
        images = []
        count = 0
        for image_data in images_json:
            filename = self._format_filename(image_data)
            url = f"https://img.rec.net/{image_data['ImageName']}"

            filepath = os.path.join(str(self.account_id), "tagged" if is_tagged else "photos", filename)

            image = Image(url, filepath)
            images.append(image)

            if is_tagged:
                self.tagged_count += 1
            else:
                self.photos_count += 1
            count += 1

        images_with_count = ImagesWithCount(
            count=count,
            images=images
        )

        return images_with_count


    """
    Adds a .png extension to filename if missing an extension
    """
    def _add_png_extension_if_missing(self, filename: str) -> str:
        if "." not in filename:
            filename += ".png"
        return filename


    """
    Downloads all images from instance variable images_to_download
    Returns amount of photos successfully downloaded
    """
    async def _download_all(self) -> int:
        assert self.total_count != 0, "No photos to download!"

        tasks = [self._download_image(image) for image in self.images_to_download]
        results = await tqdm_asyncio.gather(*tasks)
        
        return sum(results)


    """
    Downloads an image in chunks. Returns true if successful.
    """
    async def _download_image(self, image: Image) -> bool:
        async with self.semaphore:
            try:
                async with self.session.get(image.url) as resp:
                    resp.raise_for_status()

                    async with aiofiles.open(image.filepath, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 32):
                            await f.write(chunk)

                return True
            except Exception as e:
                print(f"Error downloading {image.url}: {e}")
                return False
            

async def main():
    downloader = await ImageDownloader.create(account_id=1203872)
    await downloader.archive(ask_for_confirmation=True)


asyncio.run(main())