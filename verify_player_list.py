
import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        # Get the absolute path to the HTML file
        file_path = os.path.abspath('index.htm')

        # Go to the local HTML file
        await page.goto(f'file://{file_path}')

        # Mock data to be injected into the page
        mock_presences = {
            'user1': [{'email': 'zorro@email.com'}],
            'user2': [{'email': 'alfredo@email.com'}],
            'user3': [{'email': 'bernardo@email.com'}]
        }

        mock_game_state = {
            'players': {
                'user1': {'diceCount': 5, 'dice': [1, 2, 3, 4, 5]},
                'user2': {'diceCount': 4, 'dice': [1, 2, 3, 4]},
                'user3': {'diceCount': 3, 'dice': [1, 2, 3]}
            },
            'currentPlayer': 'user2',
            'round': 1,
            'currentBid': None,
            # Ensure the turn order is alphabetical to match the logic
            'turnOrder': ['user2', 'user3', 'user1']
        }

        # Expose a logging function to see browser console messages
        # CORREÇÃO: msg.text é uma propriedade, não um método.
        page.on('console', lambda msg: print(f"Browser console: {msg.text}"))

        # Inject the mock data and render the UI
        await page.evaluate("""
            (async () => {
                const mockGameState = {
                    players: {
                        'user1': { id: 'user1', diceCount: 5, dice: [1, 2, 3, 4, 5] },
                        'user2': { id: 'user2', diceCount: 4, dice: [1, 2, 3, 4] },
                        'user3': { id: 'user3', diceCount: 3, dice: [1, 2, 3] }
                    },
                    currentPlayer: 'user2',
                    round: 1,
                    currentBid: null,
                    turnOrder: ['user2', 'user3', 'user1'] // Example turn order
                };

                const mockPresences = {
                    'user1': [{ email: 'zorro@email.com' }],
                    'user2': [{ email: 'alfredo@email.com' }],
                    'user3': [{ email: 'bernardo@email.com' }]
                };

                const mockCurrentUser = { id: 'user2', email: 'alfredo@email.com' };

                if (window.testUtils) {
                    console.log('Setting up test data...');
                    window.testUtils.setGameState(mockGameState);
                    window.testUtils.setPresences(mockPresences);
                    window.testUtils.setCurrentUser(mockCurrentUser);

                    console.log('Switching to game view...');
                    window.testUtils.showView('room-view'); // Make sure the room view is visible
                    document.getElementById('game-view').classList.remove('hidden'); // Explicitly show game-view

                    console.log('Rendering game UI...');
                    window.testUtils.renderGameUI();
                    console.log('Render complete. Player list HTML:', document.getElementById('game-players-list').innerHTML);
                } else {
                    console.error('testUtils not found on window object.');
                }
            })()
        """)

        # Give it a moment for rendering just in case
        await page.wait_for_timeout(1000)

        # Take a screenshot to verify the result
        screenshot_path = '/home/jules/verification/verification.png'
        await page.screenshot(path=screenshot_path)
        print(f"Screenshot saved to {screenshot_path}")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
