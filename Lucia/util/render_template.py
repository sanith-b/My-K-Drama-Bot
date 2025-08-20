import jinja2
from info import *
from Lucia.Bot import SilentX
from Lucia.util.human_readable import humanbytes
from Lucia.util.file_properties import get_file_ids
from Lucia.server.exceptions import InvalidHash
import urllib.parse
from logging_helper import LOGGER
import aiohttp

async def render_page(id, secure_hash, src=None):
    file = await SilentX.get_messages(int(BIN_CHANNEL), int(id))
    file_data = await get_file_ids(SilentX, int(BIN_CHANNEL), int(id))
    if file_data.unique_id[:6] != secure_hash:
        LOGGER.info(f"link hash: {secure_hash} - {file_data.unique_id[:6]}")
        LOGGER.info(f"Invalid hash for message with - ID {id}")
        raise InvalidHash

    src = urllib.parse.urljoin(
        URL,
        f"{id}/{urllib.parse.quote_plus(file_data.file_name)}?hash={secure_hash}",
    )

    tag = file_data.mime_type.split("/")[0].strip()
    file_size = humanbytes(file_data.file_size)
    if tag in ["video", "audio"]:
        template_file = "Lucia/template/req.html"
    else:
        template_file = "Lucia/template/dl.html"
        async with aiohttp.ClientSession() as s:
            async with s.get(src) as u:
                file_size = humanbytes(int(u.headers.get("Content-Length")))

    with open(template_file) as f:
        template = jinja2.Template(f.read())

    file_name = file_data.file_name.replace("_", " ")

    return template.render(
        file_name=file_name,
        file_url=src,
        file_size=file_size,
        file_unique_id=file_data.unique_id,
    )
