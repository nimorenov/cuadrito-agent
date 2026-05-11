# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the game

No build step. Open `index.html` directly in a browser. It loads Konekti from CDN and `squares.js` from disk.

In the UI: enter agent names (matching keys in `setPlayers`), board size (integer), and time (seconds), then click play.

## Architecture

Two files: `index.html` (UI wiring) and `squares.js` (all game logic).

### Core classes in `squares.js`

| Class | Role |
|---|---|
| `Agent` | Abstract base. Override `compute(board, time)` → `[row, col, side]` |
| `Board` | Stateless utility: `init`, `clone`, `valid_moves`, `check`, `move`, `fill`, `winner`, `print` |
| `Environment` | Game loop. Reads UI inputs, alternates turns, tracks per-player time budgets |
| `RandomPlayer` | Baseline: picks a random valid move |
| `AgentAvocadoGemini` | Greedy heuristic: winning moves → safe moves → desperate moves |
| `AgentAvocadoRandom` | Stub: has `countLines` but `compute` is pure random — identical behavior to `RandomPlayer` |

### Board encoding

Each cell is an integer bitmask (0–15) of drawn sides: bit 0=up, bit 1=right, bit 2=down, bit 3=left. Border cells are initialized with their boundary bits pre-set. Captured cells are negative: `-1` = Red, `-2` = Yellow.

`Board.move()` propagates neighbor bits and calls `fill()` to mark captured squares. `fill()` is recursive and can chain-capture adjacent squares that were already at 3 sides.

**Known quirk**: `move()` calls `fill()` with `ocolor` (the opposite of the current player). Red's captures are stored as `-2`, Yellow's as `-1` — swapped from what the variable names suggest. Both players are affected symmetrically so win/loss outcomes are still correct; only the square color rendering is inverted.

### Game rules (from code)

- **No bonus turn**: `Environment` always switches player after each move, even if a square was captured. This differs from classic Dots and Boxes.
- **Multi-capture in one move**: Drawing a line shared between two 3-sided cells captures both simultaneously via `fill()` propagation.
- **Win**: Most captured squares when the board is full. Tie if equal.
- **Time loss**: Player whose remaining milliseconds hit 0 loses immediately.

### Adding an agent

1. In `squares.js`: create a class extending `Agent`, implement `compute(board, time)` returning `[row, col, side]` (side: 0=up, 1=right, 2=down, 3=left).
2. In `index.html` `setPlayers({...})`: add `yourKey: new YourClass()`.
3. Enter `yourKey` in the UI's Red or Yellow field.

`compute` receives a **clone** of the board — mutating it is safe. `time` is remaining milliseconds for the whole game.

---

## Agent strategy analysis

### RandomPlayer / AgentAvocadoRandom

Pure random: pick a uniformly random valid move. O(n²) per turn. No strategy. Baseline only.

**Fatal flaw**: freely gives away squares with 3 sides already drawn, and misses obvious completions.

---

### AgentAvocadoGemini — greedy 1-ply

**Algorithm** (`compute`):

For every valid move `[r, c, s]`, calls `evaluateMove` which returns `max(lines_after in cell [r,c], lines_after in adjacent cell)`. Then categorizes:

| Category | Condition | Meaning |
|---|---|---|
| Winning | result == 4 | Move completes a square right now |
| Safe | result < 3 | Neither affected cell ends up with 3 sides → opponent can't immediately capture |
| Desperate | result == 3 | Forced to leave a square capturable by opponent |

**Priority**: Winning (random pick) → Safe (random pick) → Desperate (random pick).

**Strengths**:
- Never misses a free square
- Avoids gifting opponent squares when alternatives exist
- Fast: O(n²) per turn
- Consistently beats random agents

**Weaknesses**:

1. **Chain blindness (critical)**: When forced into desperate moves, picks randomly. Doesn't detect *chains* — connected sequences of squares all at 3 sides, where completing one exposes the next. Opening a 10-cell chain is catastrophically worse than opening a 2-cell chain, but Gemini treats both the same.

2. **evaluateMove checks only 1 neighbor**: Doesn't account for cascading effects. Drawing a line can make an adjacent cell 3-sided, which is next to another near-complete cell, and so on.

3. **No chain sacrifice**: In Dots and Boxes theory, a key tactic is to deliberately sacrifice a *short* chain to deny the opponent from opening *long* chains. Gemini has no concept of chain lengths or sacrifice trade-offs.

4. **No parity management**: The number of chains on the board (odd vs even) determines who is forced to open the last one. Gemini never reasons about this.

5. **Ignores time budget**: Same computation whether 20 ms or 20,000 ms remain. Doesn't use leftover time for deeper search.

---

## Ideal agent design

### Game-theoretic foundation

Since there is **no bonus turn** for capturing, the game is not identical to classic Dots and Boxes. However, chain theory still applies because:
- Opening a chain (drawing the 4th side) hands a sequence of free captures to the opponent on their next turns (each capture being a separate turn for them, but with no safe alternatives for you in between)
- The player who is forced to open chains loses the chain-control race

### Layer 1 — Immediate capture (always correct)

Take a free square whenever one exists. This is never a mistake.

### Layer 2 — Safe play

When no free square exists, prefer moves that leave all affected cells with ≤ 2 sides. This delays the chain-opening phase.

### Layer 3 — Chain detection and shortest-chain sacrifice

When no safe move exists (all moves are "desperate"):

1. **Detect chains**: BFS/DFS over the board to identify connected groups of squares with exactly 3 sides. Two adjacent cells both at 3 sides form a chain segment — completing one may expose the other.
2. **Open the shortest chain**: Minimize the number of squares given away in one "desperate" phase. Sacrifice a 2-cell chain instead of a 6-cell chain.
3. **Double-cross consideration**: For chains of length ≥ 4, consider "leaving 2 squares" (the double-cross): give the opponent 2 free captures to regain turn control and open shorter chains yourself. Only worth it when the remaining chains you control are larger.

### Layer 4 — Minimax with time budget

Use remaining `time` for iterative-deepening minimax with alpha-beta pruning:

- **Eval function**: `(my_captures - opponent_captures) + chain_parity_bonus`
- **Chain parity bonus**: reward positions where the opponent is forced to open more chains than you
- **Move ordering**: captures first (maximize pruning), then safe moves, then chain-opens by ascending chain length
- **Time management**: track wall-clock time per iteration; stop when remaining budget approaches a safety threshold

### Layer 5 — Opening parity management

In the early game when all cells have ≤ 2 sides: avoid creating 3-sided squares (same as Layer 2) but also try to influence the *number* of eventual chains. Having an odd vs even total chain count determines who opens the last (and usually longest) chain. This is the hardest layer to implement and yields diminishing returns vs. Layers 1–4.

### Ideal agent priority stack

| Priority | Action |
|---|---|
| 1 | Take any free square |
| 2 | Safe move (no 3-sided cells created) |
| 3 | Open shortest detected chain |
| 4 | Minimax w/ alpha-beta using remaining time |
| 5 | Opening: manage chain count parity |
