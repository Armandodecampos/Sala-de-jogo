
import re
from playwright.sync_api import Page, expect
import pytest
import os

# O mock é agora uma string Javascript autocontida para ser injetada diretamente.
MOCK_SUPABASE_SCRIPT = """
window.supabase = {
    createClient: (url, key, options) => {
        let authStateChangeCallback = null;

        const sb = {
            auth: {
                onAuthStateChange: (callback) => {
                    authStateChangeCallback = callback;
                    // Começa em um estado de logout para garantir que o formulário de login esteja visível.
                    callback('INITIAL_SESSION', null);
                    return { data: { subscription: { unsubscribe: () => {} } } };
                },
                signInWithPassword: async (credentials) => {
                    if (credentials.email === 'test@example.com' && credentials.password === 'password123') {
                        const session = { user: { id: 'user-123', email: 'test@example.com' } };
                        // Aciona a mudança de estado de autenticação de forma síncrona para imitar o comportamento real.
                        if (authStateChangeCallback) {
                            authStateChangeCallback('SIGNED_IN', session);
                        }
                        return { data: { user: session.user }, error: null };
                    }
                    return { data: null, error: { message: 'Invalid credentials' } };
                },
                signOut: async () => {
                    if (authStateChangeCallback) {
                       authStateChangeCallback('SIGNED_OUT', null);
                    }
                    return { error: null };
                }
            },
            from: (table) => {
                const handlers = {
                    rooms: {
                        select: () => ({
                            eq: (column, value) => ({
                                maybeSingle: async () => {
                                    if (value === 'CRASH1') {
                                        return { data: null, error: { message: 'Room not found' } };
                                    }
                                    return { data: { room_code: value, creator_id: 'user-123', game_started: false }, error: null };
                                }
                            })
                        }),
                        insert: (payload) => ({
                            select: () => ({
                                single: async () => {
                                    // Usa uma regex para gerar um código de sala não estático para o teste
                                    const newCode = Math.random().toString(36).substring(2, 8).toUpperCase();
                                    return { data: { room_code: newCode, creator_id: payload.creator_id }, error: null };
                                }
                            })
                        }),
                        delete: () => ({
                            eq: async (column, value) => ({ error: null })
                        })
                    },
                    profiles: {
                        select: () => ({
                            eq: () => ({
                                single: async () => ({
                                    data: { last_room: null },
                                    error: null
                                })
                            })
                        }),
                        update: () => ({
                            eq: async () => ({ error: null })
                        })
                    }
                };
                return handlers[table];
            },
            channel: (channelName) => {
                const mockChannel = {
                    on: (event, filter, callback) => {
                        mockChannel.callbacks = mockChannel.callbacks || {};
                        mockChannel.callbacks[filter.event] = callback;
                        return mockChannel;
                    },
                    subscribe: (callback) => {
                        // Simula a inscrição assíncrona
                        setTimeout(() => callback('SUBSCRIBED'), 20);
                        return mockChannel;
                    },
                    track: async (payload) => {
                        // Simulate tracking and presence sync
                        setTimeout(() => {
                            if (mockChannel.callbacks && mockChannel.callbacks['sync']) {
                                mockChannel.callbacks['sync']();
                            }
                        }, 20);
                        return { error: null };
                    },
                    unsubscribe: async () => {
                        // Esta é a parte central da simulação da condição de corrida
                        if (mockChannel.channelName.includes("OLD_ROOM")) {
                            setTimeout(() => {
                                // Encontra o *novo* canal e aciona seu callback de 'leave' com o ID do anfitrião antigo
                                if (window.testUtils.currentRoomChannel && window.testUtils.currentRoomChannel.callbacks['leave']) {
                                   window.testUtils.currentRoomChannel.callbacks['leave']({ key: 'user-123', leftPresences: [] });
                                }
                            }, 50); // Atraso para garantir que aconteça *depois* da criação da nova sala
                        }
                        return { error: null };
                    },
                    send: async (payload) => ({ error: null }),
                    presenceState: () => ({
                        'user-123': [{ email: 'test@example.com' }]
                    }),
                    channelName: channelName,
                    callbacks: {}
                };
                window.testUtils.currentRoomChannel = mockChannel;
                return mockChannel;
            }
        };
        window.testUtils = window.testUtils || {};
        window.testUtils.sb = sb;
        return sb;
    }
};
"""

def test_create_room_after_leaving_another(page: Page):
    """
    Testa o cenário específico da condição de corrida:
    1. O usuário cria e entra na sala A.
    2. O usuário sai da sala A.
    3. O usuário cria e entra imediatamente na sala B.
    4. Afirma que o evento 'leave' atrasado da sala A não fecha a sala B.
    """
    file_path = os.path.abspath('index.htm')

    # Para depurar falhas no teste
    page.on("console", lambda msg: print(f"PAGE LOG: {msg.type} >> {msg.text}"))

    # Intercepta o script real do Supabase e injeta nosso mock. Esta é a maneira mais
    # confiável de garantir que a aplicação use nosso mock em um contexto file://.
    page.route(
        "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2",
        lambda route: route.fulfill(status=200, body=MOCK_SUPABASE_SCRIPT)
    )

    page.goto(f'file://{file_path}')

    # 1. Login
    page.locator("#login-form").get_by_label("Email").fill("test@example.com")
    page.locator("#login-form").get_by_label("Senha").fill("password123")
    page.locator("#login-form").get_by_role("button", name="Entrar").click()

    # Espera o lobby estar visível verificando um elemento estável
    expect(page.get_by_role("button", name="Criar Nova Sala")).to_be_visible()

    # 2. Cria a PRIMEIRA sala
    page.get_by_role("button", name="Criar Nova Sala").click()

    # Espera estar na primeira sala
    expect(page.locator("#room-code-title")).to_be_visible()
    first_room_code_locator = page.locator("#room-code-display")
    expect(first_room_code_locator).to_be_visible()
    first_room_code = first_room_code_locator.inner_text()
    print(f"Entrou na primeira sala: {first_room_code}")
    assert first_room_code != ""

    # Marca este canal como o "antigo" para a simulação de cancelamento de inscrição
    page.evaluate("window.testUtils.currentRoomChannel.channelName = 'room:OLD_ROOM'")

    # 3. Sai da PRIMEIRA sala
    page.get_by_role("button", name="Voltar ao Lobby").click()

    # Espera estar de volta ao lobby
    expect(page.get_by_role("button", name="Criar Nova Sala")).to_be_visible()
    print("Retornou ao lobby com sucesso.")

    # 4. Cria a SEGUNDA sala imediatamente
    page.get_by_role("button", name="Criar Nova Sala").click()

    # Espera a UI da nova sala aparecer
    expect(page.locator("#room-code-title")).to_be_visible()
    second_room_code_locator = page.locator("#room-code-display")
    expect(second_room_code_locator).to_be_visible()
    second_room_code = second_room_code_locator.inner_text()
    print(f"Entrou na segunda sala: {second_room_code}")
    assert second_room_code != ""
    assert second_room_code != first_room_code

    # 5. VERIFICA a correção
    # Espera o tempo suficiente para o evento "leave" atrasado do mock disparar.
    page.wait_for_timeout(200)

    # O bug mostraria um toast de "o anfitrião desconectou-se" e retornaria ao lobby.
    # Afirmamos que o toast NÃO está visível e que ainda estamos na visualização da sala.
    expect(page.get_by_text("O anfitrião desconectou-se.")).not_to_be_visible()
    expect(page.locator("#room-view")).to_be_visible()
    expect(page.locator("#room-code-title")).to_be_visible()
    print("Verificação bem-sucedida: Ainda na segunda sala. O bug foi corrigido.")
