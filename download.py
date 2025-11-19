import aiohttp
import os
import asyncio
import aiofiles
import requests
from tqdm.asyncio import tqdm_asyncio
from secret import API_KEY

# linux/macos
try:
    import uvloop
    uvloop.install()
except Exception:
    print("uvloop not available :(")


HEADERS = {
    "Cache-Control": "nocache",
    "Api-Version": "v1",
    "Ocp-Apim-Subscription-Key": API_KEY
}
FOLDER = "images"

CONCURRENCY = 50 
TIMEOUT = aiohttp.ClientTimeout(total=30)

# id -> name
ROOMS = {

}

# id -> name
PLAYERS = {

}

PLAYER_IDS = set()

async def download_all(session, image_urls):
    os.makedirs(FOLDER, exist_ok=True)

    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [download_image(session, img_tuple, sem) for img_tuple in image_urls]
    results = await tqdm_asyncio.gather(*tasks)

    image_count = len(image_urls)
    print(f"\nDownloaded {sum(results)} / {image_count} images")


async def download_image(session, img_tuple, sem):
    url = img_tuple[0]
    filepath = img_tuple[1]

    async with sem:
        try:
            async with session.get(url) as resp:
                resp.raise_for_status()

                async with aiofiles.open(filepath, "wb") as f:
                    async for chunk in resp.content.iter_chunked(1024 * 32):
                        await f.write(chunk)

            return True
        except Exception as e:
            print(f"Error downloading {url}: {e}")
            return False


async def gather_image_urls(session, id) -> list:
    MAX_IMAGES_PER_RESPONSE = 1000
    image_urls = []
    total_image_count = 0
    skip = 0

    while True:
        async with session.get(f'https://apim.rec.net/public/images/player/{id}?take={MAX_IMAGES_PER_RESPONSE}&skip={skip}') as response:
            resp = await response.json()
            image_count = len(resp)
            total_image_count += image_count
            skip += total_image_count

            for image_object in resp:
                image_urls.append(create_image_tuple(image_object))

            if image_count != MAX_IMAGES_PER_RESPONSE:
                break

    return image_urls

"""
TUPLE: (image url, filepath)
"""
def create_image_tuple(image_object):
    image_name = image_object["ImageName"]
    creation_date = image_object["CreatedAt"].split("T")[0]

    filename = f"{creation_date} [{image_object['Id']}] {image_name}"


    filename = add_png_extension_if_missing(filename)
    filepath = os.path.join(FOLDER, filename)

    return (
        "https://img.rec.net/" + image_name,
        filepath
    )

def fetch_player_name(player_id):
    if player_id in PLAYERS:
        return PLAYERS[player_id]

    requests.get()



def add_png_extension_if_missing(filename):
    if "." not in filename:
        filename += ".png"
    return filename


async def main():
    session = aiohttp.ClientSession(headers=HEADERS)

    image_urls = await gather_image_urls(session, 205981)
    image_count = len(image_urls)
    print("Images found:", image_count)
    prompt = input("Want to download all? (y/n) > ")
    if prompt.lower() != "y": return

    await download_all(session, image_urls)

    await session.close()

asyncio.run(main())