/*
Fecha de entrega: 12 mayo 2025, 11:59 pm
Desarrollar un agente que juegue cuadrito. Tiene límite de tiempo:
 1. Aquí encuentran el código del ambiente
 2. Su agente debe heredar de la clase Agent y debe sobreescribir el método compute
 3. El método de iniciar el agente recibe tres argumentos: 
    - El color con que está jugando
    - El tablero inicial del cual puede obtener el tamaño (siempre cuadrado)
    - El tiempo total de juego en milisegundos
 4. El método compute recibe dos argumentos:
    - El tablero como va 
    - El tiempo que le queda a su agente en milisegundos
 5. El método compute debe retornar una lista con tres argumentos [fila, columna, lado]. El valor del lado
 es un número 0: arriba, 1: derecha, 2.abajo, 3:izquierda 
*/

/**
 * Abstract agent class
 */
class Agent {
  /**
   * Creates an agent
   */
  constructor() {}

  /**
   * Initializes the agent
   * @param color Color of the agent pieces ('R':red or 'Y':yellow)
   * @param board Initial state of the board (empty, useful for obtaaining the size (nxn))
   * @param time Total amount of time the agent has for playing all the game (milliseconds)
   */
  init(color, board, time = 20000) {
    this.color = color
    this.time = time
    this.size = board.length
  }

  /**
     * Determines the next play of the agent
     * @param board Current square configuration
     * @param time Remaining time the agent has for playing all the game (milliseconds)
     * @return A list with three values [row, column, side]. Parameter size can take one of the following values: 
               0 is up, 1 is right, 2 is bottom, 3 is left  
     */
  compute(board, time) {
    return [0, 0, 0]
  }
}

/*
 * A class for board operations (it is not the board but a set of operations over it)
 */
class Board {
  constructor() {}

  // Initializes a board of the given size. A board is a matrix of size*size of integers 0, .., 15, -1, or -2
  init(size) {
    var m = size - 1
    var board = []
    board[0] = []
    board[0][0] = 9
    for (var j = 1; j < m; j++) {
      board[0][j] = 1
    }
    board[0][m] = 3

    for (var i = 1; i < m; i++) {
      board[i] = []
      board[i][0] = 8
      for (var j = 1; j < m; j++) {
        board[i][j] = 0
      }
      board[i][m] = 2
    }

    board[m] = []
    board[m][0] = 12
    for (var j = 1; j < m; j++) {
      board[m][j] = 4
    }
    board[m][m] = 6

    return board
  }

  // Deep clone of a board the reduce risk of damaging the real board
  clone(board) {
    var size = board.length
    var b = []
    for (var i = 0; i < size; i++) {
      b[i] = []
      for (var j = 0; j < size; j++) b[i][j] = board[i][j]
    }
    return b
  }

  // Determines if a line can be drawn at row r, column c, side s
  check(board, r, c, s) {
    if (board[r][c] < 0) return false
    s = 1 << s
    return (board[r][c] & s) != s
  }

  // Computes all the valid moves for the given 'color'
  valid_moves(board) {
    var moves = []
    var size = board.length
    for (var i = 0; i < size; i++)
      for (var j = 0; j < size; j++)
        for (var s = 0; s < 4; s++)
          if (this.check(board, i, j, s)) moves.push([i, j, s])
    return moves
  }

  fill(board, i, j, color) {
    if (i < 0 || i == board.length || j < 0 || j == board.length) return board

    if (board[i][j] == 15 || board[i][j] == 14) {
      board[i][j] = color
      if (i > 0 && board[i - 1][j] >= 0) {
        board[i - 1][j] += 4
        this.fill(board, i - 1, j, color)
      }
    }

    if (board[i][j] == 15 || board[i][j] == 13) {
      board[i][j] = color
      if (j < board.length - 1 && board[i][j + 1] >= 0) {
        board[i][j + 1] += 8
        this.fill(board, i, j + 1, color)
      }
    }

    if (board[i][j] == 15 || board[i][j] == 11) {
      board[i][j] = color
      if (i < board.length - 1 && board[i + 1][j] >= 0) {
        board[i + 1][j] += 1
        this.fill(board, i + 1, j, color)
      }
    }

    if (board[i][j] == 15 || board[i][j] == 7) {
      board[i][j] = color
      if (j > 0 && board[i][j - 1] >= 0) {
        board[i][j - 1] += 2
        this.fill(board, i, j - 1, color)
      }
    }
    return board
  }

  // Computes the new board when a piece of 'color' is set at row i, column j, side s.
  // If it is an invalid movement stops the game and declares the other 'color' as winner
  move(board, i, j, s, color) {
    if (this.check(board, i, j, s)) {
      var ocolor = color == -2 ? -1 : -2
      board[i][j] |= 1 << s
      board = this.fill(board, i, j, ocolor)
      if (i > 0 && s == 0) {
        board[i - 1][j] |= 4
        board = this.fill(board, i - 1, j, ocolor)
      }
      if (i < board.length - 1 && s == 2) {
        board[i + 1][j] |= 1
        board = this.fill(board, i + 1, j, ocolor)
      }
      if (j > 0 && s == 3) {
        board[i][j - 1] |= 2
        board = this.fill(board, i, j - 1, ocolor)
      }

      if (j < board.length - 1 && s == 1) {
        board[i][j + 1] |= 8
        board = this.fill(board, i, j + 1, ocolor)
      }
      return true
    }
    return false
  }

  // Determines the winner of the game if available 'R': red, 'Y': yellow, ' ': none
  winner(board) {
    var cr = 0
    var cy = 0
    for (var i = 0; i < board.length; i++)
      for (var j = 0; j < board.length; j++)
        if (board[i][j] < 0) {
          if (board[i][j] == -1) {
            cr++
          } else {
            cy++
          }
        }
    if (cr + cy < board.length * board.length) return " "
    if (cr > cy) return "R"
    if (cy > cr) return "Y"
    return " "
  }

  // Returns captured square counts: R = Red's captures (-2 cells), Y = Yellow's (-1 cells)
  countScores(board) {
    var r = 0, y = 0
    for (var i = 0; i < board.length; i++)
      for (var j = 0; j < board.length; j++) {
        if (board[i][j] === -1) r++
        else if (board[i][j] === -2) y++
      }
    return { R: r, Y: y }
  }

  // Draw the board on the canvas
  print(board) {
    var size = board.length
    // Commands to be run (left as string to show them into the editor)
    var grid = []
    for (var i = 0; i < size; i++) {
      for (var j = 0; j < size; j++) {
        var commands = [{ command: "-" }]
        if (board[i][j] < 0) {
          if (board[i][j] == -1) commands.push({ command: "R" })
          else commands.push({ command: "Y" })
          commands.push({ command: "u" })
          commands.push({ command: "r" })
          commands.push({ command: "d" })
          commands.push({ command: "l" })
        } else {
          if ((board[i][j] & 1) == 1) commands.push({ command: "u" })
          if ((board[i][j] & 2) == 2) commands.push({ command: "r" })
          if ((board[i][j] & 4) == 4) commands.push({ command: "d" })
          if ((board[i][j] & 8) == 8) commands.push({ command: "l" })
        }
        grid.push({ command: "translate", y: i, x: j, commands: commands })
      }
    }

    var cmds = {
      r: true,
      x: 1.0 / size,
      y: 1.0 / size,
      command: "fit",
      commands: grid,
    }
    Konekti.client["canvas"].setText(cmds)
  }
}

/*
 * Player's Code (Must inherit from Agent: It is mandatory the inheritance process)
 * This is an example ocustom_commandsf a rangom player agent
 *
 */
class RandomPlayer extends Agent {
  constructor() {
    super()
    this.board = new Board()
  }

  compute(board, time) {
    // Always cheks the current board status since opponent move can change several squares in the board
    var moves = this.board.valid_moves(board)
    // Randomly picks one available move
    var index = Math.floor(moves.length * Math.random())
    return moves[index]
  }
}

class AgentAvocadoGemini extends Agent {
  constructor() {
    super()
    this.board_util = new Board()
  }

  /**
   * Cuenta cuántas líneas tiene actualmente un cuadrado específico
   */
  countLines(board, r, c) {
    if (r < 0 || r >= board.length || c < 0 || c >= board.length) return -1
    let val = board[r][c]
    if (val < 0) return 4 // Ya está capturado
    let count = 0
    for (let i = 0; i < 4; i++) {
      if ((val & (1 << i)) !== 0) count++
    }
    return count
  }

  /**
   * Evalúa qué tan "peligrosa" es una jugada.
   * Retorna el máximo de líneas que quedarían en los cuadros afectados.
   */
  evaluateMove(board, r, c, s) {
    let linesCurrent = this.countLines(board, r, c)
    let maxLinesResulting = linesCurrent + 1

    // Verificar el cuadro adyacente que comparte la misma línea
    let adjR = r,
      adjC = c
    if (s === 0)
      adjR-- // Arriba afecta al de arriba
    else if (s === 1)
      adjC++ // Derecha afecta al de la derecha
    else if (s === 2)
      adjR++ // Abajo afecta al de abajo
    else if (s === 3) adjC-- // Izquierda afecta al de la izquierda

    let linesAdj = this.countLines(board, adjR, adjC)
    if (linesAdj !== -1) {
      maxLinesResulting = Math.max(maxLinesResulting, linesAdj + 1)
    }

    return maxLinesResulting
  }

  compute(board, time) {
    const moves = this.board_util.valid_moves(board)

    let winningMoves = [] // Completan un cuadro (dejan 4 líneas)
    let safeMoves = [] // No regalan cuadro (dejan < 3 líneas)
    let desperateMoves = [] // Obligatorios (dejan 3 líneas, regalando el cuadro)

    for (let move of moves) {
      let [r, c, s] = move
      let res = this.evaluateMove(board, r, c, s)

      if (res === 4) {
        // ¡Prioridad máxima! Esta jugada cierra un cuadro
        winningMoves.push(move)
      } else if (res < 3) {
        // Jugada segura: el oponente no puede cerrar el cuadro en su turno
        safeMoves.push(move)
      } else {
        // Jugada peligrosa: dejamos 3 líneas, el oponente cerrará el cuadro
        desperateMoves.push(move)
      }
    }

    // 1. Si podemos ganar un cuadro, lo hacemos.
    if (winningMoves.length > 0) {
      return winningMoves[Math.floor(Math.random() * winningMoves.length)]
    }

    // 2. Si hay jugadas seguras, elegimos una al azar.
    if (safeMoves.length > 0) {
      return safeMoves[Math.floor(Math.random() * safeMoves.length)]
    }

    // 3. Si no hay de otra, jugamos donde sea (el oponente ganará algo).
    return desperateMoves[Math.floor(Math.random() * desperateMoves.length)]
  }
}

class AgentAvocadoRandom extends Agent {
  constructor() {
    super()
    this.board = new Board()
  }

  countLines(board, r, c) {
    /**
     * Cuenta cuántas líneas tiene actualmente un cuadrado específico
     */
    if (r < 0 || r >= board.length || c < 0 || c >= board.length) return -1
    let val = board[r][c]
    if (val < 0) return 4 // Ya está capturado
    let count = 0
    for (let i = 0; i < 4; i++) {
      if ((val & (1 << i)) !== 0) count++
    }
    return count
  }

  compute(board, time) {
    var moves = this.board.valid_moves(board)
    console.log({ board, moves, time })

    var index = Math.floor(moves.length * Math.random())
    return moves[index]
  }
}

class AgentAvocadoClaude extends Agent {
  constructor() {
    super()
    this.board_util = new Board()
  }

  init(color, board, time = 20000) {
    super.init(color, board, time)
    this.colorInt = color == 'R' ? -1 : -2
    // Game quirk: move() stores captures as ocolor, so my cells have opposite sign
    this.myFill = this.colorInt == -1 ? -2 : -1
    this.oppFill = this.colorInt          // opponent's cells stored as my colorInt
    this.oppColorInt = this.myFill        // opponent plays with myFill value
  }

  countLines(board, r, c) {
    if (r < 0 || r >= board.length || c < 0 || c >= board.length) return -1
    const val = board[r][c]
    if (val < 0) return 4
    let n = 0
    for (let i = 0; i < 4; i++) if (val & (1 << i)) n++
    return n
  }

  evalScore(board) {
    let mine = 0, theirs = 0
    for (let i = 0; i < board.length; i++)
      for (let j = 0; j < board.length; j++) {
        if (board[i][j] === this.myFill) mine++
        else if (board[i][j] === this.oppFill) theirs++
      }
    return mine - theirs
  }

  // Returns 'w' (winning), 's' (safe), or 'd' (desperate)
  categorizeMove(board, r, c, s) {
    const cur = this.countLines(board, r, c) + 1
    const dirs = [[-1, 0], [0, 1], [1, 0], [0, -1]]
    const adjLines = this.countLines(board, r + dirs[s][0], c + dirs[s][1])
    const adjNew = (adjLines >= 0 && adjLines < 4) ? adjLines + 1 : 0
    const mx = Math.max(cur, adjNew)
    return mx >= 4 ? 'w' : mx < 3 ? 's' : 'd'
  }

  splitMoves(board, moves) {
    const cats = { w: [], s: [], d: [] }
    for (const mv of moves) cats[this.categorizeMove(board, mv[0], mv[1], mv[2])].push(mv)
    return cats
  }

  detectChains(board) {
    const n = board.length
    const vis = Array.from({ length: n }, () => new Array(n).fill(false))
    const chains = []
    for (let i = 0; i < n; i++) {
      for (let j = 0; j < n; j++) {
        if (!vis[i][j] && board[i][j] >= 0 && this.countLines(board, i, j) === 3) {
          const chain = []
          const q = [[i, j]]
          vis[i][j] = true
          while (q.length) {
            const [r, c] = q.shift()
            chain.push([r, c])
            for (const [dr, dc] of [[-1, 0], [1, 0], [0, -1], [0, 1]]) {
              const nr = r + dr, nc = c + dc
              if (nr >= 0 && nr < n && nc >= 0 && nc < n &&
                !vis[nr][nc] && board[nr][nc] >= 0 &&
                this.countLines(board, nr, nc) === 3) {
                vis[nr][nc] = true
                q.push([nr, nc])
              }
            }
          }
          chains.push(chain)
        }
      }
    }
    return chains
  }

  // Pick desperate move that leaves the smallest max-chain on board
  openShortestChain(board, moves) {
    let best = moves[0], bestMax = Infinity
    for (const mv of moves) {
      const b = this.board_util.clone(board)
      this.board_util.move(b, mv[0], mv[1], mv[2], this.colorInt)
      const chains = this.detectChains(b)
      const maxLen = chains.reduce((m, c) => Math.max(m, c.length), 0)
      if (maxLen < bestMax) { bestMax = maxLen; best = mv }
    }
    return best
  }

  minimax(board, depth, alpha, beta, myTurn, deadline) {
    if (Date.now() >= deadline) return { score: this.evalScore(board), move: null }
    const moves = this.board_util.valid_moves(board)
    if (!moves.length || !depth) return { score: this.evalScore(board), move: null }

    const color = myTurn ? this.colorInt : this.oppColorInt
    const cats = this.splitMoves(board, moves)
    const ordered = [...cats.w, ...cats.s, ...cats.d]

    let bestMove = ordered[0]
    let bestScore = myTurn ? -Infinity : Infinity

    for (const mv of ordered) {
      if (Date.now() >= deadline) break
      const b = this.board_util.clone(board)
      this.board_util.move(b, mv[0], mv[1], mv[2], color)
      const { score } = this.minimax(b, depth - 1, alpha, beta, !myTurn, deadline)
      if (myTurn ? score > bestScore : score < bestScore) {
        bestScore = score
        bestMove = mv
      }
      if (myTurn) alpha = Math.max(alpha, bestScore)
      else beta = Math.min(beta, bestScore)
      if (beta <= alpha) break
    }
    return { score: bestScore, move: bestMove }
  }

  compute(board, time) {
    const moves = this.board_util.valid_moves(board)
    if (!moves.length) return [0, 0, 0]

    const cats = this.splitMoves(board, moves)

    // Layer 1: take free square immediately
    if (cats.w.length) return cats.w[0]

    // Time budget: 70% of fair share, capped at 2s, floor at 30ms
    const remaining = Math.max(1, Math.floor(moves.length / 2))
    const limit = Math.min(Math.max((time / remaining) * 0.7, 30), 2000)
    const deadline = Date.now() + limit

    // Fallback (used if minimax times out before depth=1 completes)
    let best = cats.s.length
      ? cats.s[Math.floor(Math.random() * cats.s.length)]
      : this.openShortestChain(board, cats.d.length ? cats.d : moves)

    // Iterative-deepening alpha-beta minimax
    for (let d = 1; d <= 12; d++) {
      if (Date.now() >= deadline) break
      const result = this.minimax(board, d, -Infinity, Infinity, true, deadline)
      if (result.move) best = result.move
    }

    return best
  }
}

/*
 * Environment (Cannot be modified or any of its attributes accesed directly)
 */
class Environment extends MainClient {
  constructor() {
    super()
    this.board = new Board()
  }

  setPlayers(players) {
    this.players = players
  }

  // Initializes the game
  init() {
    var white = Konekti.vc("R").value // Name of competitor with red pieces
    console.log(white)
    var black = Konekti.vc("Y").value // Name of competitor with yellow pieces
    var time = 1000 * parseInt(Konekti.vc("time").value) // Maximum playing time assigned to a competitor (milliseconds)
    var size = parseInt(Konekti.vc("size").value) // Size of the reversi board

    this.size = size
    this.rb = this.board.init(size)
    this.board.print(this.rb)
    var b1 = this.board.clone(this.rb)
    var b2 = this.board.clone(this.rb)

    this.white = white
    this.black = black
    this.ptime = { R: time, Y: time }
    Konekti.vc("R_time").innerHTML = "" + time
    Konekti.vc("Y_time").innerHTML = "" + time
    Konekti.vc("R_score").innerHTML = "0"
    Konekti.vc("Y_score").innerHTML = "0"
    this.player = "R"
    this.winner = ""

    this.players[white].init("R", b1, time)
    this.players[black].init("Y", b2, time)
  }

  // Listen to play button
  play() {
    var TIME = 10
    var x = this
    var board = x.board
    x.player = "R"
    Konekti.vc("log").innerHTML = "The winner is..."

    x.init()
    var start = -1

    function clock() {
      if (x.winner != "") return
      if (start == -1) setTimeout(clock, TIME)
      else {
        var end = Date.now()
        var ellapsed = end - start
        var remaining = x.ptime[x.player] - ellapsed
        Konekti.vc(x.player + "_time").innerHTML = remaining
        Konekti.vc((x.player == "R" ? "Y" : "R") + "_time").innerHTML =
          x.ptime[x.player == "R" ? "Y" : "R"]

        if (remaining <= 0)
          x.winner =
            (x.player == "R" ? x.black : x.white) +
            " since " +
            (x.player == "R" ? x.white : x.black) +
            "got time out"
        else setTimeout(clock, TIME)
      }
    }

    function compute() {
      var w = x.player == "R"
      var id = w ? x.white : x.black
      var nid = w ? x.black : x.white
      var b = board.clone(x.rb)
      start = Date.now()
      var action = x.players[id].compute(b, x.ptime[x.player])
      var end = Date.now()
      var ply = x.player == "R" ? -1 : -2
      var flag = board.move(x.rb, action[0], action[1], action[2], ply)
      if (!flag) {
        x.winner =
          nid + " ...Invalid move taken by " + id + " on column " + action
      } else {
        var winner = board.winner(x.rb)
        if (winner != " ") x.winner = winner
        else {
          var ellapsed = end - start
          x.ptime[x.player] -= ellapsed
          Konekti.vc(x.player + "_time").innerHTML = "" + x.ptime[x.player]
          if (x.ptime[x.player] <= 0) {
            x.winner = nid + " since " + id + " got run of time"
          } else {
            x.player = w ? "Y" : "R"
          }
        }
      }

      board.print(x.rb)
      var sc = board.countScores(x.rb)
      Konekti.vc("R_score").innerHTML = "" + sc.R
      Konekti.vc("Y_score").innerHTML = "" + sc.Y
      start = -1
      if (x.winner == "") setTimeout(compute, TIME)
      else {
        var wname, wcolor
        if (x.winner == "R") { wname = x.white; wcolor = "#cc0000" }
        else if (x.winner == "Y") { wname = x.black; wcolor = "#b8a000" }
        else { wname = x.winner; wcolor = "#333" }
        Konekti.vc("log").innerHTML = "The winner is " + wname
        var overlay = document.getElementById("winner-overlay")
        var msg = document.getElementById("winner-msg")
        if (overlay && msg) {
          msg.innerHTML = "&#x25a0; " + wname + " wins!<br><small style='font-size:0.45em;color:#888;font-weight:normal'>click to close</small>"
          msg.style.color = wcolor
          overlay.style.display = "flex"
        }
      }
    }

    board.print(x.rb)
    setTimeout(clock, 1000)
    setTimeout(compute, 1000)
  }
}

// Drawing commands
function custom_commands() {
  return [
    {
      command: " ",
      commands: [
        {
          command: "fillStyle",
          color: { red: 255, green: 255, blue: 255, alpha: 255 },
        },
        {
          command: "polygon",
          x: [0.2, 0.2, 0.8, 0.8],
          y: [0.2, 0.8, 0.8, 0.2],
        },
      ],
    },
    {
      command: "-",
      commands: [
        {
          command: "strokeStyle",
          color: { red: 128, green: 128, blue: 128, alpha: 255 },
        },
        {
          command: "polyline",
          x: [0, 0, 1, 1, 0],
          y: [0, 1, 1, 0, 0],
        },
      ],
    },
    {
      command: "u",
      commands: [
        {
          command: "strokeStyle",
          color: { red: 0, green: 0, blue: 255, alpha: 255 },
        },
        {
          command: "polyline",
          x: [0, 1],
          y: [0, 0],
        },
      ],
    },
    {
      command: "d",
      commands: [
        {
          command: "strokeStyle",
          color: { red: 0, green: 0, blue: 255, alpha: 255 },
        },
        {
          command: "polyline",
          x: [0, 1],
          y: [1, 1],
        },
      ],
    },
    {
      command: "r",
      commands: [
        {
          command: "strokeStyle",
          color: { red: 0, green: 0, blue: 255, alpha: 255 },
        },
        {
          command: "polyline",
          x: [1, 1],
          y: [0, 1],
        },
      ],
    },
    {
      command: "l",
      commands: [
        {
          command: "strokeStyle",
          color: { red: 0, green: 0, blue: 255, alpha: 255 },
        },
        {
          command: "polyline",
          x: [0, 0],
          y: [0, 1],
        },
      ],
    },
    {
      command: "R",
      commands: [
        {
          command: "fillStyle",
          color: { red: 255, green: 0, blue: 0, alpha: 255 },
        },
        {
          command: "polygon",
          x: [0.2, 0.2, 0.8, 0.8],
          y: [0.2, 0.8, 0.8, 0.2],
        },
      ],
    },
    {
      command: "Y",
      commands: [
        {
          command: "fillStyle",
          color: { red: 255, green: 255, blue: 0, alpha: 255 },
        },
        {
          command: "polygon",
          x: [0.2, 0.2, 0.8, 0.8],
          y: [0.2, 0.8, 0.8, 0.2],
        },
      ],
    },
  ]
}
