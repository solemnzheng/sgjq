from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Any
from collections import Counter
import math

# --- Constants ---
PIECE_RANKS = {
    "司令": 10, "军长": 9, "师长": 8, "旅长": 7, "团长": 6, "营长": 5,
    "连长": 4, "排长": 3, "工兵": 2, "地雷": 1, "炸弹": 11, "军旗": 0
}

# --- Data Classes for the World Model ---

@dataclass
class Piece:
    """Represents a single, unique piece on the board."""
    id: str
    name: str
    color: str
    player_pos: str
    rank: int = field(init=False)
    board_coords: Tuple[int, int]

    def __post_init__(self):
        self.rank = PIECE_RANKS.get(self.name, -1)

@dataclass
class BoardState:
    """Represents a complete snapshot of the board at a specific time."""
    timestamp: float
    pieces: Dict[str, Piece] = field(default_factory=dict)
    grid: Dict[Tuple[int, int], str] = field(default_factory=dict)

# --- Piece Tracker ---

class PieceTracker:
    def __init__(self):
        self._last_id_counters: Dict[str, int] = Counter()

    def get_new_id(self, piece: Piece) -> str:
        key = f"{piece.color}_{piece.name}"
        self._last_id_counters[key] += 1
        return f"{key}_{self._last_id_counters[key]}"

    def update_state(self, prev_state: Optional[BoardState], current_detections: BoardState) -> BoardState:
        if not prev_state or not prev_state.pieces:
            for piece in current_detections.pieces.values():
                piece.id = self.get_new_id(piece)
            current_detections.grid = {p.board_coords: p.id for p in current_detections.pieces.values()}
            return current_detections

        new_state = BoardState(timestamp=current_detections.timestamp)
        unmatched_new_pieces = list(current_detections.pieces.values())
        
        for prev_piece in prev_state.pieces.values():
            best_match = None
            min_dist = float('inf')
            for i, new_piece in enumerate(unmatched_new_pieces):
                if prev_piece.name == new_piece.name and prev_piece.color == new_piece.color:
                    dist = math.hypot(
                        prev_piece.board_coords[0] - new_piece.board_coords[0],
                        prev_piece.board_coords[1] - new_piece.board_coords[1]
                    )
                    if dist < 4 and dist < min_dist:
                        min_dist = dist
                        best_match = i
            
            if best_match is not None:
                matched_piece = unmatched_new_pieces.pop(best_match)
                matched_piece.id = prev_piece.id
                new_state.pieces[matched_piece.id] = matched_piece
                new_state.grid[matched_piece.board_coords] = matched_piece.id

        for new_piece in unmatched_new_pieces:
            new_piece.id = self.get_new_id(new_piece)
            new_state.pieces[new_piece.id] = new_piece
            new_state.grid[new_piece.board_coords] = new_piece.id
            
        return new_state

# --- Game Event Data Classes ---

@dataclass
class GameEvent:
    event_type: str
    timestamp: float

@dataclass
class MoveEvent(GameEvent):
    piece: Piece
    from_coords: Tuple[int, int]
    to_coords: Tuple[int, int]

@dataclass
class CaptureEvent(GameEvent):
    attacker: Piece
    defender: Piece
    coords: Tuple[int, int]

@dataclass
class TradeEvent(GameEvent):
    piece1: Piece
    piece2: Piece
    coords: Tuple[int, int]

@dataclass
class BombEvent(GameEvent):
    bomb: Piece
    target: Piece
    coords: Tuple[int, int]

@dataclass
class LandmineEvent(GameEvent):
    victim: Piece
    coords: Tuple[int, int]

# --- Game Logic Engine ---

class GameLogicEngine:
    def __init__(self):
        self.player_relationships = {
            "上方": {"allies": ["下方"], "enemies": ["左侧", "右侧"]},
            "下方": {"allies": ["上方"], "enemies": ["左侧", "右侧"]},
            "左侧": {"allies": ["右侧"], "enemies": ["上方", "下方"]},
            "右侧": {"allies": ["左侧"], "enemies": ["上方", "下方"]},
        }

    def is_enemy(self, piece1: Piece, piece2: Piece) -> bool:
        return piece2.player_pos in self.player_relationships.get(piece1.player_pos, {}).get("enemies", [])

    def compare_states(self, prev_state: BoardState, curr_state: BoardState) -> List[GameEvent]:
        events = []
        prev_ids = set(prev_state.pieces.keys())
        curr_ids = set(curr_state.pieces.keys())
        disappeared_ids = prev_ids - curr_ids
        
        if len(disappeared_ids) == 1:
            victim_id = disappeared_ids.pop()
            victim = prev_state.pieces[victim_id]
            attacker = None
            for piece in curr_state.pieces.values():
                if piece.board_coords == victim.board_coords and self.is_enemy(piece, victim):
                    attacker = piece
                    break
            if attacker:
                events.append(CaptureEvent("capture", curr_state.timestamp, attacker, victim, victim.board_coords))
            else:
                events.append(LandmineEvent("landmine", curr_state.timestamp, victim, victim.board_coords))

        elif len(disappeared_ids) == 2:
            p1_id, p2_id = disappeared_ids
            p1 = prev_state.pieces[p1_id]
            p2 = prev_state.pieces[p2_id]
            if self.is_enemy(p1, p2) and p1.board_coords == p2.board_coords:
                if p1.name == "炸弹":
                    events.append(BombEvent("bomb", curr_state.timestamp, p1, p2, p1.board_coords))
                elif p2.name == "炸弹":
                    events.append(BombEvent("bomb", curr_state.timestamp, p2, p1, p1.board_coords))
                elif p1.rank == p2.rank:
                    events.append(TradeEvent("trade", curr_state.timestamp, p1, p2, p1.board_coords))
                else:
                    attacker, defender = (p1, p2) if p1.rank > p2.rank else (p2, p1)
                    events.append(CaptureEvent("capture", curr_state.timestamp, attacker, defender, p1.board_coords))

        if not disappeared_ids:
            for piece_id, piece in curr_state.pieces.items():
                if piece_id in prev_state.pieces:
                    prev_piece = prev_state.pieces[piece_id]
                    if piece.board_coords != prev_piece.board_coords:
                        events.append(MoveEvent("move", curr_state.timestamp, piece, prev_piece.board_coords, piece.board_coords))
                        break
        return events

# --- Utility Function ---
def map_pixel_to_grid(px: int, py: int, locked_regions: Dict) -> Optional[Tuple[str, Tuple[int, int]]]:
    for region_name, bounds in locked_regions.items():
        x1, y1, x2, y2 = bounds
        if not (x1 <= px < x2 and y1 <= py < y2):
            continue
        region_w = x2 - x1
        region_h = y2 - y1
        if region_name == "中央":
            rows, cols = 3, 3
            cell_w, cell_h = region_w / cols, region_h / rows
            col = int((px - x1) / cell_w)
            row = int((py - y1) / cell_h)
            return region_name, (row, col)
        rows, cols = 6, 5
        cell_w, cell_h = region_w / cols, region_h / rows
        col = int((px - x1) / cell_w)
        row = int((py - y1) / cell_h)
        return region_name, (row, col)
    return None