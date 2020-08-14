#!/usr/bin/env python3
""" Pioneer AVR testing script. """
# pylint: disable=import-error,logging-fstring-interpolation,broad-except

import asyncio
import logging
import traceback

from pioneer_avr.pioneer_avr import PioneerAVR

_LOGGER = logging.getLogger(__name__)


async def main():
    """ Main loop. """
    _LOGGER.debug(">> main()")

    pioneer = PioneerAVR("avr")

    try:
        await pioneer.connect()
    except Exception as e:  # pylint: disable=invalid-name
        print(f"Could not connect to AVR: {type(e).__name__}: {e.args}")
        return False

    await pioneer.query_zones()
    print(f"AVR zones discovered: {pioneer.zones}")
    # await pioneer.update()
    # await asyncio.sleep(5)
    # print("...")
    # await pioneer.disconnect()

    while True:
        print("Update ...")
        await pioneer.update()
        print("...")
        await asyncio.sleep(60)

    # if not pioneer.available:
    #     try:
    #         await pioneer.connect()
    #     except Exception as e:  # pylint: disable=invalid-name
    #         print(f"Could not reconnect to AVR: {type(e).__name__}: {e.args}")
    #         await pioneer.shutdown()
    #         return False

    # await pioneer.send_raw_request("?P", "PWR")
    # print("...")
    # await asyncio.sleep(5)
    # print("...")
    # await pioneer.update()
    # print("...")
    # await asyncio.sleep(5)
    # print("...")
    await pioneer.shutdown()

    return True


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    rc = asyncio.run(main())
    exit(0 if rc else 1)
