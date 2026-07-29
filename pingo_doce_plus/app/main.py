from __future__ import annotations

import asyncio
import logging
import signal
from contextlib import suppress

from .keeper import PingoDocePlusKeeper
from .utils import load_options


async def async_main() -> None:
    options = load_options()
    logging.basicConfig(
        level=getattr(logging, options.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    logger = logging.getLogger("pingo_doce_plus")
    keeper = PingoDocePlusKeeper(options, logger)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with suppress(NotImplementedError):
            loop.add_signal_handler(sig, keeper.stop_event.set)

    try:
        await keeper.start()
        tasks = [
            asyncio.create_task(keeper.refresh_loop(), name="refresh"),
            asyncio.create_task(keeper.watchdog_loop(), name="watchdog"),
            asyncio.create_task(keeper.command_loop(), name="commands"),
        ]
        await keeper.stop_event.wait()
        for task in tasks:
            task.cancel()
        for task in tasks:
            with suppress(asyncio.CancelledError):
                await task
    finally:
        await keeper.stop()


if __name__ == "__main__":
    asyncio.run(async_main())
