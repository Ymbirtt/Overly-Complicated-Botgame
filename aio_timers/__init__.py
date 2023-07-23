"""
Timer support for asyncio.
"""

import asyncio


class Timer:
    def __init__(self, delay, callback, callback_args=(), callback_kwargs={}, callback_async=False, *, loop=None):
        """
        Call the callback after delay seconds.
        The timer is executed as a task on the event loop (asyncio.get_event_loop() if None).

        The callback is invoked:
         - as a synchronous function if it is not a coroutine;
         - with an await if it is a coroutine or the callback_async flag is set to True.

        NOTE: the callback_async flag should be used when a coroutine is decorated (e.g., using functools.partial)

        :param delay: number of seconds before the callback is executed.
        :param callback: callback to execute after delay seconds
        :param callback_args: positional arguments to pass to the callback
        :param callback_kwargs: keyword arguments to pass to the callback
        :param callback_async: if True the callback will be invoked with await
        :param loop: event loop where the timer task will be scheduled
        """
        self._future = asyncio.ensure_future(
            self._schedule_delayed_task(
                delay,
                callback,
                callback_args,
                callback_kwargs,
                callback_async
            ),

            loop=loop)

    @classmethod
    async def _schedule_delayed_task(cls, delay,
                                     callback, callback_args, callback_kwargs, callback_async):
        await asyncio.sleep(delay)

        # NOTE: it is not possible to invoke in a synchronous way a coroutine function.
        #       This is done since no result is returned.
        if callback_async or asyncio.iscoroutinefunction(callback):
            # async callback
            await callback(*callback_args, **callback_kwargs)
        else:
            callback(*callback_args, **callback_kwargs)

    async def wait(self):
        """
        Wait until the future has terminated (callback invoked or canceled)
        If the callback is cancelled an asyncio.CancelledError will be raised.
        :return: None
        """
        await self._future

    def cancel(self):
        """
        Cancel the delayed execution of the callback.
        :return: None
        """
        self._future.cancel()
