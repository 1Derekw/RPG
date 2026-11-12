
from drafter import *
from dataclasses import dataclass
import random
import time


# ==========================================
# GAME SETTINGS
# ==========================================

MAP_SIZE = 60
START_X = 30
START_Y = 30

TRAP_COOLDOWN = 30
SCAVENGE_COOLDOWN = 60

RESOURCE_TYPES = ["wood", "iron", "leather"]

ITEM_WEIGHTS = {
    "wood": 1,
    "iron": 2,
    "leather": 1,
    "rations": 1,
    "medicine": 1,
    "club": 4,
    "iron sword": 8
}


# ==========================================
# GAME STATE
# ==========================================

@dataclass
class State:
    player_health: int
    player_max_health: int
    player_x: int
    player_y: int

    enemy_health: int
    enemy_max_health: int
    enemy_damage: int
    enemy_name: str

    message: str
    game_over: bool
    victory: bool
    in_encounter: bool
    screen: str

    terrain: list
    explored: list
    permanent_explored: list
    expedition_explored: list

    houses: list
    strongholds: list
    searched_locations: list
    secured_locations: list
    completed_strongholds: list
    roads: list

    inventory: dict
    storage: dict
    capacity: int

    weapon_name: str
    weapon_weight: int

    movement_steps: int
    trap_count: int
    last_trap_time: float
    last_scavenge_time: float

    event_log: list

    selected_attacks: list
    selected_healing: list
    turn_number: int

    discovered_materials: list

    current_location: tuple
    location_stage: int


# ==========================================
# EVENT LOG
# ==========================================

def add_log(state, message):
    state.event_log.append(message)

    if len(state.event_log) > 10:
        state.event_log.pop(0)


def event_log_content(state):
    content = [Header("EVENT LOG")]

    # Show each event on its own line, newest first.
    for message in reversed(state.event_log):
        content.append(Text(message))

    return content


# ==========================================
# INVENTORY
# ==========================================

def item_weight(item):
    return ITEM_WEIGHTS.get(item, 0)


def inventory_weight(state):
    total = 0

    for item, amount in state.inventory.items():
        total += item_weight(item) * amount

    return total


def add_item(state, item, amount):
    added = 0

    for i in range(amount):
        if inventory_weight(state) + item_weight(item) <= state.capacity:
            state.inventory[item] = state.inventory.get(item, 0) + 1
            added += 1
        else:
            break

    return added


def remove_item(state, item, amount):
    if state.inventory.get(item, 0) < amount:
        return False

    state.inventory[item] -= amount

    if state.inventory[item] <= 0:
        del state.inventory[item]

    return True


def deposit_inventory(state):
    for item, amount in state.inventory.items():
        state.storage[item] = state.storage.get(item, 0) + amount

    state.inventory = {}


def storage_has(state, item, amount):
    return state.storage.get(item, 0) >= amount


def transfer_to_inventory(state, item):
    if state.storage.get(item, 0) <= 0:
        state.message = "There is none of that item in storage."
        return

    if add_item(state, item, 1) == 0:
        state.message = "You do not have enough carrying capacity."
        return

    state.storage[item] -= 1

    if state.storage[item] <= 0:
        del state.storage[item]

    state.message = "Moved 1 " + item + " into your inventory."


def transfer_to_storage(state, item):
    if state.inventory.get(item, 0) <= 0:
        state.message = "You are not carrying any of that item."
        return

    remove_item(state, item, 1)
    state.storage[item] = state.storage.get(item, 0) + 1
    state.message = "Moved 1 " + item + " into storage."


# ==========================================
# HEALTH BAR
# ==========================================

def health_bar(current_health, max_health):
    filled = current_health * 10 // max_health
    empty = 10 - filled

    return "[" + "#" * filled + "-" * empty + "]"


# ==========================================
# EVASION
# ==========================================

def evades_attack():
    return random.randint(1, 10) == 1


# ==========================================
# COMBAT SETUP
# ==========================================

def start_combat(state, enemy_name="Skeleton",
                 enemy_health=60, enemy_damage=5):

    state.enemy_name = enemy_name
    state.enemy_health = enemy_health
    state.enemy_max_health = enemy_health
    state.enemy_damage = enemy_damage

    state.in_encounter = True
    state.game_over = False
    state.victory = False

    state.selected_attacks = []
    state.selected_healing = []

    state.message = enemy_name + " appears! Prepare for battle!"
    add_log(state, state.message)


def attack_available(state, attack_name):
    if attack_name == "Punch":
        return True

    if attack_name == "Club":
        return state.inventory.get("club", 0) > 0

    if attack_name == "Iron Sword":
        owns_sword = state.inventory.get("iron sword", 0) > 0
        sword_ready = state.turn_number % 2 == 0
        return owns_sword and sword_ready

    return False


def healing_available(state, item):
    return state.inventory.get(item, 0) > 0


# ==========================================
# DEATH
# ==========================================

def player_dies(state):
    state.game_over = True
    state.victory = False
    state.in_encounter = False

    state.player_health = state.player_max_health
    state.inventory = {}

    state.player_x = START_X
    state.player_y = START_Y

    state.explored = list(state.permanent_explored)
    state.expedition_explored = []

    state.searched_locations = list(state.secured_locations)

    state.selected_attacks = []
    state.selected_healing = []

    state.screen = "camp"

    state.message = (
        "Your journey comes to an abrupt end. "
        "You awaken at the campsite, stripped of your carried items."
    )

    add_log(state, "You were defeated and returned to camp.")


# ==========================================
# ENEMY TURN
# ==========================================

def enemy_turn(state):
    if state.game_over:
        return

    if evades_attack():
        message = "You evaded the attack!"
    else:
        state.player_health -= state.enemy_damage

        if state.player_health < 0:
            state.player_health = 0

        message = (
            state.enemy_name + " attacks for "
            + str(state.enemy_damage) + " damage!"
        )

    state.message += "\n" + message
    add_log(state, message)

    if state.player_health <= 0:
        player_dies(state)


# ==========================================
# COMBAT: SELECT ATTACKS
# ==========================================

def toggle_attack(state, attack_name):
    if not attack_available(state, attack_name):
        state.message = attack_name + " is not available."
        return index(state)

    if attack_name in state.selected_attacks:
        state.selected_attacks.remove(attack_name)
        state.message = attack_name + " deselected."
    else:
        state.selected_attacks.append(attack_name)
        state.message = attack_name + " selected."

    return index(state)


@route
def select_punch(state):
    return toggle_attack(state, "Punch")


@route
def select_club(state):
    return toggle_attack(state, "Club")


@route
def select_sword(state):
    return toggle_attack(state, "Iron Sword")


# ==========================================
# COMBAT: SELECT HEALING
# ==========================================

def toggle_healing(state, item):
    if not healing_available(state, item):
        state.message = "You do not have any " + item + "."
        return index(state)

    if item in state.selected_healing:
        state.selected_healing.remove(item)
        state.message = item.title() + " deselected."
    else:
        state.selected_healing.append(item)
        state.message = item.title() + " selected."

    return index(state)


@route
def select_ration(state):
    return toggle_healing(state, "rations")


@route
def select_medicine(state):
    return toggle_healing(state, "medicine")


# ==========================================
# COMBAT: END TURN
# ==========================================

def resolve_turn(state):
    if state.game_over:
        return

    turn_messages = []

    # Healing happens before attacks.
    if "rations" in state.selected_healing:
        if remove_item(state, "rations", 1):
            state.player_health += 10
            turn_messages.append("Ration restored 10 health.")

    if "medicine" in state.selected_healing:
        if remove_item(state, "medicine", 1):
            state.player_health += 50
            turn_messages.append("Medicine restored 50 health.")

    if state.player_health > state.player_max_health:
        state.player_health = state.player_max_health

    # Apply selected attacks.
    attacks = list(state.selected_attacks)

    for attack_name in attacks:
        if state.enemy_health <= 0:
            break

        if attack_name == "Punch":
            state.enemy_health -= 15
            state.player_health -= 5
            turn_messages.append(
                "Punch dealt 15 damage. You took 5 self-damage."
            )

        elif attack_name == "Club":
            if attack_available(state, "Club"):
                state.enemy_health -= 10
                turn_messages.append("Club dealt 10 damage.")

        elif attack_name == "Iron Sword":
            if attack_available(state, "Iron Sword"):
                state.enemy_health -= 25
                turn_messages.append("Iron Sword dealt 25 damage.")

        if state.player_health <= 0:
            state.player_health = 0
            break

    if state.enemy_health < 0:
        state.enemy_health = 0

    if state.player_health <= 0:
        state.message = "\n".join(turn_messages)

        for message in turn_messages:
            add_log(state, message)

        player_dies(state)
        return

    # Check whether the enemy was defeated.
    if state.enemy_health <= 0:
        state.game_over = True
        state.victory = True

        turn_messages.append("You defeated the " + state.enemy_name + "!")

        if random.randint(1, 2) == 1:
            material = random.choice(RESOURCE_TYPES)

            if material not in state.discovered_materials:
                state.discovered_materials.append(material)

            added = add_item(state, material, 1)

            if added:
                turn_messages.append(
                    "The enemy dropped 1 " + material + "."
                )
            else:
                turn_messages.append(
                    "The enemy dropped " + material
                    + ", but you could not carry it."
                )

        state.message = "\n".join(turn_messages)

        for message in turn_messages:
            add_log(state, message)

        state.selected_attacks = []
        state.selected_healing = []
        return

    if not turn_messages:
        turn_messages.append("You chose not to use any items or attacks.")

    state.message = "\n".join(turn_messages)

    for message in turn_messages:
        add_log(state, message)

    enemy_turn(state)

    state.turn_number += 1
    state.selected_attacks = []
    state.selected_healing = []


@route
def end_turn(state):
    resolve_turn(state)

    if state.screen == "camp":
        return camp_page(state)

    return index(state)


# ==========================================
# COMBAT PAGE
# ==========================================

@route
@route
def index(state):

    # If the player isn't fighting, show the campsite.
    if not state.in_encounter and not state.game_over:
        return camp_page(state)

    state.screen = "battle"

    content = event_log_content(state) + [
        Header("THE DUNGEON"),

        Header("Player"),
        Text(
            "Health: " + str(state.player_health)
            + " / " + str(state.player_max_health)
        ),
        Text(
            health_bar(
                state.player_health,
                state.player_max_health
            )
        ),

        Header(state.enemy_name),
        Text(
            "Health: " + str(state.enemy_health)
            + " / " + str(state.enemy_max_health)
        ),
        Text(
            health_bar(
                state.enemy_health,
                state.enemy_max_health
            )
        ),

        Header("Healing Items"),
        Text("Rations: " + str(state.inventory.get("rations", 0))),
        Text("Medicine: " + str(state.inventory.get("medicine", 0)))
    ]

    if "rations" in state.selected_healing:
        ration_label = "✓ Ration selected"
    else:
        ration_label = "Ration (+10 HP)"

    if "medicine" in state.selected_healing:
        medicine_label = "✓ Medicine selected"
    else:
        medicine_label = "Medicine (+50 HP)"

    content.append(
        Button(
            ration_label,
            "select_ration",
            disabled=not healing_available(state, "rations")
        )
    )

    content.append(
        Button(
            medicine_label,
            "select_medicine",
            disabled=not healing_available(state, "medicine")
        )
    )

    content.append(Header("Attacks"))

    if "Punch" in state.selected_attacks:
        punch_label = "✓ Punch selected"
    else:
        punch_label = "Punch (15 damage, 5 self-damage)"

    content.append(Button(punch_label, "select_punch"))

    if attack_available(state, "Club"):
        if "Club" in state.selected_attacks:
            club_label = "✓ Club selected"
        else:
            club_label = "Club (10 damage)"

        content.append(Button(club_label, "select_club"))

    if state.inventory.get("iron sword", 0) > 0:
        if attack_available(state, "Iron Sword"):
            if "Iron Sword" in state.selected_attacks:
                sword_label = "✓ Iron Sword selected"
            else:
                sword_label = "Iron Sword (25 damage)"

            content.append(Button(sword_label, "select_sword"))
        else:
            content.append(Text("Iron Sword is resting this turn."))

    content.append(Header("End of Turn"))
    content.append(Button("End of Turn", "end_turn"))

    if state.game_over:
        if state.victory:
            content.append(Header("VICTORY!"))
            content.append(Button("Return to Map", "return_to_map"))
        else:
            content.append(Header("DEFEAT"))
            content.append(Button("Return to Camp", "return_to_camp"))

    return Page(state, content)


# ==========================================
# TERRAIN
# ==========================================

def create_terrain():
    rng = random.Random(42)
    terrain = []

    # Mostly open dirt and grass.
    symbols = [".", ",", ",", ",", "."]

    for y in range(MAP_SIZE):
        row = ""

        for x in range(MAP_SIZE):
            row += rng.choice(symbols)

        terrain.append(list(row))

    # Add fixed 6-by-6 terrain patches.
    patches = [
        (5, 7, "~"),
        (19, 5, "/"),
        (38, 12, "/"),
        (9, 29, "^"),
        (29, 35, ";"),
        (46, 45, "~"),
        (4, 48, "/")
    ]

    for start_x, start_y, symbol in patches:
        for y in range(start_y, min(start_y + 6, MAP_SIZE)):
            for x in range(start_x, min(start_x + 6, MAP_SIZE)):
                terrain[y][x] = symbol

    return ["".join(row) for row in terrain]


# ==========================================
# LOCATIONS
# ==========================================

def create_locations():
    houses = [
        (20, 20),
        (40, 18),
        (17, 43),
        (43, 39)
    ]

    strongholds = [
        (12, 12),
        (48, 46)
    ]

    return houses, strongholds


# ==========================================
# MAP REVEAL
# ==========================================

def reveal_area(state):
    offsets = [
        (-1, -2), (0, -2), (1, -2),
        (-2, -1), (-1, -1), (0, -1),
        (1, -1), (2, -1),
        (-2, 0), (-1, 0), (0, 0), (1, 0), (2, 0),
        (-2, 1), (-1, 1), (0, 1),
        (1, 1), (2, 1),
        (-1, 2), (0, 2), (1, 2)
    ]

    for dx, dy in offsets:
        x = state.player_x + dx
        y = state.player_y + dy

        if 0 <= x < MAP_SIZE and 0 <= y < MAP_SIZE:
            location = (x, y)

            if location not in state.explored:
                state.explored.append(location)

            if location not in state.expedition_explored:
                state.expedition_explored.append(location)


def map_symbol(state, x, y):
    location = (x, y)

    if x == state.player_x and y == state.player_y:
        return "@"

    if location == (START_X, START_Y):
        return "C"

    if location in state.roads:
        return "#"

    if location not in state.explored:
        return " "

    if location in state.completed_strongholds:
        return "O"

    if location in state.strongholds:
        return "S"

    if location in state.houses:
        return "H"

    return state.terrain[y][x]


# ==========================================
# MAP PAGE
# ==========================================

@route
def map_page(state):
    state.screen = "map"
    reveal_area(state)

    board = []

    for y in range(MAP_SIZE):
        row = ""

        for x in range(MAP_SIZE):
            row += map_symbol(state, x, y)

        board.append(row)

    content = event_log_content(state) + [
        Header("DUNGEON EXPLORATION"),
        Text("Use the arrow keys to move."),
        Text(
            "Rations: "
            + str(state.inventory.get("rations", 0))
        ),
        Text(
            "Capacity: "
            + str(inventory_weight(state))
            + " / "
            + str(state.capacity)
        ),
        PreformattedText(
            "\n".join(board),
            id="dungeon_map_active"
        ),

        Button("UP", "move_up", id="move_up_button", hidden=True),
        Button("DOWN", "move_down", id="move_down_button", hidden=True),
        Button("LEFT", "move_left", id="move_left_button", hidden=True),
        Button("RIGHT", "move_right", id="move_right_button", hidden=True)
    ]

    return Page(
        state,
        content,
        css="""
        #dungeon_map_active {
            font-family: monospace;
            font-size: 8px;
            line-height: 8px;
            letter-spacing: 0px;
            white-space: pre;
        }
        """,
        js="""
        document.onkeydown = function(event) {
            if (!document.getElementById("dungeon_map_active")) {
                return;
            }

            const buttons = {
                "ArrowUp": "move_up_button",
                "ArrowDown": "move_down_button",
                "ArrowLeft": "move_left_button",
                "ArrowRight": "move_right_button"
            };

            const buttonId = buttons[event.key];

            if (buttonId) {
                event.preventDefault();

                const button = document.getElementById(buttonId);

                if (button) {
                    button.click();
                }
            }
        };
        """
    )


# ==========================================
# MOVEMENT
# ==========================================

def terrain_description(state):
    symbol = state.terrain[state.player_y][state.player_x]

    descriptions = {
        ".": "You walk across open dirt.",
        ",": "Grass moves gently around your feet.",
        ";": "Thick brush surrounds you.",
        "/": "Trees surround you in a quiet forest.",
        "^": "Rocky ground stretches beneath your feet.",
        "~": "Water stretches out before you."
    }

    return descriptions.get(symbol, "You continue exploring.")


def move_player_in_direction(state, direction):
    old_x = state.player_x
    old_y = state.player_y

    if direction == "up" and state.player_y > 0:
        state.player_y -= 1
    elif direction == "down" and state.player_y < MAP_SIZE - 1:
        state.player_y += 1
    elif direction == "left" and state.player_x > 0:
        state.player_x -= 1
    elif direction == "right" and state.player_x < MAP_SIZE - 1:
        state.player_x += 1

    moved = old_x != state.player_x or old_y != state.player_y

    if not moved:
        return map_page(state)

    state.movement_steps += 1

    # Consume one ration every three successful moves.
    if state.movement_steps % 3 == 0:
        if state.inventory.get("rations", 0) > 0:
            remove_item(state, "rations", 1)
            add_log(state, "You consumed one ration.")

            if state.inventory.get("rations", 0) == 3:
                add_log(state, "Rations limited.")
        else:
            add_log(state, "Starvation sets in.")
            player_dies(state)
            return camp_page(state)

    reveal_area(state)

    # Reaching camp automatically returns the player home.
    if (state.player_x, state.player_y) == (START_X, START_Y):
        return return_to_camp(state)

    description = terrain_description(state)
    state.message = description
    add_log(state, description)

    location = (state.player_x, state.player_y)

    if location in state.houses or location in state.strongholds:
        state.current_location = location
        return location_page(state)

    # Roads are safe. Other terrain has an 8% encounter chance.
    if location not in state.roads:
        if random.randint(1, 100) <= 8:
            start_combat(state)
            return index(state)

    return map_page(state)


@route
def move_up(state):
    return move_player_in_direction(state, "up")


@route
def move_down(state):
    return move_player_in_direction(state, "down")


@route
def move_left(state):
    return move_player_in_direction(state, "left")


@route
def move_right(state):
    return move_player_in_direction(state, "right")


# ==========================================
# LOCATION PAGE
# ==========================================

@route
def location_page(state):
    location = state.current_location

    if location in state.strongholds:
        name = "Stronghold"
    else:
        name = "House"

    content = event_log_content(state) + [
        Header(name),
        Text("You have reached a " + name.lower() + "."),
        Text("Would you like to explore it or leave?")
    ]

    if location in state.searched_locations:
        content.append(Text("You have already explored this location."))
    else:
        content.append(Button("Explore", "explore_location"))

    content.append(Button("Leave", "leave_location"))

    return Page(state, content)


@route
def leave_location(state):
    state.message = "You leave the location behind."
    add_log(state, state.message)
    return map_page(state)


@route
def explore_location(state):
    location = state.current_location

    if location in state.searched_locations:
        state.message = "You have already explored this location."
        return location_page(state)

    start_combat(state, "Location Guard", 60, 5)
    state.location_stage = 1

    return index(state)


# ==========================================
# RETURN TO MAP AFTER COMBAT
# ==========================================

@route
def return_to_map(state):
    state.in_encounter = False
    state.game_over = False
    state.victory = False

    if state.location_stage == 1:
        location = state.current_location

        wood = random.randint(2, 4)
        iron = random.randint(1, 2)
        leather = random.randint(1, 2)

        for item in ["wood", "iron", "leather"]:
            if item not in state.discovered_materials:
                state.discovered_materials.append(item)

        add_item(state, "wood", wood)
        add_item(state, "iron", iron)
        add_item(state, "leather", leather)

        state.searched_locations.append(location)

        if location in state.strongholds:
            if location not in state.completed_strongholds:
                state.completed_strongholds.append(location)
                build_road(state, location)

            state.message = (
                "You conquered the stronghold! "
                "A permanent road now leads back to camp."
            )
        else:
            state.message = "You explored the house and found supplies."

        add_log(state, state.message)
        state.location_stage = 0

    else:
        state.message = "You continue exploring the dungeon."
        add_log(state, state.message)

    return map_page(state)


# ==========================================
# STRONGHOLD ROAD
# ==========================================

def build_road(state, location):
    x, y = location

    for road_x in range(min(x, START_X), max(x, START_X) + 1):
        point = (road_x, y)

        if point not in state.roads:
            state.roads.append(point)

    for road_y in range(min(y, START_Y), max(y, START_Y) + 1):
        point = (START_X, road_y)

        if point not in state.roads:
            state.roads.append(point)


# ==========================================
# CAMP PAGE
# ==========================================

@route
def camp_page(state):
    state.screen = "camp"

    content = event_log_content(state) + [
        Header("THE CAMPSITE"),
        Text("You are safe here."),

        Header("Player"),
        Text("Health: " + str(state.player_health)),
        Text("Carrying capacity: " + str(state.capacity)),
        Text(
            "Current weight: "
            + str(inventory_weight(state))
            + " / " + str(state.capacity)
        ),

        Button("Explore", "explore"),
        Button("Storage", "storage_page"),

        Header("Camp Activities"),
        Button("Set / Collect Traps", "use_traps"),
        Button("Scavenge for Wood", "scavenge"),

        Button("Craft Medicine (5 Rations)", "craft_medicine"),
        Button("Craft Club", "craft_club"),
        Button("Craft Iron Sword", "craft_sword"),
        Button("Craft Leather Backpack", "craft_backpack"),
        Button("Upgrade to Convoy", "upgrade_convoy"),
        Button("Upgrade Trap Capacity", "upgrade_traps")
    ]

    if state.message:
        content.append(Text(state.message))

    return Page(state, content)


# ==========================================
# STORAGE PAGE
# ==========================================

@route
def storage_page(state):
    content = event_log_content(state) + [
        Header("CAMPSITE STORAGE"),
        Text("Use - to store one carried item."),
        Text("Use + to take one stored item."),
        Header("Carried Inventory")
    ]

    all_items = [
        "wood", "iron", "leather",
        "rations", "medicine", "club", "iron sword"
    ]

    store_routes = {
        "wood": "store_wood",
        "iron": "store_iron",
        "leather": "store_leather",
        "rations": "store_rations",
        "medicine": "store_medicine",
        "club": "store_club",
        "iron sword": "store_sword"
    }

    take_routes = {
        "wood": "take_wood",
        "iron": "take_iron",
        "leather": "take_leather",
        "rations": "take_rations",
        "medicine": "take_medicine",
        "club": "take_club",
        "iron sword": "take_sword"
    }

    for item in all_items:
        amount = state.inventory.get(item, 0)

        if amount > 0:
            content.append(
                Div(
                    Text(item.title() + ": " + str(amount)),
                    Button("-", store_routes[item])
                )
            )
        else:
            content.append(Text(item.title() + ": 0"))

    content.append(
        Text(
            "Carrying weight: "
            + str(inventory_weight(state))
            + " / " + str(state.capacity)
        )
    )

    content.append(Header("Stored Items"))

    for item in all_items:
        amount = state.storage.get(item, 0)

        if amount > 0:
            content.append(
                Div(
                    Text(item.title() + ": " + str(amount)),
                    Button("+", take_routes[item])
                )
            )
        else:
            content.append(Text(item.title() + ": 0"))

    content.append(Button("Back to Camp", "camp_page"))

    if state.message:
        content.append(Text(state.message))

    return Page(state, content)


# ==========================================
# STORAGE TRANSFER ROUTES
# ==========================================

@route
def store_wood(state):
    transfer_to_storage(state, "wood")
    return storage_page(state)


@route
def store_iron(state):
    transfer_to_storage(state, "iron")
    return storage_page(state)


@route
def store_leather(state):
    transfer_to_storage(state, "leather")
    return storage_page(state)


@route
def store_rations(state):
    transfer_to_storage(state, "rations")
    return storage_page(state)


@route
def store_medicine(state):
    transfer_to_storage(state, "medicine")
    return storage_page(state)


@route
def store_club(state):
    transfer_to_storage(state, "club")
    return storage_page(state)


@route
def store_sword(state):
    transfer_to_storage(state, "iron sword")
    return storage_page(state)


@route
def take_wood(state):
    transfer_to_inventory(state, "wood")
    return storage_page(state)


@route
def take_iron(state):
    transfer_to_inventory(state, "iron")
    return storage_page(state)


@route
def take_leather(state):
    transfer_to_inventory(state, "leather")
    return storage_page(state)


@route
def take_rations(state):
    transfer_to_inventory(state, "rations")
    return storage_page(state)


@route
def take_medicine(state):
    transfer_to_inventory(state, "medicine")
    return storage_page(state)


@route
def take_club(state):
    transfer_to_inventory(state, "club")
    return storage_page(state)


@route
def take_sword(state):
    transfer_to_inventory(state, "iron sword")
    return storage_page(state)


# ==========================================
# EXPLORE
# ==========================================

@route
def explore(state):
    state.player_x = START_X
    state.player_y = START_Y

    state.game_over = False
    state.victory = False
    state.in_encounter = False

    state.movement_steps = 0
    state.expedition_explored = []

    state.screen = "map"

    add_log(state, "You leave camp and begin exploring.")

    return map_page(state)


# ==========================================
# RETURN TO CAMP
# ==========================================

@route
def return_to_camp(state):
    if (state.player_x, state.player_y) != (START_X, START_Y):
        state.message = "You must walk back to the campsite."
        return map_page(state)

    state.permanent_explored = list(state.explored)
    state.expedition_explored = []

    state.secured_locations = list(state.searched_locations)

    deposit_inventory(state)

    state.in_encounter = False
    state.game_over = False
    state.victory = False

    state.screen = "camp"

    state.message = "A familiar home is found."
    add_log(state, state.message)

    return camp_page(state)


# ==========================================
# TRAPS
# ==========================================

@route
def use_traps(state):
    current_time = time.time()

    # If traps have not been set, set them.
    if state.last_trap_time <= 0:
        state.last_trap_time = current_time

        state.message = (
            "You set " + str(state.trap_count)
            + " trap(s). Return in 30 seconds to collect."
        )

        add_log(state, state.message)
        return camp_page(state)

    # Check how much time has passed.
    elapsed = current_time - state.last_trap_time

    if elapsed < TRAP_COOLDOWN:
        remaining = int(TRAP_COOLDOWN - elapsed) + 1

        state.message = (
            "Your traps need "
            + str(remaining)
            + " more seconds."
        )

        return camp_page(state)

    # Collect the rations.
    total_rations = 0

    for i in range(state.trap_count):
        total_rations += random.randint(1, 3)

    added = add_item(state, "rations", total_rations)

    # Reset the trap timer.
    state.last_trap_time = 0

    state.message = (
        "You collected " + str(added)
        + " rations from your traps!"
    )

    add_log(state, state.message)

    return camp_page(state)


# ==========================================
# SCAVENGE
# ==========================================

@route
def scavenge(state):
    current_time = time.time()

    if state.last_scavenge_time > 0:
        elapsed = current_time - state.last_scavenge_time

        if elapsed < SCAVENGE_COOLDOWN:
            remaining = int(SCAVENGE_COOLDOWN - elapsed) + 1

            state.message = (
                "You must wait "
                + str(remaining)
                + " seconds before scavenging again."
            )

            return camp_page(state)

    amount = random.randint(2, 3)
    added = add_item(state, "wood", amount)

    state.last_scavenge_time = current_time

    state.message = (
        "You scavenged " + str(added) + " pieces of wood!"
    )

    add_log(state, state.message)

    return camp_page(state)


# ==========================================
# CRAFTING
# ==========================================

@route
def craft_medicine(state):
    if not storage_has(state, "rations", 5):
        state.message = "You need 5 stored rations."
        return camp_page(state)

    state.storage["rations"] -= 5

    if state.storage["rations"] == 0:
        del state.storage["rations"]

    state.storage["medicine"] = (
        state.storage.get("medicine", 0) + 1
    )

    state.message = "You crafted 1 medicine!"
    add_log(state, state.message)

    return camp_page(state)


@route
def craft_club(state):
    if not storage_has(state, "wood", 3):
        state.message = "You need 3 stored wood."
        return camp_page(state)

    state.storage["wood"] -= 3

    state.inventory["club"] = (
        state.inventory.get("club", 0) + 1
    )

    state.message = "You crafted a club!"
    add_log(state, state.message)

    return camp_page(state)


@route
def craft_sword(state):
    if not storage_has(state, "iron", 2):
        state.message = "You need 2 stored iron."
        return camp_page(state)

    if not storage_has(state, "wood", 1):
        state.message = "You need 1 stored wood."
        return camp_page(state)

    state.storage["iron"] -= 2
    state.storage["wood"] -= 1

    state.inventory["iron sword"] = (
        state.inventory.get("iron sword", 0) + 1
    )

    state.message = "You crafted an Iron Sword!"
    add_log(state, state.message)

    return camp_page(state)


@route
def craft_backpack(state):
    if state.capacity >= 40:
        state.message = "You already have a backpack upgrade."
        return camp_page(state)

    if not storage_has(state, "leather", 5):
        state.message = "You need 5 stored leather."
        return camp_page(state)

    state.storage["leather"] -= 5
    state.capacity = 40

    state.message = "You crafted a leather backpack. Capacity is now 40."
    add_log(state, state.message)

    return camp_page(state)


@route
def upgrade_convoy(state):
    if state.capacity >= 80:
        state.message = "You already have maximum carrying capacity."
        return camp_page(state)

    if not storage_has(state, "wood", 10):
        state.message = "You need 10 stored wood."
        return camp_page(state)

    if not storage_has(state, "leather", 5):
        state.message = "You need 5 stored leather."
        return camp_page(state)

    state.storage["wood"] -= 10
    state.storage["leather"] -= 5

    state.capacity = 80

    state.message = "Your convoy is ready! Capacity is now 80."
    add_log(state, state.message)

    return camp_page(state)


@route
def upgrade_traps(state):
    if state.trap_count >= 5:
        state.message = "You already have the maximum of 5 traps."
        return camp_page(state)

    if not storage_has(state, "wood", 2):
        state.message = "You need 2 stored wood."
        return camp_page(state)

    state.storage["wood"] -= 2
    state.trap_count += 1

    state.message = (
        "You upgraded your trap capacity to "
        + str(state.trap_count) + " traps!"
    )

    add_log(state, state.message)

    return camp_page(state)


# ==========================================
# START GAME
# ==========================================

houses, strongholds = create_locations()

initial_explored = [
    (x, y)
    for y in range(28, 33)
    for x in range(28, 33)
    if not (
        (x == 28 and y == 28)
        or (x == 32 and y == 28)
        or (x == 28 and y == 32)
        or (x == 32 and y == 32)
    )
]

start_server(
    State(
        # Player
        100,
        100,
        START_X,
        START_Y,

        # Enemy
        80,
        80,
        5,
        "Skeleton",

        # Game status
        "Welcome to the campsite.",
        False,
        False,
        False,
        "camp",

        # Map
        create_terrain(),
        list(initial_explored),
        list(initial_explored),
        [],

        # Locations
        houses,
        strongholds,
        [],
        [],
        [],
        [],

        # Inventory
        {
            "rations": 6,
            "medicine": 1,
            "club": 0,
            "iron sword": 0
        },

        # Storage
        {
            "wood": 0,
            "iron": 0,
            "leather": 0,
            "rations": 0,
            "medicine": 0,
            "club": 0,
            "iron sword": 0
        },

        # Capacity
        20,

        # Equipment
        "Fists",
        0,

        # Survival
        0,
        1,
        0,
        0,

        # Event Log
        ["You awaken at a familiar campsite."],

        # Combat selections
        [],
        [],
        0,

        # Crafting discovery
        [],

        # Location exploration
        (0, 0),
        0
    ),
    theme="terminal",
    site_title="THE DUNGEON"
)

