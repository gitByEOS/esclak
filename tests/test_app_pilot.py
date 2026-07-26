import asyncio

from clak.tui.app import ClakApp


def test_typing_does_not_crash():
    async def run() -> None:
        app = ClakApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("a", "b", "c")
            await pilot.press("enter")

    asyncio.run(run())
