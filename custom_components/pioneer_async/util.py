""" Pioneer AVR utils. """
import asyncio
import socket
import random
import logging

RECONNECT_DELAY_MAX = 64

_LOGGER = logging.getLogger(__name__)

## https://stackoverflow.com/questions/12248132/how-to-change-tcp-keepalive-timer-using-python-script
def sock_set_keepalive(sock, after_idle_sec=1, interval_sec=3, max_fails=5):
    """Set TCP keepalive on an open socket.

    It activates after 1 second (after_idle_sec) of idleness,
    then sends a keepalive ping once every 3 seconds (interval_sec),
    and closes the connection after 5 failed ping (max_fails), or 15 seconds
    """
    if sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, after_idle_sec)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, interval_sec)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, max_fails)


def get_backoff_delay(retry_count):
    """ Calculate exponential backoff with random jitter delay. """
    delay = round(
        min(RECONNECT_DELAY_MAX, (2 ** max(retry_count, 2)))
        + (random.randint(0, 1000) / 1000),
        4,
    )
    return delay


async def cancel_task(task, task_name=None):
    """ Cancels a task and waits for it to finish. """
    if task:
        if not task.done():
            task.cancel()
            if not task_name:
                task_name = task.get_name()
            try:
                _LOGGER.debug("Waiting for %s task to be cancelled", task_name)
                await task
            except asyncio.CancelledError:
                _LOGGER.debug("Task %s cancelled", task_name)
            else:
                _LOGGER.debug("Task %s completed", task_name)
        else:
            _LOGGER.debug("Task %s already completed", task_name)
