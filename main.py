
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
    "iron": 4,
    "leather": 2,
    "rations": 1,
    "medicine": 4,
    "club": 3,
    "iron sword": 8,
    "shield": 5
}

ALL_ITEMS = [
    "wood", "iron", "leather", "rations",
    "medicine", "club", "iron sword", "shield"
]


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

    pending_loot: dict
    loot_return_action: str
    stronghold_progress: dict
    claimed_outposts: list
    combat_kind: str

    leather_armour: bool
    iron_armour: bool

    # New location and crafting progress
    house_progress: dict
    completed_houses: list
    iron_mines: list
    mine_progress: dict
    completed_mines: list
    iron_crafting_unlocked: bool


# ==========================================
# EVENT LOG
# ==========================================

def add_log(state, message):
    state.event_log.append(message)

    if len(state.event_log) > 10:
        state.event_log.pop(0)


def event_log_content(state):
    content = [Header("EVENT LOG")]

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
    if max_health <= 0:
        return "[----------]"

    filled = current_health * 10 // max_health
    filled = min(filled, 10)
    empty = 10 - filled

    return "[" + "#" * filled + "-" * empty + "]"


# ==========================================
# EVASION
# ==========================================

def evades_attack():
    return random.randint(1, 10) == 1


def player_evades_attack(state):
    # A shield gives the player a second evasion roll.
    if evades_attack():
        return True

    if state.inventory.get("shield", 0) > 0:
        if evades_attack():
            return True

    return False


# ==========================================
# LOOT TABLE
# ==========================================

def roll_loot(number_of_rolls=5, reroll_empty=False):
    loot = {
        "rations": 0,
        "wood": 0,
        "leather": 0,
        "medicine": 0,
        "iron": 0
    }

    successful_rolls = 0

    while successful_rolls < number_of_rolls:
        roll = random.randint(1, 100)
        found_item = False

        if roll <= 40:
            pass

        elif roll <= 65:
            loot["rations"] += random.randint(1, 2)
            found_item = True

        elif roll <= 80:
            loot["wood"] += random.randint(1, 2)
            found_item = True

        elif roll <= 90:
            loot["leather"] += random.randint(1, 2)
            found_item = True

        elif roll <= 95:
            loot["medicine"] += 1
            found_item = True

        else:
            loot["iron"] += 1
            found_item = True

        if found_item:
            successful_rolls += 1

        elif not reroll_empty:
            successful_rolls += 1

    return loot


# ==========================================
# LOOT SELECTION
# ==========================================

def take_loot_item(state, item):
    amount = state.pending_loot.get(item, 0)

    if amount <= 0:
        state.message = "There is no more " + item + " available."
        return

    added = add_item(state, item, 1)

    if added == 0:
        state.message = "You do not have enough carrying capacity."
        return

    state.pending_loot[item] -= 1

    if state.pending_loot[item] <= 0:
        del state.pending_loot[item]

    if item in RESOURCE_TYPES:
        if item not in state.discovered_materials:
            state.discovered_materials.append(item)

    state.message = "Collected 1 " + item + "."


def loot_page(state):
    state.screen = "loot"

    inventory_content = [Header("YOUR INVENTORY")]

    for item in ALL_ITEMS:
        amount = state.inventory.get(item, 0)
        inventory_content.append(
            Text(item.title() + ": " + str(amount))
        )

    inventory_content.append(
        Text(
            "Weight: " + str(inventory_weight(state))
            + " / " + str(state.capacity)
        )
    )

    loot_content = [Header("AVAILABLE LOOT")]

    for item in ALL_ITEMS:
        amount = state.pending_loot.get(item, 0)

        if amount > 0:
            loot_content.append(
                Div(
                    Text(item.title() + ": " + str(amount)),
                    Button("-", loot_routes[item])
                )
            )

    if sum(state.pending_loot.values()) == 0:
        loot_content.append(Text("No loot remains to collect."))

    content = event_log_content(state) + [
        Header("LOOT"),
        Text("Choose which items you want to carry."),
        Div(
            Div(*inventory_content, id="loot_inventory"),
            Div(*loot_content, id="loot_available"),
            id="loot_columns"
        )
    ]

    if state.message:
        content.append(Text(state.message))

    content.append(Button("Continue", "finish_loot"))

    return Page(
        state,
        content,
        css="""
        #loot_columns {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            align-items: start;
        }

        #loot_inventory, #loot_available {
            border: 1px solid #777;
            padding: 12px;
            border-radius: 6px;
            min-width: 0;
        }

        @media (max-width: 600px) {
            #loot_columns {
                grid-template-columns: 1fr;
            }
        }
        """
    )


@route
def loot_wood(state):
    take_loot_item(state, "wood")
    return loot_page(state)


@route
def loot_iron(state):
    take_loot_item(state, "iron")
    return loot_page(state)


@route
def loot_leather(state):
    take_loot_item(state, "leather")
    return loot_page(state)


@route
def loot_rations(state):
    take_loot_item(state, "rations")
    return loot_page(state)


@route
def loot_medicine(state):
    take_loot_item(state, "medicine")
    return loot_page(state)


@route
def loot_club(state):
    take_loot_item(state, "club")
    return loot_page(state)


@route
def loot_sword(state):
    take_loot_item(state, "iron sword")
    return loot_page(state)


@route
def loot_shield(state):
    take_loot_item(state, "shield")
    return loot_page(state)


loot_routes = {
    "wood": "loot_wood",
    "iron": "loot_iron",
    "leather": "loot_leather",
    "rations": "loot_rations",
    "medicine": "loot_medicine",
    "club": "loot_club",
    "iron sword": "loot_sword",
    "shield": "loot_shield"
}


# ==========================================
# FINISH LOOT
# ==========================================

@route
def finish_loot(state):
    action = state.loot_return_action

    state.pending_loot = {}
    state.loot_return_action = ""

    state.game_over = False
    state.victory = False
    state.in_encounter = False

    if action == "skeleton":
        state.message = "You leave the battlefield."
        add_log(state, state.message)
        return map_page(state)

    if action == "stronghold_first":
        key = str(state.current_location)
        state.stronghold_progress[key] = "first_guard_done"

        state.location_stage = 0
        state.message = "The first guardian is defeated."
        add_log(state, state.message)
        return location_page(state)

    if action == "stronghold_end":
        location = state.current_location

        if location not in state.completed_strongholds:
            state.completed_strongholds.append(location)

        if location not in state.searched_locations:
            state.searched_locations.append(location)

        build_road(state, location)

        state.location_stage = 0
        state.message = (
            "You reached the end of the stronghold! "
            "A permanent road now leads back to camp."
        )

        add_log(state, state.message)
        return map_page(state)

    if action == "house_first":
        key = str(state.current_location)
        state.house_progress[key] = "first_guard_done"

        state.location_stage = 0
        state.message = "The house guardian is defeated."
        add_log(state, state.message)
        return location_page(state)

    if action == "house_end":
        location = state.current_location

        if location not in state.completed_houses:
            state.completed_houses.append(location)

        if location not in state.searched_locations:
            state.searched_locations.append(location)

        state.location_stage = 0
        state.message = (
            "You finished exploring the house. "
            "The location is now secured for this expedition."
        )

        add_log(state, state.message)
        return map_page(state)

    if action == "mine_first":
        key = str(state.current_location)
        state.mine_progress[key] = "first_guard_done"

        state.location_stage = 0
        state.message = "The Iron Miner has been defeated."
        add_log(state, state.message)
        return location_page(state)

    if action == "mine_end":
        location = state.current_location

        if location not in state.completed_mines:
            state.completed_mines.append(location)

        state.iron_crafting_unlocked = True
        state.location_stage = 0

        state.message = (
            "You cleared the iron mine! Iron crafting is now unlocked. "
            "Check out the crafting area at the campfire!"
        )

        add_log(state, state.message)
        return map_page(state)

    if action == "outpost":
        location = state.current_location

        if location not in state.claimed_outposts:
            state.claimed_outposts.append(location)

        state.message = "You collected supplies from the outpost."
        add_log(state, state.message)
        return map_page(state)

    return map_page(state)


# ==========================================
# COMBAT SETUP
# ==========================================

def start_combat(state, enemy_name="Skeleton",
                 enemy_health=60, enemy_damage=5,
                 combat_kind="skeleton"):

    state.enemy_name = enemy_name
    state.enemy_health = enemy_health
    state.enemy_max_health = enemy_health
    state.enemy_damage = enemy_damage

    state.in_encounter = True
    state.game_over = False
    state.victory = False

    state.selected_attacks = []
    state.selected_healing = []

    # Reset weapon cooldowns at the beginning of every battle.
    state.turn_number = 0

    state.combat_kind = combat_kind
    state.screen = "battle"

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
# LOCATION END LOOT
# ==========================================

def reach_location_end(state, location_type):
    # Eight successful loot results. Empty rolls are rerolled.
    state.pending_loot = roll_loot(8, True)

    if location_type == "stronghold":
        state.loot_return_action = "stronghold_end"
        state.message = (
            "You have reached the end of the stronghold! "
            "Choose which supplies to carry."
        )

    elif location_type == "house":
        state.loot_return_action = "house_end"
        state.message = (
            "You have reached the end of the house! "
            "Choose which supplies to carry."
        )

    elif location_type == "mine":
        state.loot_return_action = "mine_end"
        state.message = (
            "You cleared the iron mine! Choose which supplies to carry. "
            "Afterward, check the crafting area at the campfire "
            "to see what you unlocked!"
        )

    state.in_encounter = False
    state.game_over = False
    state.victory = False

    add_log(state, state.message)
    return loot_page(state)


def reach_stronghold_end(state):
    return reach_location_end(state, "stronghold")


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

    state.pending_loot = {}
    state.loot_return_action = ""

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

    if player_evades_attack(state):
        message = "You evaded the attack!"

        if state.inventory.get("shield", 0) > 0:
            message += " Your shield helped protect you."

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

@route
def resolve_turn(state):
    if state.game_over:
        return

    turn_messages = []

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

    # Enemy defeated.
    if state.enemy_health <= 0:
        state.game_over = True
        state.victory = True
        state.in_encounter = False

        turn_messages.append("You defeated the " + state.enemy_name + "!")

        combat_kind = state.combat_kind

        if combat_kind == "skeleton":
            state.pending_loot = roll_loot(3)
            state.loot_return_action = "skeleton"

        elif combat_kind == "stronghold_first":
            state.pending_loot = roll_loot(6)
            state.loot_return_action = "stronghold_first"

        elif combat_kind == "house_first":
            state.pending_loot = roll_loot(6)
            state.loot_return_action = "house_first"

        elif combat_kind == "mine_first":
            state.pending_loot = roll_loot(6)
            state.loot_return_action = "mine_first"

        elif combat_kind == "stronghold_buff":
            state.selected_attacks = []
            state.selected_healing = []

            for message in turn_messages:
                add_log(state, message)

            return reach_location_end(state, "stronghold")

        elif combat_kind == "house_buff":
            state.selected_attacks = []
            state.selected_healing = []

            for message in turn_messages:
                add_log(state, message)

            return reach_location_end(state, "house")

        elif combat_kind == "mine_buff":
            state.selected_attacks = []
            state.selected_healing = []

            for message in turn_messages:
                add_log(state, message)

            return reach_location_end(state, "mine")

        else:
            state.pending_loot = roll_loot(3)
            state.loot_return_action = "skeleton"

        state.message = "\n".join(turn_messages)

        for message in turn_messages:
            add_log(state, message)

        state.selected_attacks = []
        state.selected_healing = []

        state.screen = "loot"
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

    if state.screen == "loot":
        return loot_page(state)

    if state.screen == "camp":
        return camp_page(state)

    return index(state)


# ==========================================
# COMBAT PAGE
# ==========================================

@route
def index(state):
    if state.screen == "loot":
        return loot_page(state)

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
        Text(health_bar(state.player_health, state.player_max_health)),

        Header(state.enemy_name),
        Text(
            "Health: " + str(state.enemy_health)
            + " / " + str(state.enemy_max_health)
        ),
        Text(health_bar(state.enemy_health, state.enemy_max_health)),

        Header("Healing Items"),
        Text("Rations: " + str(state.inventory.get("rations", 0))),
        Text("Medicine: " + str(state.inventory.get("medicine", 0))),
        Text("Shield: " + str(state.inventory.get("shield", 0)))
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

    return Page(state, content)


# ==========================================
# TERRAIN
# ==========================================

def create_terrain():
    rng = random.Random(42)
    terrain = []

    symbols = [".", ",", ",", ",", "."]

    for y in range(MAP_SIZE):
        row = ""

        for x in range(MAP_SIZE):
            row += rng.choice(symbols)

        terrain.append(list(row))

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
    # Six houses: 50% more than the original four.
    # All are closer to the campsite than the original placements.
    houses = [
        (24, 22),
        (36, 23),
        (22, 37),
        (38, 36),
        (25, 30),
        (35, 30)
    ]

    # Both strongholds are closer to camp than before.
    strongholds = [
        (18, 18),
        (40, 38)
    ]

    # One iron mine.
    iron_mines = [
        (22, 40)
    ]

    return houses, strongholds, iron_mines


def find_closest_stronghold(state):
    if not state.strongholds:
        return None

    return min(
        state.strongholds,
        key=lambda location:
            abs(location[0] - START_X)
            + abs(location[1] - START_Y)
    )


# ==========================================
# MAP REVEAL
# ==========================================

                
def reveal_area(state):
    for dy in range(-3, 4):
        for dx in range(-3, 4):

            # Remove the four outer corner tiles
            if abs(dx) == 3 and abs(dy) == 3:
                continue

            x = state.player_x + dx
            y = state.player_y + dy

            if 0 <= x < MAP_SIZE and 0 <= y < MAP_SIZE:
                if (x, y) not in state.explored:
                    state.explored.append((x, y))


def map_symbol(state, x, y):
    location = (x, y)

    # Always show the player.
    if x == state.player_x and y == state.player_y:
        return "@"

    # Always show the campsite.
    if location == (START_X, START_Y):
        return "C"

    # Always show the closest stronghold.
    closest_stronghold = find_closest_stronghold(state)

    if location == closest_stronghold:
        if location in state.completed_strongholds:
            return "O"
        return "S"

    # Show other strongholds once discovered.
    if location in state.strongholds:
        if location in state.completed_strongholds:
            return " "
        if location in state.explored:
            return "S"
        return " "

    # Show roads.
    if location in state.roads:
        return "#"

    # Hide unexplored terrain.
    if location not in state.explored:
        return " "

    # Completed houses are grayed out.
    if location in state.searched_locations:
        return "h"

    # Show unexplored houses.
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
        Text("@ = You | C = Camp | S = Stronghold | O = Completed Outpost"),
        Text("H = House | h = Completed House"),
        Text("I = Iron Mine | i = Completed Iron Mine"),
        Text("# = Road"),
        Text("Rations: " + str(state.inventory.get("rations", 0))),
        Text(
            "Capacity: " + str(inventory_weight(state))
            + " / " + str(state.capacity)
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

    if (state.player_x, state.player_y) == (START_X, START_Y):
        return return_to_camp(state)

    # Display walking messages every other step.
    description = terrain_description(state)

    if state.movement_steps % 2 == 0:
        state.message = description
        add_log(state, description)
    else:
        state.message = ""

    location = (state.player_x, state.player_y)

    if (
        location in state.houses
        or location in state.strongholds
        or location in state.iron_mines
    ):
        state.current_location = location
        return location_page(state)

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

    # STRONGHOLD
    if location in state.strongholds:
        if location in state.completed_strongholds:
            content = event_log_content(state) + [
                Header("OUTPOST"),
                Text("You have reached a secured outpost.")
            ]

            if location in state.claimed_outposts:
                content.append(
                    Text("You have already collected supplies here.")
                )
            else:
                content.append(
                    Text("There are rations available at this outpost.")
                )
                content.append(
                    Button("Collect Outpost Rations", "collect_outpost")
                )

            content.append(Button("Leave", "leave_location"))
            return Page(state, content)

        key = str(location)
        progress = state.stronghold_progress.get(key, "")

        content = event_log_content(state) + [
            Header("STRONGHOLD"),
            Text("You have reached a stronghold.")
        ]

        if progress == "first_guard_done":
            content.append(Text("The first guardian has been defeated."))
            content.append(
                Text("You can explore further or leave the stronghold.")
            )
            content.append(
                Button("Explore Further", "explore_further")
            )
        else:
            content.append(Text("A guardian stands in your way."))
            content.append(Button("Explore", "explore_location"))

        content.append(Button("Leave", "leave_location"))
        return Page(state, content)

    # IRON MINE
    if location in state.iron_mines:
        if location in state.completed_mines:
            content = event_log_content(state) + [
                Header("IRON MINE"),
                Text("This iron mine has already been cleared."),
                Text("Iron crafting is unlocked at the campsite.")
            ]
            content.append(Button("Leave", "leave_location"))
            return Page(state, content)

        key = str(location)
        progress = state.mine_progress.get(key, "")

        content = event_log_content(state) + [
            Header("IRON MINE"),
            Text("You have discovered an iron mine.")
        ]

        if progress == "first_guard_done":
            content.append(Text("The Iron Miner has been defeated."))
            content.append(
                Text("You can explore further or leave the mine.")
            )
            content.append(
                Button("Explore Further", "explore_mine_further")
            )
        else:
            content.append(
                Text("An Iron Miner is guarding the mine.")
            )
            content.append(Button("Explore", "explore_location"))

        content.append(Button("Leave", "leave_location"))
        return Page(state, content)

    # HOUSE
    if location in state.houses:
        if location in state.completed_houses:
            content = event_log_content(state) + [
                Header("HOUSE"),
                Text("You have already cleared this house.")
            ]
            content.append(Button("Leave", "leave_location"))
            return Page(state, content)

        key = str(location)
        progress = state.house_progress.get(key, "")

        content = event_log_content(state) + [
            Header("HOUSE"),
            Text("You have reached a house.")
        ]

        if progress == "first_guard_done":
            content.append(Text("The first house guardian is defeated."))
            content.append(
                Text("You can explore further or leave the house.")
            )
            content.append(
                Button("Explore Further", "explore_house_further")
            )
        else:
            content.append(Text("A guardian stands inside the house."))
            content.append(Button("Explore", "explore_location"))

        content.append(Button("Leave", "leave_location"))
        return Page(state, content)

    return map_page(state)


@route
def leave_location(state):
    state.message = "You leave the location behind."
    add_log(state, state.message)
    return map_page(state)


# ==========================================
# EXPLORE A LOCATION
# ==========================================

@route
def explore_location(state):
    location = state.current_location

    if location in state.strongholds:
        key = str(location)

        if state.stronghold_progress.get(key, "") == "first_guard_done":
            state.message = "You have already defeated the first guardian."
            return location_page(state)

        start_combat(
            state,
            "Guardian",
            60,
            10,
            "stronghold_first"
        )

        state.location_stage = 1
        return index(state)

    if location in state.iron_mines:
        key = str(location)

        if state.mine_progress.get(key, "") == "first_guard_done":
            state.message = "You have already defeated the Iron Miner."
            return location_page(state)

        start_combat(
            state,
            "Iron Miner",
            120,
            15,
            "mine_first"
        )

        state.location_stage = 1
        return index(state)

    if location in state.houses:
        key = str(location)

        if state.house_progress.get(key, "") == "first_guard_done":
            state.message = "You have already defeated the first guardian."
            return location_page(state)

        start_combat(
            state,
            "House Guardian",
            60,
            10,
            "house_first"
        )

        state.location_stage = 1
        return index(state)

    return map_page(state)


# ==========================================
# EXPLORE FURTHER: STRONGHOLD
# ==========================================

@route
def explore_further(state):
    chance = random.randint(1, 2)

    if chance == 1:
        state.message = "You found the end of the stronghold!"
        add_log(state, state.message)
        return reach_location_end(state, "stronghold")

    start_combat(
        state,
        "Buff Guardian",
        120,
        15,
        "stronghold_buff"
    )

    return index(state)


# ==========================================
# EXPLORE FURTHER: HOUSE
# ==========================================

@route
def explore_house_further(state):
    chance = random.randint(1, 2)

    if chance == 1:
        state.message = "You found the end of the house!"
        add_log(state, state.message)
        return reach_location_end(state, "house")

    start_combat(
        state,
        "Stronger House Guardian",
        120,
        15,
        "house_buff"
    )

    return index(state)


# ==========================================
# EXPLORE FURTHER: IRON MINE
# ==========================================

@route
def explore_mine_further(state):
    chance = random.randint(1, 2)

    if chance == 1:
        state.message = "You found the end of the iron mine!"
        add_log(state, state.message)
        return reach_location_end(state, "mine")

    start_combat(
        state,
        "Stronger Iron Miner",
        200,
        20,
        "mine_buff"
    )

    return index(state)


# ==========================================
# OUTPOST
# ==========================================

@route
def collect_outpost(state):
    location = state.current_location

    if location in state.claimed_outposts:
        state.message = "You have already collected these supplies."
        return location_page(state)

    amount = random.randint(3, 8)

    state.pending_loot = {
        "rations": amount
    }

    state.loot_return_action = "outpost"
    state.screen = "loot"

    state.message = (
        "The outpost has rations available. "
        "Choose how many you want to carry."
    )

    add_log(state, state.message)
    return loot_page(state)


# ==========================================
# RETURN TO MAP AFTER COMBAT
# ==========================================

@route
def return_to_map(state):
    state.in_encounter = False
    state.game_over = False
    state.victory = False

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
        Text("Maximum health: " + str(state.player_max_health)),
        Text("Carrying capacity: " + str(state.capacity)),
        Text(
            "Current weight: " + str(inventory_weight(state))
            + " / " + str(state.capacity)
        ),

        Button("Explore", "explore"),
        Button("Storage", "storage_page"),
        Button("Craft", "craft_page"),

        Header("Camp Activities"),
        Button("Set / Collect Traps", "use_traps"),
        Button("Scavenge for Wood", "scavenge")
    ]

    if state.message:
        content.append(Text(state.message))

    return Page(state, content)


# ==========================================
# STORAGE PAGE
# ==========================================

@route
def storage_page(state):
    state.screen = "storage"

    inventory_content = [Header("YOUR INVENTORY")]
    storage_content = [Header("CAMPSITE STORAGE")]

    store_routes = {
        "wood": "store_wood",
        "iron": "store_iron",
        "leather": "store_leather",
        "rations": "store_rations",
        "medicine": "store_medicine",
        "club": "store_club",
        "iron sword": "store_sword",
        "shield": "store_shield"
    }

    take_routes = {
        "wood": "take_wood",
        "iron": "take_iron",
        "leather": "take_leather",
        "rations": "take_rations",
        "medicine": "take_medicine",
        "club": "take_club",
        "iron sword": "take_sword",
        "shield": "take_shield"
    }

    for item in ALL_ITEMS:
        amount = state.inventory.get(item, 0)

        inventory_content.append(
            Div(
                Text(item.title() + ": " + str(amount)),
                Button("-", store_routes[item])
            )
        )

    inventory_content.append(
        Text(
            "Weight: " + str(inventory_weight(state))
            + " / " + str(state.capacity)
        )
    )

    for item in ALL_ITEMS:
        amount = state.storage.get(item, 0)

        storage_content.append(
            Div(
                Text(item.title() + ": " + str(amount)),
                Button("+", take_routes[item])
            )
        )

    content = event_log_content(state) + [
        Header("CAMPSITE STORAGE"),
        Text("Use - to store one carried item. Use + to take one stored item."),
        Div(
            Div(*inventory_content, id="carried_column"),
            Div(*storage_content, id="storage_column"),
            id="storage_columns"
        ),
        Button("Back to Camp", "camp_page")
    ]

    if state.message:
        content.append(Text(state.message))

    return Page(
        state,
        content,
        css="""
        #storage_columns {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            align-items: start;
        }

        #carried_column, #storage_column {
            border: 1px solid #777;
            padding: 12px;
            border-radius: 6px;
            min-width: 0;
        }

        @media (max-width: 600px) {
            #storage_columns {
                grid-template-columns: 1fr;
            }
        }
        """
    )


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
def store_shield(state):
    transfer_to_storage(state, "shield")
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


@route
def take_shield(state):
    transfer_to_inventory(state, "shield")
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

    # Outposts can be collected again on each expedition.
    state.claimed_outposts = []

    # Houses can be explored once per expedition.
    state.completed_houses = []
    state.house_progress = {}

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

    # Do not automatically deposit the player's inventory.
    # The player chooses what to store on the Storage page.

    state.in_encounter = False
    state.game_over = False
    state.victory = False

    state.screen = "camp"

    state.message = "You return safely to the campsite with your inventory."
    add_log(state, state.message)

    return camp_page(state)


# ==========================================
# TRAPS
# ==========================================

@route
def use_traps(state):
    current_time = time.time()

    if state.last_trap_time <= 0:
        state.last_trap_time = current_time

        state.message = (
            "You set " + str(state.trap_count)
            + " trap(s). Return in 30 seconds to collect."
        )

        add_log(state, state.message)
        return camp_page(state)

    elapsed = current_time - state.last_trap_time

    if elapsed < TRAP_COOLDOWN:
        remaining = int(TRAP_COOLDOWN - elapsed) + 1

        state.message = (
            "Your traps need " + str(remaining)
            + " more seconds."
        )

        return camp_page(state)

    total_rations = 0

    for i in range(state.trap_count):
        total_rations += random.randint(3, 6)

    # Trap rations go directly into campsite storage.
    state.storage["rations"] = (
        state.storage.get("rations", 0) + total_rations
    )

    state.last_trap_time = 0

    state.message = (
        "You collected " + str(total_rations)
        + " rations from your traps! They were placed in storage."
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
                "You must wait " + str(remaining)
                + " seconds before scavenging again."
            )

            return camp_page(state)

    amount = random.randint(2, 3)

    # Scavenged wood goes directly into campsite storage.
    state.storage["wood"] = (
        state.storage.get("wood", 0) + amount
    )

    state.last_scavenge_time = current_time

    state.message = (
        "You scavenged " + str(amount)
        + " pieces of wood and placed them in storage."
    )

    add_log(state, state.message)
    return camp_page(state)


# ==========================================
# CRAFTING PAGE
# ==========================================

@route
def craft_page(state):
    state.screen = "craft"

    if state.iron_crafting_unlocked:
        iron_button_label = "Craft 1 Iron (10 Rations)"
    else:
        iron_button_label = "Missing requirement: must clear Iron mine"

    content = event_log_content(state) + [
        Header("CRAFTING"),
        Text("Crafting uses materials stored at the campsite."),

        Header("Equipment"),
        Button("Craft Medicine (5 Rations)", "craft_medicine"),
        Button("Craft Club (3 Wood)", "craft_club"),
        Button("Craft Iron Sword (2 Iron, 1 Wood)", "craft_sword"),
        Button("Craft Shield (1 Iron, 5 Wood, 2 Leather)", "craft_shield"),

        Header("Iron Crafting"),

        Button(
            iron_button_label,
            "craft_iron"
        ),

        Header("Armour"),

        Button(
            "Craft Leather Armour (+50 Max HP, 10 Leather)",
            "craft_leather_armour",
            disabled=state.leather_armour
        ),

        Button(
            "Craft Iron Armour (+100 Max HP, 10 Iron)",
            "craft_iron_armour"
        ),

        Header("Carrying Upgrades"),
        Text("Current capacity: " + str(state.capacity)),

        Button(
            "Leather Backpack (+20 capacity, 5 Leather)",
            "craft_backpack",
            disabled=state.capacity >= 60
        ),

        Button(
            "Convoy (+40 capacity, 10 Wood, 5 Iron)",
            "upgrade_convoy"
        ),

        Header("Camp Upgrades"),

        Button("Upgrade Trap Capacity", "upgrade_traps"),
        Text("Current traps: " + str(state.trap_count)),
        Text(
            "Next trap upgrade cost: "
            + str(state.trap_count * 2)
            + " wood"
        ),

        Button("Back to Camp", "camp_page")
    ]

    if state.message:
        content.append(Text(state.message))

    return Page(state, content)


# ==========================================
# CRAFTING: MEDICINE
# ==========================================

@route
def craft_medicine(state):
    if not storage_has(state, "rations", 5):
        state.message = "You need 5 stored rations."
        return craft_page(state)

    state.storage["rations"] -= 5

    if state.storage["rations"] == 0:
        del state.storage["rations"]

    state.storage["medicine"] = (
        state.storage.get("medicine", 0) + 1
    )

    state.message = "You crafted 1 medicine!"
    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# CRAFTING: CLUB
# ==========================================

@route
def craft_club(state):
    if not storage_has(state, "wood", 3):
        state.message = "You need 3 stored wood."
        return craft_page(state)

    state.storage["wood"] -= 3

    if state.storage["wood"] == 0:
        del state.storage["wood"]

    state.storage["club"] = (
        state.storage.get("club", 0) + 1
    )

    state.message = "You crafted a club!"
    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# CRAFTING: IRON SWORD
# ==========================================

@route
def craft_sword(state):
    if not storage_has(state, "iron", 2):
        state.message = "You need 2 stored iron."
        return craft_page(state)

    if not storage_has(state, "wood", 1):
        state.message = "You need 1 stored wood."
        return craft_page(state)

    state.storage["iron"] -= 2
    state.storage["wood"] -= 1

    if state.storage["iron"] == 0:
        del state.storage["iron"]

    if state.storage["wood"] == 0:
        del state.storage["wood"]

    state.storage["iron sword"] = (
        state.storage.get("iron sword", 0) + 1
    )

    state.message = "You crafted an Iron Sword!"
    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# CRAFTING: SHIELD
# ==========================================

@route
def craft_shield(state):
    if not storage_has(state, "iron", 1):
        state.message = "You need 1 stored iron."
        return craft_page(state)

    if not storage_has(state, "wood", 5):
        state.message = "You need 5 stored wood."
        return craft_page(state)

    if not storage_has(state, "leather", 2):
        state.message = "You need 2 stored leather."
        return craft_page(state)

    state.storage["iron"] -= 1
    state.storage["wood"] -= 5
    state.storage["leather"] -= 2

    for item in ["iron", "wood", "leather"]:
        if state.storage[item] == 0:
            del state.storage[item]

    state.storage["shield"] = state.storage.get("shield", 0) + 1

    state.message = (
        "You crafted a Shield! Move it from storage into your inventory "
        "to gain a second evasion roll during combat."
    )

    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# CRAFTING: IRON
# ==========================================

@route
def craft_iron(state):
    if not state.iron_crafting_unlocked:
        state.message = "Missing requirement: must clear Iron mine"
        return craft_page(state)

    if not storage_has(state, "rations", 10):
        state.message = "You need 10 stored rations."
        return craft_page(state)

    state.storage["rations"] -= 10

    if state.storage["rations"] == 0:
        del state.storage["rations"]

    state.storage["iron"] = state.storage.get("iron", 0) + 1

    state.message = "You crafted 1 iron from 10 rations!"
    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# CRAFTING: LEATHER ARMOUR
# ==========================================

@route
def craft_leather_armour(state):
    if state.leather_armour:
        state.message = "You already have leather armour."
        return craft_page(state)

    if not storage_has(state, "leather", 10):
        state.message = "You need 10 stored leather."
        return craft_page(state)

    state.storage["leather"] -= 10

    if state.storage["leather"] == 0:
        del state.storage["leather"]

    state.leather_armour = True

    state.player_max_health += 50
    state.player_health += 50

    state.message = (
        "You crafted leather armour! Your health is now "
        + str(state.player_health) + " / "
        + str(state.player_max_health) + "."
    )

    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# CRAFTING: IRON ARMOUR
# ==========================================

@route
def craft_iron_armour(state):
    if not state.leather_armour:
        state.message = "Missing requirement: Leather Armour."
        return craft_page(state)

    if state.iron_armour:
        state.message = "You already have iron armour."
        return craft_page(state)

    if not storage_has(state, "iron", 10):
        state.message = "You need 10 stored iron."
        return craft_page(state)

    state.storage["iron"] -= 10

    if state.storage["iron"] == 0:
        del state.storage["iron"]

    state.iron_armour = True

    state.player_max_health += 100
    state.player_health += 100

    state.message = (
        "You crafted iron armour! Your health is now "
        + str(state.player_health) + " / "
        + str(state.player_max_health) + "."
    )

    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# CRAFTING: BACKPACK
# ==========================================

@route
def craft_backpack(state):
    if state.capacity >= 60:
        state.message = "You already have a backpack upgrade."
        return craft_page(state)

    if not storage_has(state, "leather", 5):
        state.message = "You need 5 stored leather."
        return craft_page(state)

    state.storage["leather"] -= 5

    if state.storage["leather"] == 0:
        del state.storage["leather"]

    state.capacity = 60

    state.message = "You crafted a leather backpack. Capacity is now 60."
    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# CRAFTING: CONVOY
# ==========================================

@route
def upgrade_convoy(state):
    if state.capacity < 60:
        state.message = "Missing requirement: Leather Backpack."
        return craft_page(state)

    if state.capacity >= 100:
        state.message = "You already have maximum carrying capacity."
        return craft_page(state)

    if not storage_has(state, "wood", 10):
        state.message = "You need 10 stored wood."
        return craft_page(state)

    if not storage_has(state, "iron", 5):
        state.message = "You need 5 stored iron."
        return craft_page(state)

    state.storage["wood"] -= 10
    state.storage["iron"] -= 5

    if state.storage["wood"] == 0:
        del state.storage["wood"]

    if state.storage["iron"] == 0:
        del state.storage["iron"]

    state.capacity = 100

    state.message = "Your convoy is ready! Capacity is now 100."
    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# CRAFTING: TRAPS
# ==========================================

@route
def upgrade_traps(state):
    if state.trap_count >= 5:
        state.message = "You already have the maximum of 5 traps."
        return craft_page(state)

    cost = state.trap_count * 2

    if not storage_has(state, "wood", cost):
        state.message = "You need " + str(cost) + " stored wood."
        return craft_page(state)

    state.storage["wood"] -= cost

    if state.storage["wood"] == 0:
        del state.storage["wood"]

    state.trap_count += 1

    state.message = (
        "You upgraded your trap capacity to "
        + str(state.trap_count)
        + " traps! The next upgrade will cost "
        + str(state.trap_count * 2)
        + " wood."
    )

    add_log(state, state.message)
    return craft_page(state)


# ==========================================
# START GAME
# ==========================================

houses, strongholds, iron_mines = create_locations()

initial_explored = [
    (x, y)
    for y in range(27, 34)
    for x in range(27, 34)
    if not (
        (x == 27 and y == 27)
        or (x == 33 and y == 27)
        or (x == 27 and y == 33)
        or (x == 33 and y == 33)
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
            "rations": 15,
            "medicine": 1,
            "club": 0,
            "iron sword": 0,
            "shield": 0
        },

        # Storage
        {
            "wood": 0,
            "iron": 0,
            "leather": 0,
            "rations": 0,
            "medicine": 0,
            "club": 0,
            "iron sword": 0,
            "shield": 0
        },

        # Starting carrying capacity
        40,

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
        0,

        # Loot and stronghold progress
        {},
        "",
        {},
        [],
        "skeleton",

        # Armour
        False,
        False,

        # New house progress
        {},
        [],

        # Iron mine locations and progress
        iron_mines,
        {},
        [],
        False
    ),
    theme="terminal",
    site_title="THE DUNGEON"
)


