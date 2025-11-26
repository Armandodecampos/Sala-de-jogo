
import asyncio
from playwright.async_api import async_playwright, expect
import os

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        file_path = os.path.abspath('index.htm')
        await page.goto(f'file://{file_path}')

        page.on('console', lambda msg: print(f"Browser console: {msg.text}"))

        # --- Etapa 1: Configurar a sala e o anfitrião ---
        host_id = 'user-host'
        other_player_id = 'user-player2'

        await page.evaluate(f"""
            (async () => {{
                // Mock da chamada de atualização do banco de dados para evitar erros de rede
                const originalFrom = sb.from;
                sb.from = (tableName) => {{
                    if (tableName === 'rooms') {{
                        return {{
                            update: () => ({{
                                eq: () => ({{
                                    // Simula uma atualização bem-sucedida
                                    then: (callback) => callback({{ error: null }})
                                }})
                            }})
                        }};
                    }}
                    return originalFrom.apply(sb, [tableName]);
                }};

                const hostId = '{host_id}';
                const otherPlayerId = '{other_player_id}';

                window.testUtils.setCurrentUser({{ id: hostId, email: 'host@email.com' }});
                window.testUtils.setCurrentRoom({{ room_code: 'TEST1', creator_id: hostId }});
                window.testUtils.setCurrentRoomChannel({{
                    send: () => {{}},
                    presenceState: () => ({{
                        [hostId]: [{{ email: 'host@email.com' }}],
                        [otherPlayerId]: [{{ email: 'player2@email.com' }}]
                    }})
                }});
                window.testUtils.setPresences({{
                    [hostId]: [{{ email: 'host@email.com' }}],
                    [otherPlayerId]: [{{ email: 'player2@email.com' }}]
                }});
                window.testUtils.setGameStarted(false);

                window.testUtils.showView('room-view');
                window.testUtils.renderRoomUI();
            }})()
        """)

        # Verifica se o botão "Iniciar Jogo" está visível e habilitado
        start_game_btn = page.locator('#game-action-btn')
        await expect(start_game_btn).to_be_visible()
        await expect(start_game_btn).to_be_enabled()
        print("Verificação: O botão 'Iniciar Jogo' está visível e habilitado para o anfitrião.")

        # --- Etapa 2: Iniciar o jogo ---
        await start_game_btn.click()
        print("Ação: O jogo foi iniciado.")

        # --- Etapa 3: Verificar a UI inicial do jogo para o anfitrião ---
        await expect(page.locator('#game-view')).to_be_visible()
        await expect(page.locator('#my-dice-display svg')).to_have_count(5)
        print("Verificação: A visualização do jogo está visível e o anfitrião tem 5 dados.")

        player_list = page.locator('#game-players-list')
        await expect(player_list.locator('div')).to_have_count(2)
        print("Verificação: A lista de jogadores mostra 2 participantes.")

        # O anfitrião é o primeiro a jogar
        await expect(page.locator('#bid-btn')).to_be_enabled()
        await expect(page.locator('#challenge-btn')).to_be_disabled()
        await expect(page.locator('#exact-btn')).to_be_disabled()
        print("Verificação: Os botões de ação do anfitrião estão no estado correto (Apostar habilitado).")

        # --- Etapa 4: Anfitrião faz um lance ---
        await page.locator('#bid-quantity').fill('2')
        await page.locator('#bid-face').select_option('3')
        await page.locator('#bid-btn').click()
        print("Ação: O anfitrião apostou 2 dados de face 3.")

        # --- Etapa 5: Verificar a UI do anfitrião após o lance ---
        await expect(page.locator('#bid-btn')).to_be_disabled()
        await expect(page.locator('#challenge-btn')).to_be_disabled()
        await expect(page.locator('#exact-btn')).to_be_disabled()
        print("Verificação: Os botões do anfitrião foram desabilitados após o lance.")

        current_bid = page.locator('#current-bid-display')
        await expect(current_bid).to_contain_text('2 x')
        print("Verificação: O lance atual foi atualizado na UI.")

        # --- Etapa 6: Mudar para a perspectiva do Jogador 2 e verificar ---
        await page.evaluate(f"""
            (async () => {{
                const otherPlayerId = '{other_player_id}';
                window.testUtils.setCurrentUser({{ id: otherPlayerId, email: 'player2@email.com' }});
                window.testUtils.renderGameUI();
            }})()
        """)
        print("Ação: Mudou o contexto para o Jogador 2.")

        # Para o jogador 2, os botões de duvidar/confirmar devem estar habilitados
        await expect(page.locator('#bid-btn')).to_be_enabled()
        await expect(page.locator('#challenge-btn')).to_be_enabled()
        await expect(page.locator('#exact-btn')).to_be_enabled()
        print("Verificação: Os botões 'Duvidar' e 'Confirmar' estão habilitados para o Jogador 2.")

        # --- Etapa 7: Captura de tela ---
        screenshot_path = '/home/jules/verification/verification.png'
        await page.screenshot(path=screenshot_path)
        print(f"Captura de tela salva em {screenshot_path}")

        await browser.close()

if __name__ == '__main__':
    asyncio.run(main())
