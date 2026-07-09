#!/usr/bin/env python3
import asyncio
import re
from pathlib import Path

from playwright.async_api import async_playwright
from scrapers import (
    cdnlivetv,
    embedhd,
    fawa,
    fsports,
    futbolx,
    istreameast,
    mainportal,
    pelotalibre,
    roxie,
    sportspass,
    streamcenter,
    streamsgate,
    streamtp,
    streamxhd,
    watchfooty,
    webcast,
    xyzstream,
)
from scrapers.utils import get_logger, network

log = get_logger(__name__)

BASE_FILE = Path(__file__).parent / "base.m3u8"
EVENTS_FILE = Path(__file__).parent / "events.m3u8"
COMBINED_FILE = Path(__file__).parent / "TV.m3u8"

def load_base() -> tuple[list[str], int]:
    log.info("Fetching base M3U8")
    if not BASE_FILE.exists():
        return [], 0
    data = BASE_FILE.read_text(encoding="utf-8")
    pattern = re.compile(r'tvg-chno="(\d+)"')
    last_chnl_num = max(map(int, pattern.findall(data)), default=0)
    return data.splitlines(), last_chnl_num

async def main() -> None:
    log.info(f"{'=' * 10} FORK SOCCER Scraper Started {'=' * 10}")

    base_m3u8, tvg_chno = load_base()

    async with async_playwright() as p:
        try:
            hdl_brwsr = await network.browser(p)
            xtrnl_brwsr = await network.browser(p, external=True)

            pw_tasks = [
                asyncio.create_task(embedhd.scrape(hdl_brwsr)),
                asyncio.create_task(fsports.scrape(xtrnl_brwsr)),
                asyncio.create_task(roxie.scrape(hdl_brwsr)),
                asyncio.create_task(sportspass.scrape(xtrnl_brwsr)),
            ]

            httpx_tasks = [
                asyncio.create_task(fawa.scrape()),
                # asyncio.create_task(futbolx.scrape()),
                asyncio.create_task(istreameast.scrape()),
                asyncio.create_task(mainportal.scrape()),
                asyncio.create_task(pelotalibre.scrape()),
                asyncio.create_task(streamcenter.scrape()),
                asyncio.create_task(streamsgate.scrape()),
                asyncio.create_task(streamtp.scrape()),
                asyncio.create_task(streamxhd.scrape()),
                asyncio.create_task(webcast.scrape()),
                asyncio.create_task(xyzstream.scrape()),
            ]

            await asyncio.gather(*(pw_tasks + httpx_tasks))

            # others
            await cdnlivetv.scrape(xtrnl_brwsr)
            await watchfooty.scrape(xtrnl_brwsr)

        finally:
            await hdl_brwsr.close()
            await xtrnl_brwsr.close()
            await network.client.aclose()

    additions = (
        cdnlivetv.urls
        | embedhd.urls
        | fawa.urls
        | fsports.urls
        | futbolx.urls
        | istreameast.urls
        | mainportal.urls
        | pelotalibre.urls
        | roxie.urls
        | sportspass.urls
        | streamcenter.urls
        | streamsgate.urls
        | streamtp.urls
        | streamxhd.urls
        | watchfooty.urls
        | webcast.urls
        | xyzstream.urls
    )

    live_events: list[str] = []
    combined_channels: list[str] = []
    
    # Counter pembuat nomor urut channel khusus bola kaki
    soccer_count = 0

    for event_name, event_info in sorted(additions.items()):
        name_upper = event_name.upper()
        
        # Saringan ketat pembuang cabang non-sepakbola (Dibuat multi-baris agar tidak terpotong)
        banned_sports = [
            "BASKETBALL", "VOLLEYBALL", "TENNIS", "WIMBLEDON", 
            "MLB", "BASEBALL", "NFL", "F1", "MOTOGP", 
            "UFC", "BOXING", "CRICKET", "RUGBY", "GOLF"
        ]
        if any(banned in name_upper for banned in banned_sports):
            continue
            
        # Memastikan aroma kompetisi sepakbola kaki tetap terjaga (Dibuat multi-baris)
        keywords_bola = [
            "FOOTBALL", "SOCCER", "LIGA", "LEAGUE", "CUP", 
            "UEFA", "FIFA", "COPA", "CHAMPIONSHIP", "VS", "X"
        ]
        if not any(key in name_upper for key in keywords_bola):
            continue
            
        soccer_count += 1

        tvg_id, logo, refer, source = (
            event_info[x] for x in ("tvg-id", "logo", "refer", "source")
        )
        ua = event_info.get("user-agent", network.UA)

        extinf_all = (
            f'#EXTINF:-1 tvg-chno="{tvg_chno + soccer_count}" tvg-id="{tvg_id}" '
            f'tvg-name="{event_name}" tvg-logo="{logo}" group-title="Live Football Events",{event_name}'
        )

        extinf_live = (
            f'#EXTINF:-1 tvg-chno="{soccer_count}" tvg-id="{tvg_id}" '
            f'tvg-name="{event_name}" tvg-logo="{logo}" group-title="Live Football Events",{event_name}'
        )

        vlc_block: list[str] = [
            f"#EXTVLCOPT:http-referrer={refer}",
            f"#EXTVLCOPT:http-origin={refer}",
            f"#EXTVLCOPT:http-user-agent={ua}",
            source,
        ]

        combined_channels.extend(["\n" + extinf_all, *vlc_block])
        live_events.extend(["\n" + extinf_live, *vlc_block])

    COMBINED_FILE.write_text(
        "\n".join(base_m3u8 + combined_channels),
        encoding="utf-8",
    )
    log.info(f"Base + Football Events saved to {COMBINED_FILE.resolve()}")

    EVENTS_FILE.write_text(
        '#EXTM3U url-tvg="https://raw.githubusercontent.com/doms9/iptv/refs/heads/default/M3U8/TV.xml"\n'
        + "\n".join(live_events),
        encoding="utf-8",
    )
    log.info(f"Football Events saved to {EVENTS_FILE.resolve()}")

if __name__ == "__main__":
    asyncio.run(main())
    for hndlr in log.handlers:
        hndlr.flush()
        hndlr.stream.write("\n")
