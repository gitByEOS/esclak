import asyncio

from clak.tui.app import ClakApp


def test_tui_uses_the_terminal_default_background():
    async def run() -> None:
        app = ClakApp()
        async with app.run_test(size=(80, 24)):
            assert app.native_ansi_color
            assert app.styles.background.ansi == -1
            assert app.screen.styles.background.ansi == -1

    asyncio.run(run())
    assert "background:" not in ClakApp.CSS
    assert "#0d1117" not in ClakApp.CSS


def test_typing_does_not_crash():
    async def run() -> None:
        app = ClakApp()
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.press("a", "b", "c")
            await pilot.press("enter")

    asyncio.run(run())
