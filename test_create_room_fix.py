
import re
from playwright.sync_api import Page, expect
import pytest
import os

# The mock is now a self-contained Javascript string to be injected directly.
MOCK_SUPABASE_SCRIPT = """
window.supabase = {
    createClient: (url, key, options) => {
        let authStateChangeCallback = null;

        const sb = {
            auth: {
                onAuthStateChange: (callback) => {
                    authStateChangeCallback = callback;
                    // Start in a logged-out state to ensure the login form is visible.
                    callback('INITIAL_SESSION', null);
                    return { data: { subscription: { unsubscribe: () => {} } } };
                },
                signInWithPassword: async (credentials) => {
                    if (credentials.email === 'test@example.com' && credentials.password === 'password123') {
                        const session = { user: { id: 'user-123', email: 'test@example.com' } };
                        // Synchronously trigger the auth state change to mimic real behavior.
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
                                    // Use a regex to generate a non-static room code for the test
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
                        // Simulate async subscription
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
                        // This is the core of the race condition simulation
                        if (mockChannel.channelName.includes("OLD_ROOM")) {
                            setTimeout(() => {
                                // Find the *new* channel and trigger its leave callback with the old host ID
                                if (window.testUtils.currentRoomChannel && window.testUtils.currentRoomChannel.callbacks['leave']) {
                                   window.testUtils.currentRoomChannel.callbacks['leave']({ key: 'user-123', leftPresences: [] });
                                }
                            }, 50); // Delay to ensure it happens *after* the new room is created
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
    Tests the specific race condition scenario:
    1. User creates and joins room A.
    2. User leaves room A.
    3. User immediately creates and joins room B.
    4. Asserts that the delayed 'leave' event from room A does not close room B.
    """
    file_path = os.path.abspath('index.htm')

    # For debugging test failures
    page.on("console", lambda msg: print(f"PAGE LOG: {msg.type} >> {msg.text}"))

    # Intercept the real Supabase script and inject our mock instead. This is the most
    # reliable way to ensure the application uses our mock in a file:// context.
    page.route(
        "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2",
        lambda route: route.fulfill(status=200, body=MOCK_SUPABASE_SCRIPT)
    )

    page.goto(f'file://{file_path}')

    # 1. Login
    page.locator("#login-form").get_by_label("Email").fill("test@example.com")
    page.locator("#login-form").get_by_label("Senha").fill("password123")
    page.locator("#login-form").get_by_role("button", name="Entrar").click()

    # Wait for lobby to be visible by checking for a stable element
    expect(page.get_by_role("button", name="Criar Nova Sala")).to_be_visible()

    # 2. Create the FIRST room
    page.get_by_role("button", name="Criar Nova Sala").click()

    # Expect to be in the first room
    expect(page.locator("#room-code-title")).to_be_visible()
    first_room_code_locator = page.locator("#room-code-display")
    expect(first_room_code_locator).to_be_visible()
    first_room_code = first_room_code_locator.inner_text()
    print(f"Entered first room: {first_room_code}")
    assert first_room_code != ""

    # Mark this channel as the "old" one for the unsubscribe simulation
    page.evaluate("window.testUtils.currentRoomChannel.channelName = 'room:OLD_ROOM'")

    # 3. Leave the FIRST room
    page.get_by_role("button", name="Voltar ao Lobby").click()

    # Wait to be back in the lobby
    expect(page.get_by_role("button", name="Criar Nova Sala")).to_be_visible()
    print("Successfully returned to lobby.")

    # 4. Create the SECOND room immediately
    page.get_by_role("button", name="Criar Nova Sala").click()

    # Wait for the new room UI to appear
    expect(page.locator("#room-code-title")).to_be_visible()
    second_room_code_locator = page.locator("#room-code-display")
    expect(second_room_code_locator).to_be_visible()
    second_room_code = second_room_code_locator.inner_text()
    print(f"Entered second room: {second_room_code}")
    assert second_room_code != ""
    assert second_room_code != first_room_code

    # 5. VERIFY the fix
    # Wait long enough for the delayed "leave" event from the mock to fire.
    page.wait_for_timeout(200)

    # The bug would show a "host has disconnected" toast and return to the lobby.
    # We assert that the toast is NOT visible and we are still in the room view.
    expect(page.get_by_text("O anfitrião desconectou-se.")).not_to_be_visible()
    expect(page.locator("#room-view")).to_be_visible()
    expect(page.locator("#room-code-title")).to_be_visible()
    print("Verification successful: Still in the second room. The bug is fixed.")
