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
    print("INFO: uvloop not available on windows :(")
    
Image = namedtuple("Image", ["url", "filepath"])

class ImageDownloader:
    HOST = "https://apim.rec.net/apis/api/images/"
    TAGGED_ENDPOINT = "v3/feed/player"
    PHOTOS_ENDPOINT = "v4/player"

    CONCURRENCY = 50 
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


    @classmethod
    async def create(cls, account_id: int):
        self = ImageDownloader(account_id)

        self.__create_directories()
        self.__copy_shared_files()
        self.session = aiohttp.ClientSession()
        self.semaphore = asyncio.Semaphore(self.CONCURRENCY)
        self.html_session = AsyncHTMLSession()

        return self
    

    # Closes the sessions gracefully
    async def close(self):
        if self.session:
            await self.session.close()
        if self.html_session:
            await self.html_session.close()

    
    # Archives given account's taken photos and tagged photos
    async def archive(self, ask_for_confirmation: bool = True):
        await self.gather_images()

        if ask_for_confirmation and self.prompt_for_confirmation() == False:
            print("Cancelled!")
            return
        
        await self.download_all()
        

    # Asks the user if they want to proceed with downloading the photos.
    # Returns answer as a boolean.
    def prompt_for_confirmation(self) -> bool:
        print(f"You're about to download {self.total_count} photos in total.")
        print(f"Taken photos: {self.photos_count}")
        print(f"Tagged photos: {self.tagged_count}")
        print(f"Account ID: {self.account_id}\n")

        answer = ""
        while answer != "y":
            answer = input("Proceed? (y/n) > ").lower()
            if answer == "n":
                return False
            
        return True


    # Creates archive directories
    def __create_directories(self):
        assert self.account_id != None, "Account ID missing!"

        root_path = str(self.account_id)
        directories = ("photos", "tagged", "photos_data", "tagged_data")

        for name in directories:
            dir = os.path.join(root_path, name)
            os.makedirs(dir, exist_ok=True)


    # Copies shared files into the archive
    def __copy_shared_files(self):
        root_path = str(self.account_id)
        shared_files_path = "shared_files"

        assert os.path.exists(root_path), "Directories missing!"
        assert os.path.exists(shared_files_path), "Shared files missing!"

        shutil.copytree(shared_files_path, root_path, dirs_exist_ok=True)


    # Gathers taken photos and tagged photos. 
    # Stores total count of photos in instance variable total_count
    async def gather_images(self):
        await self.download_image_data(is_tagged=True)
        await self.download_image_data(is_tagged=False)
        self.total_count = self.photos_count + self.tagged_count


    """
    Downloads the public image data from RecNet. Stores images in images_to_download list.
    Returns image count.

    ARGS
    is_tagged: 
        True: grabs images player is tagged in
        False: grabs images player has taken
    """
    async def download_image_data(self, is_tagged: bool) -> int:
        endpoint = self.TAGGED_ENDPOINT if is_tagged else self.PHOTOS_ENDPOINT
        url = f"{self.HOST}/{endpoint}/{self.account_id}"

        # Cannot use HTMLSession within an existing event loop
        html = await self.__fetch_html_data(url)

        # Image data is located inside pre element
        raw_images_json = html.find("pre", first=True).text
        images_json = json.loads(raw_images_json)

        self.images_to_download += self.__convert_images_json_to_tuples(images_json, is_tagged)

        if is_tagged:
            return self.tagged_count
        else:
            return self.photos_count
        
    
    async def __fetch_html_data(self, url: str) -> str:
        resp = await self.html_session.get(url)
        # API requires JavaScript rendering in order to return data. Otherwise returns 403.
        await resp.html.arender(timeout=20)
        return resp.html
    

    # Turns image data into a indexable filename
    def __format_filename(self, image_data: dict) -> str:
        image_id = image_data["Id"]
        creation_date = self.__shorten_creation_timestamp(image_data["CreatedAt"])
        player_id = image_data["PlayerId"]
        room_id = image_data["RoomId"]
        image_name = image_data['ImageName']

        filename = f"{creation_date} [{image_id}] [player: {player_id}] [room: {room_id}] {image_name}"
        filename = self.__add_png_extension_if_missing(filename)

        return filename
    

    # Shortens a ISO 8601 timestamp to just the date
    # ex: 2023-10-12T20:24:50.0168341Z -> 2023-10-12
    def __shorten_creation_timestamp(self, creation_timestamp: str) -> str:
        if "T" in creation_timestamp:
            return creation_timestamp.split("T")[0]
        return creation_timestamp


    # Takes in a list of image data and returns a list of tuples. 
    # Also counts image count and stores in the respective instance image count variable.
    def __convert_images_json_to_tuples(self, images_json: List[dict], is_tagged: bool) -> List[Image]:
        images = []
        for image_data in images_json:
            filename = self.__format_filename(image_data)
            url = f"https://img.rec.net/{image_data['ImageName']}"

            filepath = os.path.join("tagged" if is_tagged else "photos", filename)
            filepath = os.path.join(str(self.account_id), filepath)

            image = Image(url, filepath)
            images.append(image)

            if is_tagged:
                self.tagged_count += 1
            else:
                self.photos_count += 1

        return images


    def __add_png_extension_if_missing(self, filename) -> str:
        if "." not in filename:
            filename += ".png"
        return filename


    # Downloads all images from instance variable images_to_download
    async def download_all(self):
        total_count = self.photos_count + self.tagged_count
        assert total_count != 0, "No photos to download!"

        print(f"Downloading {total_count} photos...")

        tasks = [self.download_image(image) for image in self.images_to_download]
        results = await tqdm_asyncio.gather(*tasks)

        print(f"\nFinished archiving photos! Account: {self.account_id}")
        print(f"Downloaded {self.photos_count} photos and {self.tagged_count} tagged photos.")


    # Downloads an image in chunks
    async def download_image(self, image: Image):
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
    downloader = await ImageDownloader.create(account_id=1700372)
    await downloader.archive(ask_for_confirmation=True)
    await downloader.close()

asyncio.run(main())