
// --- 1. ESTADO INICIAL DO JOGO DO DADO DO MENTIROSO ---

/**
 * Cria o estado inicial do jogo para uma lista de jogadores.
 * @param {string[]} playerIds - Um array com os IDs de todos os jogadores na sala.
 * @param {string} firstPlayerId - O ID do jogador que irá começar a primeira rodada.
 * @returns {object} O objeto de estado inicial do jogo.
 */
export function createInitialGameState(playerIds, firstPlayerId) {
    const players = {};
    playerIds.forEach(id => {
        players[id] = {
            diceCount: 5, // Cada jogador começa com 5 dados
            dice: [],     // Os dados rolados serão armazenados aqui
        };
    });

    return {
        players: players,
        turnOrder: [], // Armazena a ordem dos turnos dos jogadores
        currentPlayer: firstPlayerId, // O anfitrião (ou quem for definido) começa
        currentBid: null, // Nenhum lance no início (ex: { quantity: 2, face: 3 })
        lastBidder: null, // Quem fez o último lance
        turn: 1,
        round: 1,
        gameWinner: null, // ID do vencedor final
        roundInfo: {      // Informações sobre a resolução da rodada
            reveal: false,    // Se os dados devem ser revelados
            bidder: null,     // Quem fez o lance
            challenger: null, // Quem desafiou
            loser: null,      // Quem perdeu o dado
            actualQuantity: 0,// Quantidade real do dado apostado
            message: '',      // Mensagem de resultado da rodada
        },
    };
}
