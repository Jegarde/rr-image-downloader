import typer

from .image_downloader import rr_image_downloader


app = typer.Typer()
app.command()(rr_image_downloader)


if __name__ == "__main__":
    app()
