import aiohttp
import os
import asyncio
import aiofiles
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


async def download_all(session, image_urls):
    os.makedirs(FOLDER, exist_ok=True)

    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [download_image(session, url, sem) for url in image_urls]
    results = await tqdm_asyncio.gather(*tasks)

    image_count = len(image_urls)
    print(f"\nDownloaded {sum(results)} / {image_count} images")


async def download_image(session, url, sem):
    filename = url.split("img.rec.net/")[-1]
    if "." not in filename:
        filename += ".png"
    filepath = os.path.join(FOLDER, filename)

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

            for img in resp:
                image_urls.append(f"https://img.rec.net/{img['ImageName']}")

            if image_count != MAX_IMAGES_PER_RESPONSE:
                break

    return image_urls


async def main():
    session = aiohttp.ClientSession(headers=HEADERS)

    image_urls = await gather_image_urls(session, 9085)
    image_count = len(image_urls)
    print("Images found:", image_count)
    prompt = input("Want to download all? (y/n) > ")
    if prompt.lower() != "y": return

    await download_all(session, image_urls)

    await session.close()

asyncio.run(main())