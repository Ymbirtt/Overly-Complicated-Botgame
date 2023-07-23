# silly tests
from aio_timers import Timer

if __name__ == "__main__":
    import asyncio

    loop = asyncio.get_event_loop()

    def callback(v):
        print(v)

    timer = Timer(7, callback, callback_args=(45,), loop=loop)
    timer = Timer(3, callback, callback_args=(42,), loop=loop)

    loop.run_until_complete(timer.wait())
    print("terminated")

    async def test():
        timer = Timer(3, callback, callback_args=(43,), loop=loop)
        await asyncio.sleep(4)

    loop.run_until_complete(test())
    print("terminated")

    timer = Timer(3, callback, callback_args=(44,), loop=loop)
    loop.run_until_complete(asyncio.sleep(4))
    print("terminated")

    async def test(sleep):
        timer = Timer(3, callback, callback_args=(46,), loop=loop)
        await asyncio.sleep(sleep)
        print("sleeped {} seconds".format(sleep))
        await timer.wait()

    loop.run_until_complete(test(2))
    print("terminated")

    async def test(sleep):
        timer = Timer(3, callback, callback_args=(47,), loop=loop)
        await asyncio.sleep(sleep)
        print("sleeped {} seconds".format(sleep))
        timer.cancel()
        try:
            await timer.wait()
        except asyncio.CancelledError:
            print("callback not executed (cancelled)")

    loop.run_until_complete(test(2))
    print("terminated")

    loop.close()
