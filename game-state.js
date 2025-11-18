// --- 1. DEFINIÇÕES DE CARTAS ---
const allCards = [
    { id: 1, name: 'Dragão', attack: 8, defense: 7 },
    { id: 2, name: 'Elfo', attack: 4, defense: 5 },
    { id: 3, name: 'Anão', attack: 6, defense: 4 },
    { id: 4, name: 'Guerreiro', attack: 7, defense: 6 },
    { id: 5, name: 'Mago', attack: 9, defense: 2 },
    { id: 6, name: 'Orc', attack: 7, defense: 3 },
];

// --- 2. ESTADO INICIAL DO JOGO ---
export function createInitialGameState(player1Id, player2Id) {
    // Embaralha o deck para garantir aleatoriedade
    const shuffledDeck = [...allCards].sort(() => Math.random() - 0.5);

    // Cada jogador recebe um deck completo e compra 3 cartas
    const player1Deck = [...shuffledDeck];
    const player2Deck = [...shuffledDeck];

    const player1Hand = player1Deck.splice(0, 3);
    const player2Hand = player2Deck.splice(0, 3);

    return {
        players: {
            [player1Id]: {
                deck: player1Deck,
                hand: player1Hand,
                field: [],
            },
            [player2Id]: {
                deck: player2Deck,
                hand: player2Hand,
                field: [],
            },
        },
        currentPlayer: player1Id, // O anfitrião (player1) começa
        turn: 1,
    };
}
