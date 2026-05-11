# AgentAvocadoClaude — Implementation Plan

## Steps (check off as done)

- [x] Read codebase: understand Board API, color quirk, move semantics
- [x] Add `AgentAvocadoClaude` class to `squares.js`
- [x] Register agent in `index.html` setPlayers
- [ ] Verify no syntax errors (open in browser, check console)

---

## Design decisions (locked)

**Color quirk**: `move(board,r,c,s,color)` stores captured cells as `ocolor` (opposite).
- Red plays `colorInt=-1` → cells stored as `-2` → `myFill = -2`
- Yellow plays `colorInt=-2` → cells stored as `-1` → `myFill = -1`
- evalScore counts `myFill` cells as mine, `colorInt` cells as theirs (oppFill = colorInt)

**No bonus turn**: always alternates, so minimax just flips `myTurn` each ply.

**Eval**: `mine - theirs` (absolute captured square difference).

## Layer stack

| # | Condition | Action |
|---|---|---|
| 1 | Winning moves exist | Take first winning move immediately |
| 2 | Time budget set | Run iterative-deepening minimax (depth 1..12) |
| 3 | Minimax timed out before depth=1 | Chain fallback: open shortest chain |

**Move ordering in minimax**: winning → safe → desperate (maximizes alpha-beta cutoffs)

**Time budget per move**: `min((remaining_time / remaining_moves) * 0.7, 2000 ms)`

---

## Key methods

- `countLines(board, r, c)` → int (−1=OOB, 0–3=lines, 4=captured)
- `categorizeMove(board, r, c, s)` → `'w'|'s'|'d'` (winning/safe/desperate)
- `evalScore(board)` → int (my_captures − opp_captures)
- `detectChains(board)` → BFS groups of connected 3-sided free cells
- `openShortestChain(board, moves)` → move that minimizes max post-move chain length
- `minimax(board, depth, α, β, myTurn, deadline)` → {score, move}
- `compute(board, time)` → [row, col, side]
